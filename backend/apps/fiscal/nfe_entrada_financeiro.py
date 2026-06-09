"""ERP 4.0.14.4 — Geração manual de Contas a Pagar a partir de NF-e Entrada importada."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction

from apps.financeiro.constants import FormaPagamentoCodigo
from apps.financeiro.models import CategoriaFinanceira, CentroCusto, ContaFinanceira, TituloFinanceiro
from apps.financeiro.services.titulo import TOLERANCIA_PARCELAS, criar_titulo_financeiro
from apps.fiscal.models import NFeEntradaConferencia, NFeEntradaHistoricaImportada
from apps.fiscal.nfe_entrada_duplicatas import montar_parcelas_sugeridas_nf_entrada

CENTAVO = Decimal('0.01')

_CSTAT_CANCELADA = frozenset({'101', '110', '135', '136', '151'})

MSG_CANCELADA = 'Esta NF-e Entrada está cancelada e não pode gerar contas a pagar.'
MSG_JA_GERADO = 'Contas a pagar já foram geradas para esta NF-e Entrada.'
MSG_TITULO_CANCELADO = (
    'Já existe título financeiro vinculado a esta origem, mesmo que cancelado. '
    'Revise antes de gerar novamente.'
)
MSG_SEM_FORNECEDOR = 'Fornecedor não identificado na NF-e Entrada.'
MSG_VALOR_ZERO = 'Valor da NF-e Entrada inválido para gerar financeiro.'
MSG_XML_INVALIDO = 'XML da NF-e Entrada não foi lido ou é inválido para gerar financeiro.'
MSG_PARCELA_VENCIMENTO = 'Informe o vencimento de todas as parcelas.'
MSG_SOMA_PARCELAS = 'A soma das parcelas não confere com o valor total.'
MSG_ALERTA_NFE_CANCELADA = 'A NF-e Entrada de origem foi cancelada. Revise este título financeiro.'
MSG_AVISO_PENDENCIAS_OPERACIONAIS = (
    'Esta NF-e Entrada possui pendências operacionais. As contas a pagar podem ser geradas, '
    'mas estoque, produtos e pedido de compra continuarão pendentes até conferência.'
)
MSG_AVISO_PENDENCIAS_WIZARD = (
    'Esta NF-e Entrada possui pendências operacionais. A geração das contas a pagar não '
    'movimenta estoque, não resolve equivalências e não altera pedido de compra.'
)
MSG_CONFIRMACAO_PENDENCIAS = (
    'Confirme que deseja gerar o financeiro mesmo com pendências operacionais.'
)


def _round_money(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _resolve_conferencia(nf: NFeEntradaHistoricaImportada) -> NFeEntradaConferencia | None:
    try:
        return nf.conferencia
    except NFeEntradaConferencia.DoesNotExist:
        return None


def nfe_entrada_cancelada(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None = None,
) -> bool:
    conf = conferencia if conferencia is not None else _resolve_conferencia(nf)
    if conf and conf.status == NFeEntradaConferencia.Status.CANCELADA:
        return True
    cstat = (nf.cstat or '').strip()
    return cstat in _CSTAT_CANCELADA


def nfe_entrada_xml_valido_para_financeiro(nf: NFeEntradaHistoricaImportada) -> bool:
    if (nf.chave_acesso or '').strip():
        return True
    return bool((nf.numero or '').strip()) and _round_money(nf.valor_total_nf or 0) > 0


def motivo_bloqueio_financeiro_real(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None = None,
    *,
    vinculados: list[TituloFinanceiro] | None = None,
) -> str:
    """Retorna motivo de bloqueio financeiro real ou string vazia se pode gerar."""
    conf = conferencia if conferencia is not None else _resolve_conferencia(nf)
    titulos = vinculados if vinculados is not None else list(titulos_vinculados_nfe_entrada(nf))
    if titulos:
        if any(t.cancelado for t in titulos):
            return MSG_TITULO_CANCELADO
        return MSG_JA_GERADO
    if nfe_entrada_cancelada(nf, conf):
        return MSG_CANCELADA
    if not nf.fornecedor_emitente_id:
        return MSG_SEM_FORNECEDOR
    if _round_money(nf.valor_total_nf or 0) <= 0:
        return MSG_VALOR_ZERO
    if not nfe_entrada_xml_valido_para_financeiro(nf):
        return MSG_XML_INVALIDO
    return ''


def detectar_pendencias_operacionais_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None = None,
) -> dict[str, Any]:
    """Pendências operacionais que não bloqueiam financeiro, mas exigem ciência do usuário."""
    from apps.fiscal.conferencia_pedido import montar_resumo_pedido_conferencia
    from apps.fiscal.models import ItemNFeEntradaConferencia
    from apps.produtos.equivalencia_sugestao import montar_resumo_equivalencias_conferencia

    conf = conferencia if conferencia is not None else _resolve_conferencia(nf)
    motivos: list[str] = []

    if not conf:
        motivos.append('conferencia_nao_iniciada')
    else:
        itens = list(conf.itens.all())
        if conf.status == NFeEntradaConferencia.Status.PENDENTE:
            motivos.append('conferencia_em_andamento')
        if conf.status != NFeEntradaConferencia.Status.PREPARADA and not conf.estoque_aplicado_em:
            if conf.status != NFeEntradaConferencia.Status.CANCELADA:
                motivos.append('estoque_nao_preparado')
        if not conf.estoque_aplicado_em and conf.status != NFeEntradaConferencia.Status.CANCELADA:
            motivos.append('estoque_nao_aplicado')

        for it in itens:
            if it.status == ItemNFeEntradaConferencia.Status.IGNORADO:
                continue
            if not it.produto_id:
                motivos.append('produto_nao_vinculado')
                break
            if it.divergencias and not conf.divergencias_aceitas:
                motivos.append('divergencias_operacionais')
                break
            if it.status in (
                ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO,
                ItemNFeEntradaConferencia.Status.DIVERGENTE,
            ):
                motivos.append('item_conferencia_pendente')
                break

        resumo_pedido = montar_resumo_pedido_conferencia(conf)
        if resumo_pedido.get('pedido_selecionado'):
            totais = resumo_pedido.get('totais') or {}
            if any(
                totais.get(k)
                for k in (
                    'faltantes',
                    'extras',
                    'itens_parciais',
                    'itens_excedentes',
                    'itens_pendentes_global',
                    'itens_parciais_global',
                    'itens_excedentes_global',
                )
            ):
                motivos.append('divergencia_pedido_compra')

        try:
            resumo_eq = montar_resumo_equivalencias_conferencia(conf)
            if resumo_eq.get('sugestoes'):
                motivos.append('equivalencia_pendente')
        except Exception:
            pass

    possui = bool(motivos)
    return {
        'possui_pendencias_operacionais': possui,
        'motivos_pendencias_operacionais': motivos,
        'aviso_pendencias_operacionais': MSG_AVISO_PENDENCIAS_OPERACIONAIS if possui else '',
        'pode_gerar_com_pendencias': possui,
    }


def titulos_vinculados_nfe_entrada(nf: NFeEntradaHistoricaImportada):
    return TituloFinanceiro.objects.filter(
        tipo=TituloFinanceiro.Tipo.PAGAR,
        origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
        origem_id=nf.pk,
    ).order_by('-id')


def numero_nfe_entrada_exibicao(nf: NFeEntradaHistoricaImportada) -> str:
    num = (nf.numero or '').strip()
    return num or str(nf.pk)


def montar_origem_descricao_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None = None,
) -> str:
    conf = conferencia if conferencia is not None else _resolve_conferencia(nf)
    forn = ''
    if nf.fornecedor_emitente_id and nf.fornecedor_emitente:
        forn = nf.fornecedor_emitente.razao_social
    elif nf.emit_json:
        forn = (nf.emit_json.get('xNome') or '').strip()
    base = f'NF-e Entrada do fornecedor {forn}' if forn else 'NF-e Entrada importada'
    chave = (nf.chave_acesso or '').strip()
    if chave:
        base = f'{base} — chave {chave}'
    if conf and conf.pedido_compra_id and conf.pedido_compra:
        base = f'{base} · {conf.pedido_compra.numero}'
    return base


def montar_flags_financeiro_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None = None,
) -> dict[str, Any]:
    conf = conferencia if conferencia is not None else _resolve_conferencia(nf)
    vinculados = list(titulos_vinculados_nfe_entrada(nf))
    financeiro_gerado = bool(vinculados)
    motivo = motivo_bloqueio_financeiro_real(nf, conf, vinculados=vinculados)
    pode_gerar = not financeiro_gerado and not motivo
    pendencias = detectar_pendencias_operacionais_nfe_entrada(nf, conf)

    return {
        'financeiro_gerado': financeiro_gerado,
        'pode_gerar_contas_pagar': pode_gerar,
        'motivo_bloqueio_financeiro': motivo,
        **pendencias,
        'contas_pagar_vinculadas': [
            {
                'id': t.id,
                'numero': t.numero,
                'status': t.status,
                'cancelado': t.cancelado,
            }
            for t in vinculados
        ],
        'nfe_entrada_cancelada_com_financeiro': nfe_entrada_cancelada(nf, conf) and financeiro_gerado,
    }


def sugerir_categoria_despesa_id(*, servico: bool = False) -> int | None:
    nome = 'Serviços de terceiros' if servico else 'Compra de mercadorias'
    cat = (
        CategoriaFinanceira.objects.filter(nome__iexact=nome, ativo=True)
        .filter(tipo__in=(CategoriaFinanceira.Tipo.DESPESA, CategoriaFinanceira.Tipo.AMBOS))
        .first()
    )
    if cat:
        return cat.pk
    if servico:
        return None
    cat = (
        CategoriaFinanceira.objects.filter(nome__iexact='Compra de mercadorias', ativo=True)
        .filter(tipo__in=(CategoriaFinanceira.Tipo.DESPESA, CategoriaFinanceira.Tipo.AMBOS))
        .first()
    )
    return cat.pk if cat else None


def _eh_nota_servico(nf: NFeEntradaHistoricaImportada) -> bool:
    nat = (nf.nat_op or '').lower()
    return 'serv' in nat


def preview_contas_pagar_de_nfe_entrada(nf: NFeEntradaHistoricaImportada) -> dict[str, Any]:
    conf = _resolve_conferencia(nf)
    motivo = motivo_bloqueio_financeiro_real(nf, conf)
    if motivo:
        raise ValueError(motivo)

    total = _round_money(nf.valor_total_nf or 0)
    parcelas = montar_parcelas_sugeridas_nf_entrada(nf, conf)
    flags = montar_flags_financeiro_nfe_entrada(nf, conf)
    forn = nf.fornecedor_emitente
    pedido_numero = conf.pedido_compra.numero if conf and conf.pedido_compra_id else ''

    return {
        **flags,
        'aviso_pendencias_wizard': MSG_AVISO_PENDENCIAS_WIZARD if flags.get('possui_pendencias_operacionais') else '',
        'fornecedor': {
            'id': nf.fornecedor_emitente_id,
            'nome': forn.razao_social if forn else '',
            'cnpj': forn.cnpj if forn else '',
        },
        'origem': {
            'tipo': TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
            'id': nf.pk,
            'numero': numero_nfe_entrada_exibicao(nf),
            'serie': nf.serie or '',
            'chave_acesso': nf.chave_acesso or '',
            'data_emissao': nf.dh_emissao.date().isoformat() if nf.dh_emissao else None,
            'data_importacao': nf.importado_em.isoformat() if nf.importado_em else None,
            'descricao': montar_origem_descricao_nfe_entrada(nf, conf),
            'valor_total': str(total),
            'pedido_compra_id': conf.pedido_compra_id if conf else None,
            'pedido_compra_numero': pedido_numero,
        },
        'parcelas': parcelas,
        'quantidade_parcelas_sugeridas': len(parcelas),
        'categoria_sugerida_id': sugerir_categoria_despesa_id(servico=_eh_nota_servico(nf)),
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


def titulo_origem_nfe_entrada_cancelada(titulo: TituloFinanceiro) -> bool:
    if titulo.origem_tipo != TituloFinanceiro.OrigemTipo.NFE_ENTRADA or not titulo.origem_id:
        return False
    nf = NFeEntradaHistoricaImportada.objects.filter(pk=titulo.origem_id).first()
    if not nf:
        return False
    return nfe_entrada_cancelada(nf)


def montar_origem_nfe_entrada_detalhe(titulo: TituloFinanceiro) -> dict[str, Any] | None:
    if titulo.origem_tipo != TituloFinanceiro.OrigemTipo.NFE_ENTRADA or not titulo.origem_id:
        return None
    nf = (
        NFeEntradaHistoricaImportada.objects.select_related('fornecedor_emitente')
        .filter(pk=titulo.origem_id)
        .first()
    )
    if not nf:
        return None
    conf = _resolve_conferencia(nf)
    pedido_numero = conf.pedido_compra.numero if conf and conf.pedido_compra_id else ''
    return {
        'nfe_entrada_id': nf.pk,
        'numero_nfe': numero_nfe_entrada_exibicao(nf),
        'serie_nfe': nf.serie or '',
        'chave_acesso': nf.chave_acesso or '',
        'data_emissao': nf.dh_emissao.date().isoformat() if nf.dh_emissao else None,
        'data_importacao': nf.importado_em.isoformat() if nf.importado_em else None,
        'fornecedor_nome': nf.fornecedor_emitente.razao_social if nf.fornecedor_emitente_id else '',
        'pedido_compra_numero': pedido_numero,
        'origem_cancelada': nfe_entrada_cancelada(nf, conf),
        'alerta_origem_cancelada': MSG_ALERTA_NFE_CANCELADA if nfe_entrada_cancelada(nf, conf) else '',
    }


@transaction.atomic
def gerar_contas_pagar_de_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    *,
    parcelas: list[dict],
    categoria_id: int | None = None,
    centro_custo_id: int | None = None,
    forma_pagamento_prevista_codigo: str = '',
    conta_financeira_prevista_id: int | None = None,
    observacoes: str = '',
    confirmar_pendencias_operacionais: bool = False,
    usuario=None,
) -> TituloFinanceiro:
    conf = _resolve_conferencia(nf)
    flags = montar_flags_financeiro_nfe_entrada(nf, conf)
    motivo = flags.get('motivo_bloqueio_financeiro') or ''
    if flags['financeiro_gerado'] or motivo:
        raise ValueError(motivo or MSG_JA_GERADO)
    if flags.get('possui_pendencias_operacionais') and not confirmar_pendencias_operacionais:
        raise ValueError(MSG_CONFIRMACAO_PENDENCIAS)

    total = _round_money(nf.valor_total_nf or 0)

    _validar_categoria(categoria_id)
    _validar_centro_custo(centro_custo_id)
    _validar_conta_financeira(conta_financeira_prevista_id)
    _validar_forma_pagamento(forma_pagamento_prevista_codigo)

    parcelas_norm = _validar_parcelas_payload(parcelas, total)
    primeiro_venc = min(p['data_vencimento'] for p in parcelas_norm)
    origem_numero = numero_nfe_entrada_exibicao(nf)
    data_emissao = nf.dh_emissao.date() if nf.dh_emissao else date.today()
    competencia = date(data_emissao.year, data_emissao.month, 1)

    return criar_titulo_financeiro(
        tipo=TituloFinanceiro.Tipo.PAGAR,
        fornecedor_id=nf.fornecedor_emitente_id,
        tipo_lancamento=TituloFinanceiro.TipoLancamentoPagar.FORNECEDOR,
        data_emissao=data_emissao,
        data_vencimento=primeiro_venc,
        competencia=competencia,
        valor_original=total,
        origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
        origem_id=nf.pk,
        origem_numero=origem_numero,
        origem_descricao=montar_origem_descricao_nfe_entrada(nf, conf),
        origem_data=data_emissao,
        documento_origem=f'NF-e Entrada nº {origem_numero}',
        forma_pagamento_prevista_codigo=forma_pagamento_prevista_codigo,
        conta_financeira_prevista_id=conta_financeira_prevista_id,
        categoria_id=categoria_id,
        centro_custo_id=centro_custo_id,
        observacoes=observacoes,
        parcelas_custom=parcelas_norm,
        usuario=usuario,
    )
