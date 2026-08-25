"""Serviço de liberação financeira da Proposta Comercial (MVP)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.comercial.analise_financeira_condicao import (
    CondicaoAmbiguaError,
    condicao_aprovada_permitida_mvp,
    condicoes_iguais,
    normalizar_condicao_de_proposta,
    possui_pagamento_futuro,
)
from apps.comercial.analise_financeira_indicadores import montar_indicadores
from apps.comercial.models import AnaliseFinanceiraProposta, AnaliseFinanceiraPropostaEvento, Proposta
from apps.comercial.payment_terms import pagamento_integralmente_a_vista

VALIDADE_PADRAO_DIAS = 15

MSG_SEM_LIBERACAO = (
    'Esta proposta possui pagamento futuro e precisa de liberação financeira '
    'válida antes da conversão em Pedido de Venda.'
)
MSG_CONDICAO_DIVERGENTE = (
    'A condição atual da proposta não corresponde à condição aprovada pelo Financeiro. '
    'Ajuste a proposta ou solicite nova análise.'
)
MSG_VALOR_EXCEDE = 'O valor atual da proposta excede o valor autorizado na análise financeira.'
MSG_EXPIRADA = 'A liberação financeira expirou. Solicite uma nova análise.'
MSG_CLIENTE_DIVERGENTE = (
    'O cliente da proposta não corresponde ao cliente da liberação financeira. '
    'Solicite uma nova análise.'
)
MSG_ANALISE_PENDENTE = (
    'Existe análise financeira em andamento para esta proposta. '
    'Aguarde a decisão do Financeiro antes de converter em Pedido.'
)
MSG_ANALISE_NAO_APROVADA = (
    'A análise financeira desta proposta não foi aprovada. '
    'Ajuste a condição ou solicite nova análise.'
)


class LiberacaoFinanceiraBloqueio(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)

    def as_dict(self) -> dict[str, str]:
        return {'code': self.code, 'detail': self.detail}


def _dec(v) -> Decimal:
    return Decimal(str(v or 0))


def _registrar_evento(analise: AnaliseFinanceiraProposta, tipo: str, ator, dados: dict | None = None):
    AnaliseFinanceiraPropostaEvento.objects.create(
        analise=analise,
        tipo=tipo,
        ator=ator if getattr(ator, 'is_authenticated', False) else None,
        dados=dados or {},
    )


def montar_snapshot_proposta(proposta: Proposta, condicao: dict[str, Any]) -> dict[str, Any]:
    return {
        'proposta_id': proposta.pk,
        'numero': proposta.numero,
        'cliente_id': proposta.cliente_id,
        'valor_total': format(_dec(proposta.valor_total), 'f'),
        'valor_frete': format(_dec(proposta.valor_frete), 'f'),
        'condicao_pagamento_texto': (proposta.condicao_pagamento_texto or '').strip(),
        'condicao': condicao,
        'data_proposta': proposta.data.isoformat() if proposta.data else None,
        'vendedor': (proposta.vendedor or '').strip(),
        'vendedor_ref_id': proposta.vendedor_ref_id,
        'data_corte': timezone.localdate().isoformat(),
    }


def condicao_atual_proposta(proposta: Proposta) -> dict[str, Any]:
    return normalizar_condicao_de_proposta(
        texto=proposta.condicao_pagamento_texto,
        dias_parcelas=list(proposta.dias_parcelas or []),
    )


@transaction.atomic
def solicitar_analise(proposta: Proposta, *, usuario, observacao_vendedor: str = '') -> AnaliseFinanceiraProposta:
    if not proposta.cliente_id:
        raise ValueError('Vincule um cliente cadastrado antes de solicitar a análise financeira.')
    valor = _dec(proposta.valor_total)
    if valor <= 0:
        raise ValueError('A proposta precisa ter valor total positivo para solicitar análise.')

    try:
        condicao = condicao_atual_proposta(proposta)
    except CondicaoAmbiguaError as exc:
        raise ValueError(str(exc)) from exc

    proposta = Proposta.objects.select_for_update().get(pk=proposta.pk)
    ativas = list(
        AnaliseFinanceiraProposta.objects.select_for_update().filter(
            proposta=proposta,
            status__in=(
                AnaliseFinanceiraProposta.Status.PENDENTE,
                AnaliseFinanceiraProposta.Status.EM_ANALISE,
            ),
        )
    )
    versao = (
        AnaliseFinanceiraProposta.objects.filter(proposta=proposta).aggregate(m=Max('versao'))['m'] or 0
    ) + 1

    indicadores = montar_indicadores(
        cliente=proposta.cliente,
        valor_proposta=valor,
        proposta_id=proposta.pk,
    )
    snapshot = montar_snapshot_proposta(proposta, condicao)

    nova = AnaliseFinanceiraProposta.objects.create(
        proposta=proposta,
        cliente_id=proposta.cliente_id,
        status=AnaliseFinanceiraProposta.Status.PENDENTE,
        versao=versao,
        solicitada_por=usuario if getattr(usuario, 'is_authenticated', False) else None,
        observacao_vendedor=(observacao_vendedor or '').strip(),
        valor_solicitado=valor,
        snapshot_proposta=snapshot,
        snapshot_indicadores=indicadores,
        condicao_solicitada=condicao,
    )

    for antiga in ativas:
        antiga.status = AnaliseFinanceiraProposta.Status.SUBSTITUIDA
        antiga.substituida_por = nova
        antiga.save(update_fields=['status', 'substituida_por', 'atualizada_em'])
        _registrar_evento(
            antiga,
            AnaliseFinanceiraPropostaEvento.Tipo.SUBSTITUIDA,
            usuario,
            {'nova_analise_id': nova.pk},
        )

    _registrar_evento(
        nova,
        AnaliseFinanceiraPropostaEvento.Tipo.SOLICITADA,
        usuario,
        {
            'valor_solicitado': format(valor, 'f'),
            'dias': condicao['dias'],
            'versao': versao,
            'schema_versao': indicadores.get('schema_versao'),
            'data_corte': indicadores.get('data_corte'),
            'qualidade': (indicadores.get('qualidade') or {}).get('status')
            or indicadores.get('qualidade_dados'),
            'indicadores_indisponiveis': len(
                (indicadores.get('qualidade') or {}).get('indisponiveis')
                or indicadores.get('dados_indisponiveis')
                or []
            ),
        },
    )
    return nova


@transaction.atomic
def iniciar_analise(analise: AnaliseFinanceiraProposta, *, usuario) -> AnaliseFinanceiraProposta:
    analise = AnaliseFinanceiraProposta.objects.select_for_update().get(pk=analise.pk)
    if analise.status != AnaliseFinanceiraProposta.Status.PENDENTE:
        raise ValueError('Somente análises pendentes podem ser assumidas.')
    analise.status = AnaliseFinanceiraProposta.Status.EM_ANALISE
    analise.iniciada_por = usuario if getattr(usuario, 'is_authenticated', False) else None
    analise.iniciada_em = timezone.now()
    analise.save(update_fields=['status', 'iniciada_por', 'iniciada_em', 'atualizada_em'])
    _registrar_evento(analise, AnaliseFinanceiraPropostaEvento.Tipo.INICIADA, usuario, {})
    return analise


def _exigir_decidivel(analise: AnaliseFinanceiraProposta):
    if analise.status not in (
        AnaliseFinanceiraProposta.Status.PENDENTE,
        AnaliseFinanceiraProposta.Status.EM_ANALISE,
    ):
        raise ValueError('Esta análise já foi decidida e não pode ser alterada.')


def _aplicar_decisao(
    analise: AnaliseFinanceiraProposta,
    *,
    usuario,
    status: str,
    evento_tipo: str,
    condicao_aprovada: dict | None,
    valor_maximo: Decimal | None,
    valida_ate: date | None,
    justificativa: str,
):
    analise = AnaliseFinanceiraProposta.objects.select_for_update().get(pk=analise.pk)
    _exigir_decidivel(analise)
    analise.status = status
    analise.decidida_por = usuario if getattr(usuario, 'is_authenticated', False) else None
    analise.decidida_em = timezone.now()
    analise.justificativa_decisao = (justificativa or '').strip()
    analise.condicao_aprovada = condicao_aprovada or {}
    analise.valor_maximo_aprovado = valor_maximo
    analise.valida_ate = valida_ate
    analise.save(
        update_fields=[
            'status',
            'decidida_por',
            'decidida_em',
            'justificativa_decisao',
            'condicao_aprovada',
            'valor_maximo_aprovado',
            'valida_ate',
            'atualizada_em',
        ]
    )
    _registrar_evento(
        analise,
        evento_tipo,
        usuario,
        {
            'status': status,
            'dias_aprovados': (condicao_aprovada or {}).get('dias'),
            'valor_maximo_aprovado': format(valor_maximo, 'f') if valor_maximo is not None else None,
            'valida_ate': valida_ate.isoformat() if valida_ate else None,
            'justificativa': analise.justificativa_decisao[:500],
        },
    )
    return analise


@transaction.atomic
def aprovar_como_solicitado(
    analise: AnaliseFinanceiraProposta,
    *,
    usuario,
    valida_ate: date | None = None,
    valor_maximo: Decimal | None = None,
) -> AnaliseFinanceiraProposta:
    validade = valida_ate or (timezone.localdate() + timedelta(days=VALIDADE_PADRAO_DIAS))
    valor = valor_maximo if valor_maximo is not None else analise.valor_solicitado
    return _aplicar_decisao(
        analise,
        usuario=usuario,
        status=AnaliseFinanceiraProposta.Status.APROVADA,
        evento_tipo=AnaliseFinanceiraPropostaEvento.Tipo.APROVADA,
        condicao_aprovada=dict(analise.condicao_solicitada or {}),
        valor_maximo=_dec(valor),
        valida_ate=validade,
        justificativa='',
    )


@transaction.atomic
def aprovar_com_ajuste(
    analise: AnaliseFinanceiraProposta,
    *,
    usuario,
    dias_aprovados: list[int],
    justificativa: str,
    valida_ate: date | None = None,
    valor_maximo: Decimal | None = None,
) -> AnaliseFinanceiraProposta:
    if not (justificativa or '').strip():
        raise ValueError('Justificativa é obrigatória para aprovação com ajuste.')
    dias = sorted(int(d) for d in dias_aprovados)
    if not condicao_aprovada_permitida_mvp(dias):
        raise ValueError('Condição aprovada inválida para o MVP.')
    from apps.comercial.analise_financeira_condicao import modalidade_de_dias, texto_exibicao_dias

    condicao = {
        'texto': texto_exibicao_dias(dias),
        'dias': dias,
        'quantidade_parcelas': len(dias),
        'modalidade': modalidade_de_dias(dias),
        'maior_prazo_dias': max(dias) if dias else 0,
    }
    validade = valida_ate or (timezone.localdate() + timedelta(days=VALIDADE_PADRAO_DIAS))
    valor = valor_maximo if valor_maximo is not None else analise.valor_solicitado
    return _aplicar_decisao(
        analise,
        usuario=usuario,
        status=AnaliseFinanceiraProposta.Status.APROVADA_COM_AJUSTE,
        evento_tipo=AnaliseFinanceiraPropostaEvento.Tipo.APROVADA_COM_AJUSTE,
        condicao_aprovada=condicao,
        valor_maximo=_dec(valor),
        valida_ate=validade,
        justificativa=justificativa,
    )


@transaction.atomic
def devolver_analise(analise: AnaliseFinanceiraProposta, *, usuario, justificativa: str):
    if not (justificativa or '').strip():
        raise ValueError('Justificativa é obrigatória para devolução.')
    return _aplicar_decisao(
        analise,
        usuario=usuario,
        status=AnaliseFinanceiraProposta.Status.DEVOLVIDA_PARA_AJUSTE,
        evento_tipo=AnaliseFinanceiraPropostaEvento.Tipo.DEVOLVIDA,
        condicao_aprovada={},
        valor_maximo=None,
        valida_ate=None,
        justificativa=justificativa,
    )


@transaction.atomic
def nao_aprovar(analise: AnaliseFinanceiraProposta, *, usuario, justificativa: str):
    if not (justificativa or '').strip():
        raise ValueError('Justificativa é obrigatória para não aprovação.')
    return _aplicar_decisao(
        analise,
        usuario=usuario,
        status=AnaliseFinanceiraProposta.Status.NAO_APROVADA,
        evento_tipo=AnaliseFinanceiraPropostaEvento.Tipo.NAO_APROVADA,
        condicao_aprovada={},
        valor_maximo=None,
        valida_ate=None,
        justificativa=justificativa,
    )


def ultima_aprovacao_candidata(proposta: Proposta) -> AnaliseFinanceiraProposta | None:
    return (
        AnaliseFinanceiraProposta.objects.filter(
            proposta=proposta,
            status__in=(
                AnaliseFinanceiraProposta.Status.APROVADA,
                AnaliseFinanceiraProposta.Status.APROVADA_COM_AJUSTE,
            ),
        )
        .order_by('-decidida_em', '-id')
        .first()
    )


def avaliar_aprovacao_para_proposta(
    proposta: Proposta,
    analise: AnaliseFinanceiraProposta | None = None,
) -> dict[str, Any]:
    """Retorna status de cobertura da liberação vs proposta atual."""
    try:
        condicao = condicao_atual_proposta(proposta)
        futura = possui_pagamento_futuro(condicao)
        a_vista = pagamento_integralmente_a_vista(condicao['dias'])
    except CondicaoAmbiguaError as exc:
        return {
            'exige_liberacao': True,
            'a_vista': False,
            'valida': False,
            'motivo_codigo': 'CONDICAO_AMBIGUA',
            'motivo': str(exc),
            'condicao_atual': None,
            'analise_id': None,
        }

    if a_vista and not futura:
        return {
            'exige_liberacao': False,
            'a_vista': True,
            'valida': True,
            'motivo_codigo': 'A_VISTA',
            'motivo': 'Pagamento integralmente à vista — liberação financeira não exigida neste MVP.',
            'condicao_atual': condicao,
            'analise_id': None,
        }

    analise = analise or ultima_aprovacao_candidata(proposta)
    if analise is None:
        ativa = AnaliseFinanceiraProposta.objects.filter(
            proposta=proposta,
            status__in=(
                AnaliseFinanceiraProposta.Status.PENDENTE,
                AnaliseFinanceiraProposta.Status.EM_ANALISE,
            ),
        ).first()
        if ativa is not None:
            return {
                'exige_liberacao': True,
                'a_vista': False,
                'valida': False,
                'motivo_codigo': 'ANALISE_PENDENTE',
                'motivo': MSG_ANALISE_PENDENTE,
                'condicao_atual': condicao,
                'analise_id': ativa.pk,
            }
        ultima = (
            AnaliseFinanceiraProposta.objects.filter(proposta=proposta)
            .order_by('-solicitada_em', '-id')
            .first()
        )
        if ultima is not None and ultima.status == AnaliseFinanceiraProposta.Status.NAO_APROVADA:
            return {
                'exige_liberacao': True,
                'a_vista': False,
                'valida': False,
                'motivo_codigo': 'ANALISE_NAO_APROVADA',
                'motivo': MSG_ANALISE_NAO_APROVADA,
                'condicao_atual': condicao,
                'analise_id': ultima.pk,
            }
        return {
            'exige_liberacao': True,
            'a_vista': False,
            'valida': False,
            'motivo_codigo': 'SEM_APROVACAO',
            'motivo': MSG_SEM_LIBERACAO,
            'condicao_atual': condicao,
            'analise_id': None,
        }

    if analise.cliente_id != proposta.cliente_id:
        return {
            'exige_liberacao': True,
            'a_vista': False,
            'valida': False,
            'motivo_codigo': 'CLIENTE_DIVERGENTE',
            'motivo': MSG_CLIENTE_DIVERGENTE,
            'condicao_atual': condicao,
            'analise_id': analise.pk,
        }

    if analise.valida_ate and analise.valida_ate < timezone.localdate():
        return {
            'exige_liberacao': True,
            'a_vista': False,
            'valida': False,
            'motivo_codigo': 'EXPIRADA',
            'motivo': MSG_EXPIRADA,
            'condicao_atual': condicao,
            'analise_id': analise.pk,
        }

    if not condicoes_iguais(condicao, analise.condicao_aprovada):
        return {
            'exige_liberacao': True,
            'a_vista': False,
            'valida': False,
            'motivo_codigo': 'CONDICAO_DIVERGENTE',
            'motivo': MSG_CONDICAO_DIVERGENTE,
            'condicao_atual': condicao,
            'analise_id': analise.pk,
        }

    valor_max = analise.valor_maximo_aprovado
    if valor_max is None or _dec(proposta.valor_total) > _dec(valor_max):
        return {
            'exige_liberacao': True,
            'a_vista': False,
            'valida': False,
            'motivo_codigo': 'VALOR_EXCEDE',
            'motivo': MSG_VALOR_EXCEDE,
            'condicao_atual': condicao,
            'analise_id': analise.pk,
        }

    return {
        'exige_liberacao': True,
        'a_vista': False,
        'valida': True,
        'motivo_codigo': 'APROVADA',
        'motivo': 'Liberação financeira válida.',
        'condicao_atual': condicao,
        'analise_id': analise.pk,
    }


def garantir_liberacao_para_conversao(proposta: Proposta) -> None:
    """Guard obrigatório antes de criar Pedido. Levanta LiberacaoFinanceiraBloqueio."""
    avaliacao = avaliar_aprovacao_para_proposta(proposta)
    if avaliacao.get('valida'):
        return
    code = avaliacao.get('motivo_codigo') or 'SEM_APROVACAO'
    detail = avaliacao.get('motivo') or MSG_SEM_LIBERACAO
    raise LiberacaoFinanceiraBloqueio(code, detail)


def situacao_proposta(proposta: Proposta) -> dict[str, Any]:
    avaliacao = avaliar_aprovacao_para_proposta(proposta)
    ultima = (
        AnaliseFinanceiraProposta.objects.filter(proposta=proposta)
        .order_by('-solicitada_em', '-id')
        .first()
    )
    ativa = AnaliseFinanceiraProposta.objects.filter(
        proposta=proposta,
        status__in=(
            AnaliseFinanceiraProposta.Status.PENDENTE,
            AnaliseFinanceiraProposta.Status.EM_ANALISE,
        ),
    ).first()
    return {
        'avaliacao': avaliacao,
        'ultima_analise_id': ultima.pk if ultima else None,
        'ultima_analise_status': ultima.status if ultima else None,
        'analise_ativa_id': ativa.pk if ativa else None,
        'reanalise_necessaria': bool(avaliacao.get('exige_liberacao') and not avaliacao.get('valida') and not avaliacao.get('a_vista')),
    }
