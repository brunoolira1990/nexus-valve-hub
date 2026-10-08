"""Resumo operacional do Financeiro — ERP 4.0.14.5."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.financeiro.filtragem import filtro_origem_fiscal_cancelada_q, resolver_periodo
from apps.financeiro.models import BaixaFinanceira, CreditoFinanceiro, TituloFinanceiro
from apps.financeiro.status import CENTAVO

_STATUS_FECHADO = frozenset(
    {
        TituloFinanceiro.Status.RECEBIDO,
        TituloFinanceiro.Status.PAGO,
        TituloFinanceiro.Status.CANCELADO,
    },
)


def _hoje() -> date:
    return timezone.localdate()


def _metrica(qs, campo_valor: str = 'valor_aberto') -> dict[str, Any]:
    agg = qs.aggregate(total=Sum(campo_valor), quantidade=Count('id'))
    total = agg['total'] or Decimal('0')
    return {'valor': str(total.quantize(Decimal('0.01'))), 'quantidade': agg['quantidade'] or 0}


def _base_aberto(tipo: str):
    return TituloFinanceiro.objects.filter(
        tipo=tipo,
        cancelado=False,
        valor_aberto__gt=CENTAVO,
    ).exclude(status__in=_STATUS_FECHADO)


def _resumo_tipo(tipo: str, hoje: date, periodo_ini: date, periodo_fim: date) -> dict[str, Any]:
    base = _base_aberto(tipo)
    hoje_qs = base.filter(data_vencimento=hoje)
    vencido_qs = base.filter(data_vencimento__lt=hoje)
    prox7_qs = base.filter(
        data_vencimento__gte=hoje,
        data_vencimento__lte=hoje + timedelta(days=7),
    )
    em_aberto_qs = base

    baixa_tipo = BaixaFinanceira.objects.filter(
        titulo__tipo=tipo,
        estornada=False,
        data_baixa__gte=periodo_ini,
        data_baixa__lte=periodo_fim,
    )
    periodo_label = 'recebido_periodo' if tipo == TituloFinanceiro.Tipo.RECEBER else 'pago_periodo'
    periodo_agg = baixa_tipo.aggregate(total=Sum('valor'), quantidade=Count('id', distinct=True))
    periodo_valor = periodo_agg['total'] or Decimal('0')

    return {
        'hoje': _metrica(hoje_qs),
        'vencido': _metrica(vencido_qs),
        'proximos_7_dias': _metrica(prox7_qs),
        'em_aberto': _metrica(em_aberto_qs),
        periodo_label: {
            'valor': str(periodo_valor.quantize(Decimal('0.01'))),
            'quantidade': periodo_agg['quantidade'] or 0,
        },
    }


def _montar_alertas(hoje: date) -> list[dict[str, Any]]:
    alertas: list[dict[str, Any]] = []
    rec_venc = _base_aberto(TituloFinanceiro.Tipo.RECEBER).filter(data_vencimento__lt=hoje)
    pag_venc = _base_aberto(TituloFinanceiro.Tipo.PAGAR).filter(data_vencimento__lt=hoje)
    qtd_vencidos = rec_venc.count() + pag_venc.count()
    if qtd_vencidos:
        alertas.append(
            {
                'codigo': 'titulos_vencidos',
                'mensagem': 'Existem títulos vencidos que precisam de atenção.',
                'quantidade': qtd_vencidos,
                'acao': 'ver_vencidos',
            },
        )

    rec_hoje = _base_aberto(TituloFinanceiro.Tipo.RECEBER).filter(data_vencimento=hoje).count()
    pag_hoje = _base_aberto(TituloFinanceiro.Tipo.PAGAR).filter(data_vencimento=hoje).count()
    qtd_hoje = rec_hoje + pag_hoje
    if qtd_hoje:
        alertas.append(
            {
                'codigo': 'vencendo_hoje',
                'mensagem': 'Existem títulos com vencimento hoje.',
                'quantidade': qtd_hoje,
                'acao': 'ver_hoje',
            },
        )

    origem_q = filtro_origem_fiscal_cancelada_q()
    qtd_origem = TituloFinanceiro.objects.filter(origem_q, cancelado=False).count()
    if qtd_origem:
        alertas.append(
            {
                'codigo': 'origem_fiscal_cancelada',
                'mensagem': 'Existem títulos vinculados a NF-e cancelada. Revise antes de baixar.',
                'quantidade': qtd_origem,
                'acao': 'ver_origem_cancelada',
            },
        )

    sem_cat = TituloFinanceiro.objects.filter(
        categoria__isnull=True,
        cancelado=False,
        valor_aberto__gt=CENTAVO,
    ).exclude(status__in=_STATUS_FECHADO).count()
    if sem_cat:
        alertas.append(
            {
                'codigo': 'sem_categoria',
                'mensagem': 'Existem títulos sem categoria financeira.',
                'quantidade': sem_cat,
                'acao': 'ver_sem_categoria',
            },
        )

    sem_conta = TituloFinanceiro.objects.filter(
        conta_financeira_prevista__isnull=True,
        cancelado=False,
        valor_aberto__gt=CENTAVO,
    ).exclude(status__in=_STATUS_FECHADO).count()
    if sem_conta:
        alertas.append(
            {
                'codigo': 'sem_conta_prevista',
                'mensagem': 'Existem títulos sem conta/caixa prevista.',
                'quantidade': sem_conta,
                'acao': 'ver_sem_conta',
            },
        )

    creditos_qs = CreditoFinanceiro.objects.filter(cancelado=False, saldo__gt=CENTAVO).filter(
        Q(status=CreditoFinanceiro.Status.DISPONIVEL)
        | Q(status=CreditoFinanceiro.Status.PARCIALMENTE_UTILIZADO),
    )
    qtd_cred = creditos_qs.count()
    if qtd_cred:
        alertas.append(
            {
                'codigo': 'creditos_disponiveis',
                'mensagem': 'Existem créditos disponíveis para aplicar.',
                'quantidade': qtd_cred,
                'acao': 'ver_creditos',
            },
        )

    return alertas


def _resumo_por_conta(hoje: date) -> list[dict[str, Any]]:
    from apps.financeiro.models import ContaFinanceira

    linhas: list[dict[str, Any]] = []
    for conta in ContaFinanceira.objects.filter(ativo=True).order_by('nome'):
        rec = _base_aberto(TituloFinanceiro.Tipo.RECEBER).filter(conta_financeira_prevista=conta)
        pag = _base_aberto(TituloFinanceiro.Tipo.PAGAR).filter(conta_financeira_prevista=conta)
        v_rec = rec.aggregate(t=Sum('valor_aberto'))['t'] or Decimal('0')
        v_pag = pag.aggregate(t=Sum('valor_aberto'))['t'] or Decimal('0')
        if v_rec <= CENTAVO and v_pag <= CENTAVO:
            continue
        saldo = v_rec - v_pag
        linhas.append(
            {
                'conta_id': conta.id,
                'conta_nome': conta.nome,
                'a_receber_em_aberto': str(v_rec.quantize(Decimal('0.01'))),
                'a_pagar_em_aberto': str(v_pag.quantize(Decimal('0.01'))),
                'saldo_previsto': str(saldo.quantize(Decimal('0.01'))),
            },
        )
    return linhas


def _resumo_por_categoria(periodo_ini: date, periodo_fim: date) -> dict[str, list[dict[str, Any]]]:
    receitas: list[dict[str, Any]] = []
    despesas: list[dict[str, Any]] = []

    for tipo_titulo, destino in (
        (TituloFinanceiro.Tipo.RECEBER, receitas),
        (TituloFinanceiro.Tipo.PAGAR, despesas),
    ):
        qs = TituloFinanceiro.objects.filter(
            tipo=tipo_titulo,
            cancelado=False,
            data_emissao__gte=periodo_ini,
            data_emissao__lte=periodo_fim,
        ).exclude(status=TituloFinanceiro.Status.CANCELADO)
        rows = (
            qs.values('categoria_id', 'categoria__nome')
            .annotate(total=Sum('valor_original'))
            .order_by('-total')
        )
        for row in rows[:12]:
            nome = row['categoria__nome'] or 'Sem categoria'
            total = row['total'] or Decimal('0')
            if total <= CENTAVO:
                continue
            destino.append(
                {
                    'categoria_id': row['categoria_id'],
                    'categoria_nome': nome,
                    'valor': str(total.quantize(Decimal('0.01'))),
                },
            )

    return {'receitas': receitas, 'despesas': despesas}


def _resumo_creditos() -> dict[str, Any]:
    base = CreditoFinanceiro.objects.filter(cancelado=False, saldo__gt=CENTAVO).filter(
        Q(status=CreditoFinanceiro.Status.DISPONIVEL)
        | Q(status=CreditoFinanceiro.Status.PARCIALMENTE_UTILIZADO),
    )

    def _bloco(tipo: str) -> dict[str, Any]:
        qs = base.filter(tipo=tipo)
        agg = qs.aggregate(total=Sum('saldo'), quantidade=Count('id'))
        return {
            'quantidade': agg['quantidade'] or 0,
            'valor_disponivel': str((agg['total'] or Decimal('0')).quantize(Decimal('0.01'))),
        }

    clientes = _bloco(CreditoFinanceiro.Tipo.CLIENTE)
    fornecedores = _bloco(CreditoFinanceiro.Tipo.FORNECEDOR)
    total = Decimal(clientes['valor_disponivel']) + Decimal(fornecedores['valor_disponivel'])
    return {
        'clientes': clientes,
        'fornecedores': fornecedores,
        'total_disponivel': str(total.quantize(Decimal('0.01'))),
    }


def montar_resumo_financeiro(
    *,
    periodo: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> dict[str, Any]:
    hoje = _hoje()
    periodo_ini, periodo_fim = resolver_periodo(periodo, data_inicio=data_inicio, data_fim=data_fim)

    receber = _resumo_tipo(TituloFinanceiro.Tipo.RECEBER, hoje, periodo_ini, periodo_fim)
    pagar = _resumo_tipo(TituloFinanceiro.Tipo.PAGAR, hoje, periodo_ini, periodo_fim)

    rec_aberto = Decimal(receber['em_aberto']['valor'])
    pag_aberto = Decimal(pagar['em_aberto']['valor'])
    rec_7 = Decimal(receber['proximos_7_dias']['valor'])
    pag_7 = Decimal(pagar['proximos_7_dias']['valor'])

    return {
        'periodo': (periodo or 'mes').strip().lower(),
        'data_inicio': periodo_ini.isoformat(),
        'data_fim': periodo_fim.isoformat(),
        'referencia_data': hoje.isoformat(),
        'receber': receber,
        'pagar': pagar,
        'saldo_previsto': {
            'em_aberto': str((rec_aberto - pag_aberto).quantize(Decimal('0.01'))),
            'proximos_7_dias': str((rec_7 - pag_7).quantize(Decimal('0.01'))),
        },
        'alertas': _montar_alertas(hoje),
        'por_conta': _resumo_por_conta(hoje),
        'por_categoria': _resumo_por_categoria(periodo_ini, periodo_fim),
        'creditos': _resumo_creditos(),
        # Compatibilidade com UI anterior
        'a_receber_hoje': receber['hoje']['valor'],
        'a_receber_vencido': receber['vencido']['valor'],
        'a_pagar_hoje': pagar['hoje']['valor'],
        'a_pagar_vencido': pagar['vencido']['valor'],
        'recebido_mes': receber['recebido_periodo']['valor'],
        'pago_mes': pagar['pago_periodo']['valor'],
    }
