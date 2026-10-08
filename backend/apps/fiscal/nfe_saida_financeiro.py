"""ERP 4.0.14.3 — Contas a Receber a partir de NF-e (manual + automático pós-produção)."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.financeiro.constants import FormaPagamentoCodigo
from apps.financeiro.models import CategoriaFinanceira, CentroCusto, ContaFinanceira, TituloFinanceiro
from apps.financeiro.services.titulo import TOLERANCIA_PARCELAS, criar_titulo_financeiro
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_bloqueio import (
    _status_normalizado,
    nf_autorizada_homologacao,
    nf_autorizada_producao,
    nf_cancelada_operacional,
)
from apps.fiscal.nfe_saida_condicao_pagamento import (
    filtrar_queryset_deve_gerar_cobranca_a_prazo,
    nfe_venda_integralmente_a_vista,
)
from apps.fiscal.nfe_saida_duplicatas import gerar_duplicatas_nfe_saida

logger = logging.getLogger(__name__)

CENTAVO = Decimal('0.01')
CSTAT_AUTORIZADO = frozenset({'100', '150'})
_STATUS_CANCELADA_LISTAGEM = frozenset({
    'CANCELADA',
    'CANCELADO',
    'CANCELADA_INTERNA',
    'CANCELADA_HOMOLOGACAO',
    'CANCELADA_PRODUCAO',
})

MSG_NAO_AUTORIZADA = 'Esta NF-e ainda não está autorizada.'
MSG_CANCELADA = 'Esta NF-e está cancelada e não pode gerar contas a receber.'
MSG_JA_GERADO = 'Contas a receber já foram geradas para esta NF-e.'
MSG_TITULO_CANCELADO = (
    'Já existe título financeiro vinculado a esta origem, mesmo que cancelado. '
    'Revise antes de gerar novamente.'
)
MSG_SEM_CLIENTE = 'Informe o cliente para contas a receber.'
MSG_VALOR_ZERO = 'O valor do título deve ser maior que zero.'
MSG_PARCELA_VENCIMENTO = 'Informe o vencimento de todas as parcelas.'
MSG_SOMA_PARCELAS = 'A soma das parcelas não confere com o valor total.'
MSG_ALERTA_NFE_CANCELADA = 'A NF-e de origem foi cancelada. Revise este título financeiro.'
MSG_CR_GERADO = 'Contas a receber gerado.'
MSG_CR_JA_EXISTENTE = 'Contas a receber já gerado.'
MSG_VENDA_A_VISTA = 'Venda à vista — não gera Contas a Receber.'
MSG_AUTO_FALHA_CR = (
    'NF-e autorizada, mas não foi possível gerar o Contas a Receber. '
    'Use a ação Gerar contas a receber para regularizar.'
)
MSG_AUTO_NAO_APLICAVEL_A_VISTA = MSG_VENDA_A_VISTA


def filtrar_queryset_autorizadas_a_prazo_sem_contas_receber(
    qs: QuerySet[NFeSaida],
) -> QuerySet[NFeSaida]:
    """
    NF-e autorizadas em produção, elegíveis a CR a prazo, sem título RECEBER vinculado.

    Critérios alinhados às flags financeiras e a ``nfe_deve_gerar_cobranca_a_prazo``:
    - ``status_emissao_sefaz`` / ``status`` de autorização em produção;
    - não cancelada;
    - cliente e valor_total > 0;
    - não integralmente à vista (``[0]``);
    - sem ``TituloFinanceiro`` RECEBER com ``origem_tipo=NFE_SAIDA`` e ``origem_id``.
    """
    qs = qs.filter(
        Q(status_emissao_sefaz__iexact=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO)
        | Q(status__iexact='AUTORIZADA_PRODUCAO'),
    )
    qs = qs.exclude(status__in=_STATUS_CANCELADA_LISTAGEM)
    qs = qs.exclude(status_emissao_sefaz__icontains='CANCEL')
    qs = qs.filter(cliente_id__isnull=False).exclude(valor_total__lte=0)
    qs = filtrar_queryset_deve_gerar_cobranca_a_prazo(qs)

    titulo_cr = TituloFinanceiro.objects.filter(
        tipo=TituloFinanceiro.Tipo.RECEBER,
        origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
        origem_id=OuterRef('pk'),
    )
    return qs.filter(~Exists(titulo_cr))


def _round_money(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def nf_cancelada(nf: NFeSaida) -> bool:
    return nf_cancelada_operacional(nf)


MSG_HOMOLOG_SEM_FINANCEIRO = 'Financeiro indisponível para NF-e de homologação.'


def nf_autorizada_para_financeiro(nf: NFeSaida) -> bool:
    if nf_autorizada_homologacao(nf):
        return False
    if nf_autorizada_producao(nf):
        return True
    st = _status_normalizado(nf.status)
    return st in ('AUTORIZADA', 'AUTORIZADA_INTERNA', 'EMITIDA', 'EMITIDO')


def titulos_vinculados_nfe(nf: NFeSaida):
    return TituloFinanceiro.objects.filter(
        tipo=TituloFinanceiro.Tipo.RECEBER,
        origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
        origem_id=nf.pk,
    ).order_by('-id')


def numero_nfe_exibicao(nf: NFeSaida) -> str:
    num = (nf.numero_nfe or nf.numero or '').strip()
    return num or str(nf.pk)


def montar_origem_descricao_nfe(nf: NFeSaida) -> str:
    chave = (nf.chave_acesso or '').strip()
    if nf_autorizada_homologacao(nf):
        base = 'NF-e autorizada em homologação'
    elif nf_autorizada_producao(nf):
        base = 'NF-e autorizada em produção'
    else:
        base = 'NF-e autorizada'
    if chave:
        return f'{base} — chave {chave}'
    return base


def montar_flags_financeiro_nfe(nf: NFeSaida) -> dict[str, Any]:
    vinculados = list(titulos_vinculados_nfe(nf))
    financeiro_gerado = bool(vinculados)
    tem_cancelado = any(t.cancelado for t in vinculados)
    venda_a_vista = nfe_venda_integralmente_a_vista(nf)

    pode_gerar = False
    motivo = ''

    if financeiro_gerado:
        motivo = MSG_TITULO_CANCELADO if tem_cancelado else MSG_JA_GERADO
    elif nf_cancelada(nf):
        motivo = MSG_CANCELADA
    elif nf_autorizada_homologacao(nf):
        motivo = MSG_HOMOLOG_SEM_FINANCEIRO
    elif venda_a_vista:
        motivo = MSG_VENDA_A_VISTA
    elif not nf_autorizada_para_financeiro(nf):
        motivo = 'Disponível após autorização da NF-e.'
    elif not nf.cliente_id:
        motivo = MSG_SEM_CLIENTE
    elif _round_money(nf.valor_total or 0) <= 0:
        motivo = MSG_VALOR_ZERO
    else:
        pode_gerar = True

    return {
        'financeiro_gerado': financeiro_gerado,
        'pode_gerar_contas_receber': pode_gerar,
        'motivo_bloqueio_financeiro': motivo,
        'venda_integralmente_a_vista': venda_a_vista,
        'contas_receber_vinculadas': [
            {
                'id': t.id,
                'numero': t.numero,
                'status': t.status,
                'cancelado': t.cancelado,
            }
            for t in vinculados
        ],
        'nfe_cancelada_com_financeiro': nf_cancelada(nf) and financeiro_gerado,
    }


def _parse_iso_date(value: str | date | None) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def montar_parcelas_sugeridas_nfe(nf: NFeSaida) -> list[dict[str, Any]]:
    if nfe_venda_integralmente_a_vista(nf):
        return []

    dups = gerar_duplicatas_nfe_saida(nf)
    if not dups:
        venc = nf.data or date.today()
        total = _round_money(nf.valor_total or 0)
        if total <= 0:
            return []
        return [
            {
                'numero_parcela': 1,
                'vencimento': venc.isoformat(),
                'valor': str(total),
                'observacoes': '',
            },
        ]

    parcelas: list[dict[str, Any]] = []
    for idx, dup in enumerate(dups, start=1):
        try:
            num = int(dup['numero'])
        except (TypeError, ValueError):
            num = idx
        parcelas.append(
            {
                'numero_parcela': num,
                'vencimento': dup['vencimento'],
                'valor': str(_round_money(dup['valor'])),
                'observacoes': '',
            },
        )
    return parcelas


def sugerir_categoria_receita_id() -> int | None:
    cat = (
        CategoriaFinanceira.objects.filter(
            nome__iexact='Venda de mercadorias',
            ativo=True,
        )
        .filter(tipo__in=(CategoriaFinanceira.Tipo.RECEITA, CategoriaFinanceira.Tipo.AMBOS))
        .first()
    )
    return cat.pk if cat else None


def preview_contas_receber_de_nfe(nf: NFeSaida) -> dict[str, Any]:
    if nf_cancelada(nf):
        raise ValueError(MSG_CANCELADA)
    if nf_autorizada_homologacao(nf):
        raise ValueError(MSG_HOMOLOG_SEM_FINANCEIRO)
    if nfe_venda_integralmente_a_vista(nf):
        raise ValueError(MSG_VENDA_A_VISTA)
    if not nf_autorizada_para_financeiro(nf):
        raise ValueError(MSG_NAO_AUTORIZADA)
    if not nf.cliente_id:
        raise ValueError(MSG_SEM_CLIENTE)

    total = _round_money(nf.valor_total or 0)
    if total <= 0:
        raise ValueError(MSG_VALOR_ZERO)

    parcelas = montar_parcelas_sugeridas_nfe(nf)
    flags = montar_flags_financeiro_nfe(nf)
    pedido_numero = ''
    if nf.pedido_venda_id and nf.pedido_venda:
        pedido_numero = nf.pedido_venda.numero or ''
    fat_numero = ''
    if nf.faturamento_pedido_venda_id and nf.faturamento_pedido_venda:
        fat_numero = nf.faturamento_pedido_venda.numero_faturamento or ''

    return {
        **flags,
        'cliente': {
            'id': nf.cliente_id,
            'nome': nf.cliente.razao_social if nf.cliente_id else '',
        },
        'origem': {
            'tipo': TituloFinanceiro.OrigemTipo.NFE_SAIDA,
            'id': nf.pk,
            'numero': numero_nfe_exibicao(nf),
            'serie': nf.serie_nfe or '',
            'chave_acesso': nf.chave_acesso or '',
            'data_emissao': nf.data.isoformat() if nf.data else None,
            'data_autorizacao': nf.autorizada_em.isoformat() if nf.autorizada_em else None,
            'descricao': montar_origem_descricao_nfe(nf),
            'valor_total': str(total),
            'pedido_venda_numero': pedido_numero,
            'faturamento_numero': fat_numero,
        },
        'parcelas': parcelas,
        'quantidade_parcelas_sugeridas': len(parcelas),
        'categoria_sugerida_id': sugerir_categoria_receita_id(),
    }


def _validar_parcelas_payload(parcelas: list[dict], total: Decimal) -> list[dict]:
    if not parcelas:
        raise ValueError('Informe ao menos uma parcela.')

    normalizadas: list[dict] = []
    soma = Decimal('0')
    for i, parcela in enumerate(parcelas, start=1):
        venc_raw = parcela.get('vencimento') or parcela.get('data_vencimento')
        venc = _parse_iso_date(venc_raw)
        if not venc:
            raise ValueError(MSG_PARCELA_VENCIMENTO)
        val = _round_money(parcela.get('valor', 0))
        if val <= 0:
            raise ValueError('O valor de cada parcela deve ser maior que zero.')
        num = int(parcela.get('numero_parcela') or i)
        normalizadas.append(
            {
                'numero_parcela': num,
                'data_vencimento': venc,
                'valor': val,
                'observacoes': (parcela.get('observacoes') or '')[:500],
            },
        )
        soma += val

    diff = abs(soma - total)
    if diff > TOLERANCIA_PARCELAS:
        raise ValueError(MSG_SOMA_PARCELAS)
    if diff > 0 and normalizadas:
        ajuste = total - soma
        normalizadas[-1]['valor'] = _round_money(normalizadas[-1]['valor'] + ajuste)

    return normalizadas


def _validar_categoria(categoria_id: int | None) -> None:
    if not categoria_id:
        return
    if not CategoriaFinanceira.objects.filter(pk=categoria_id, ativo=True).exists():
        raise ValueError('Categoria financeira inválida.')


def _validar_centro_custo(centro_custo_id: int | None) -> None:
    if not centro_custo_id:
        return
    if not CentroCusto.objects.filter(pk=centro_custo_id, ativo=True).exists():
        raise ValueError('Centro de custo inválido.')


def _validar_conta_financeira(conta_id: int | None) -> None:
    if not conta_id:
        return
    if not ContaFinanceira.objects.filter(pk=conta_id, ativo=True).exists():
        raise ValueError('Conta financeira inválida.')


def _validar_forma_pagamento(codigo: str) -> None:
    if not codigo:
        return
    validos = {c for c, _ in FormaPagamentoCodigo.CHOICES}
    if codigo not in validos:
        raise ValueError('Forma de pagamento prevista inválida.')


def titulo_origem_nfe_cancelada(titulo: TituloFinanceiro) -> bool:
    if titulo.origem_tipo != TituloFinanceiro.OrigemTipo.NFE_SAIDA or not titulo.origem_id:
        return False
    nf = NFeSaida.objects.filter(pk=titulo.origem_id).only('status', 'status_emissao_sefaz').first()
    if not nf:
        return False
    return nf_cancelada(nf)


def montar_origem_nfe_detalhe(titulo: TituloFinanceiro) -> dict[str, Any] | None:
    if titulo.origem_tipo != TituloFinanceiro.OrigemTipo.NFE_SAIDA or not titulo.origem_id:
        return None
    nf = (
        NFeSaida.objects.select_related('pedido_venda', 'faturamento_pedido_venda')
        .filter(pk=titulo.origem_id)
        .first()
    )
    if not nf:
        return None
    pedido_numero = nf.pedido_venda.numero if nf.pedido_venda_id else ''
    fat_numero = (
        nf.faturamento_pedido_venda.numero_faturamento if nf.faturamento_pedido_venda_id else ''
    )
    return {
        'nfe_id': nf.pk,
        'numero_nfe': numero_nfe_exibicao(nf),
        'serie_nfe': nf.serie_nfe or '',
        'chave_acesso': nf.chave_acesso or '',
        'data_autorizacao': nf.autorizada_em.isoformat() if nf.autorizada_em else None,
        'pedido_venda_numero': pedido_numero,
        'faturamento_numero': fat_numero,
        'origem_cancelada': nf_cancelada(nf),
        'alerta_origem_cancelada': MSG_ALERTA_NFE_CANCELADA if nf_cancelada(nf) else '',
    }


def nf_comprovadamente_autorizada_producao_para_cr(nf: NFeSaida) -> bool:
    """Critérios estritos para disparo automático de CR após autorização SEFAZ produção."""
    if nf_cancelada(nf):
        return False
    if nf_autorizada_homologacao(nf):
        return False
    if not nf_autorizada_producao(nf):
        return False
    if (nf.ambiente_emissao or '').strip() != NFeSaida.AmbienteEmissao.PRODUCAO:
        return False
    if (nf.cstat_autorizacao or '').strip() not in CSTAT_AUTORIZADO:
        return False
    if not (nf.protocolo_autorizacao or '').strip():
        return False
    if not (nf.numero_nfe or nf.numero or '').strip():
        return False
    if not (nf.serie_nfe or '').strip():
        return False
    if not (nf.xml_autorizado or '').strip():
        return False
    return True


def _payload_financeiro_auto(
    *,
    tentado: bool,
    gerado: bool = False,
    ja_existente: bool = False,
    erro: bool = False,
    mensagem: str = '',
    titulo: TituloFinanceiro | None = None,
    nf: NFeSaida | None = None,
) -> dict[str, Any]:
    flags = montar_flags_financeiro_nfe(nf) if nf is not None else {
        'financeiro_gerado': bool(titulo) or ja_existente,
        'pode_gerar_contas_receber': False,
        'motivo_bloqueio_financeiro': '',
        'venda_integralmente_a_vista': False,
        'contas_receber_vinculadas': [],
        'nfe_cancelada_com_financeiro': False,
    }
    return {
        'tentado': tentado,
        'gerado': gerado,
        'ja_existente': ja_existente,
        'erro': erro,
        'mensagem': mensagem,
        'titulo_id': titulo.pk if titulo else (flags['contas_receber_vinculadas'][0]['id'] if flags.get('contas_receber_vinculadas') else None),
        'titulo_numero': (
            titulo.numero
            if titulo
            else (flags['contas_receber_vinculadas'][0]['numero'] if flags.get('contas_receber_vinculadas') else '')
        ),
        'financeiro_gerado': flags['financeiro_gerado'],
        'pode_gerar_contas_receber': flags['pode_gerar_contas_receber'],
        'motivo_bloqueio_financeiro': flags.get('motivo_bloqueio_financeiro') or '',
        'venda_integralmente_a_vista': bool(flags.get('venda_integralmente_a_vista')),
        'contas_receber_vinculadas': flags.get('contas_receber_vinculadas') or [],
    }


def gerar_contas_receber_automatico_apos_autorizacao_producao(
    nf: NFeSaida,
    *,
    usuario=None,
) -> dict[str, Any]:
    """
    Gera CR após autorização SEFAZ de produção persistida.

    Soft-fail: nunca propaga exceção que desfaça a autorização fiscal.
    Idempotente: reprocessamento retorna o título já existente.
    """
    try:
        nf = NFeSaida.objects.select_related('cliente').get(pk=nf.pk)
    except NFeSaida.DoesNotExist:
        logger.warning('AUTO_CR_NFE nfe inexistente')
        return _payload_financeiro_auto(
            tentado=False,
            erro=True,
            mensagem=MSG_AUTO_FALHA_CR,
        )

    if not nf_comprovadamente_autorizada_producao_para_cr(nf):
        return _payload_financeiro_auto(
            tentado=False,
            mensagem='NF-e não elegível para geração automática de Contas a Receber.',
            nf=nf,
        )

    if nfe_venda_integralmente_a_vista(nf):
        return _payload_financeiro_auto(
            tentado=False,
            mensagem=MSG_AUTO_NAO_APLICAVEL_A_VISTA,
            nf=nf,
        )

    try:
        with transaction.atomic():
            nf = NFeSaida.objects.select_for_update().select_related('cliente').get(pk=nf.pk)
            vinculados = list(titulos_vinculados_nfe(nf).select_for_update())
            if vinculados:
                titulo = vinculados[0]
                return _payload_financeiro_auto(
                    tentado=True,
                    ja_existente=True,
                    mensagem=MSG_CR_JA_EXISTENTE,
                    titulo=titulo,
                    nf=nf,
                )

            if nfe_venda_integralmente_a_vista(nf):
                return _payload_financeiro_auto(
                    tentado=False,
                    mensagem=MSG_AUTO_NAO_APLICAVEL_A_VISTA,
                    nf=nf,
                )

            parcelas = montar_parcelas_sugeridas_nfe(nf)
            if not parcelas:
                logger.warning('AUTO_CR_NFE sem parcelas válidas nfe_id=%s', nf.pk)
                return _payload_financeiro_auto(
                    tentado=True,
                    erro=True,
                    mensagem=MSG_AUTO_FALHA_CR,
                    nf=nf,
                )

            titulo = gerar_contas_receber_de_nfe_autorizada(
                nf,
                parcelas=parcelas,
                categoria_id=sugerir_categoria_receita_id(),
                usuario=usuario,
            )
            return _payload_financeiro_auto(
                tentado=True,
                gerado=True,
                mensagem=MSG_CR_GERADO,
                titulo=titulo,
                nf=nf,
            )
    except ValueError as exc:
        msg = str(exc)
        if MSG_JA_GERADO in msg or MSG_TITULO_CANCELADO in msg:
            flags = montar_flags_financeiro_nfe(nf)
            titulo = None
            if flags['contas_receber_vinculadas']:
                titulo = TituloFinanceiro.objects.filter(
                    pk=flags['contas_receber_vinculadas'][0]['id'],
                ).first()
            return _payload_financeiro_auto(
                tentado=True,
                ja_existente=True,
                mensagem=MSG_CR_JA_EXISTENTE,
                titulo=titulo,
                nf=nf,
            )
        logger.warning('AUTO_CR_NFE falha operacional nfe_id=%s detalhe=%s', nf.pk, msg[:200])
        return _payload_financeiro_auto(
            tentado=True,
            erro=True,
            mensagem=MSG_AUTO_FALHA_CR,
            nf=nf,
        )
    except Exception:
        logger.exception('AUTO_CR_NFE erro inesperado nfe_id=%s', nf.pk)
        return _payload_financeiro_auto(
            tentado=True,
            erro=True,
            mensagem=MSG_AUTO_FALHA_CR,
            nf=nf,
        )


@transaction.atomic
def gerar_contas_receber_de_nfe_autorizada(
    nf: NFeSaida,
    *,
    parcelas: list[dict],
    categoria_id: int | None = None,
    centro_custo_id: int | None = None,
    forma_pagamento_prevista_codigo: str = '',
    conta_financeira_prevista_id: int | None = None,
    observacoes: str = '',
    usuario=None,
) -> TituloFinanceiro:
    nf = NFeSaida.objects.select_for_update().select_related('cliente').get(pk=nf.pk)
    list(titulos_vinculados_nfe(nf).select_for_update())

    flags = montar_flags_financeiro_nfe(nf)
    if flags['financeiro_gerado']:
        if any(t['cancelado'] for t in flags['contas_receber_vinculadas']):
            raise ValueError(MSG_TITULO_CANCELADO)
        raise ValueError(MSG_JA_GERADO)
    if nf_cancelada(nf):
        raise ValueError(MSG_CANCELADA)
    if nf_autorizada_homologacao(nf):
        raise ValueError(MSG_HOMOLOG_SEM_FINANCEIRO)
    if nfe_venda_integralmente_a_vista(nf):
        raise ValueError(MSG_VENDA_A_VISTA)
    if not nf_autorizada_para_financeiro(nf):
        raise ValueError(MSG_NAO_AUTORIZADA)
    if not nf.cliente_id:
        raise ValueError(MSG_SEM_CLIENTE)

    total = _round_money(nf.valor_total or 0)
    if total <= 0:
        raise ValueError(MSG_VALOR_ZERO)

    _validar_categoria(categoria_id)
    _validar_centro_custo(centro_custo_id)
    _validar_conta_financeira(conta_financeira_prevista_id)
    _validar_forma_pagamento(forma_pagamento_prevista_codigo)

    parcelas_norm = _validar_parcelas_payload(parcelas, total)
    primeiro_venc = min(p['data_vencimento'] for p in parcelas_norm)
    origem_numero = numero_nfe_exibicao(nf)

    return criar_titulo_financeiro(
        tipo=TituloFinanceiro.Tipo.RECEBER,
        cliente_id=nf.cliente_id,
        data_emissao=nf.data or date.today(),
        data_vencimento=primeiro_venc,
        valor_original=total,
        origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
        origem_id=nf.pk,
        origem_numero=origem_numero,
        origem_descricao=montar_origem_descricao_nfe(nf),
        origem_data=nf.data,
        documento_origem=f'NF-e nº {origem_numero}',
        forma_pagamento_prevista_codigo=forma_pagamento_prevista_codigo,
        conta_financeira_prevista_id=conta_financeira_prevista_id,
        categoria_id=categoria_id,
        centro_custo_id=centro_custo_id,
        observacoes=observacoes,
        parcelas_custom=parcelas_norm,
        usuario=usuario,
    )
