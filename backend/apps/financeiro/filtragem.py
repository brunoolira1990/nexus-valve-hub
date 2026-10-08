"""Filtros operacionais de títulos — ERP 4.0.14.5."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.financeiro.models import TituloFinanceiro
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


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def resolver_periodo(
    periodo: str | None,
    *,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> tuple[date, date]:
    hoje = _hoje()
    periodo = (periodo or 'mes').strip().lower()
    if periodo == 'personalizado':
        ini = _parse_date(data_inicio) or hoje.replace(day=1)
        fim = _parse_date(data_fim) or hoje
        return ini, fim
    if periodo == 'hoje':
        return hoje, hoje
    if periodo == 'semana':
        ini = hoje - timedelta(days=hoje.weekday())
        return ini, ini + timedelta(days=6)
    if periodo == 'proximos_7':
        return hoje, hoje + timedelta(days=7)
    if periodo == 'proximos_30':
        return hoje, hoje + timedelta(days=30)
    if periodo == 'proximos_15':
        return hoje, hoje + timedelta(days=15)
    if periodo == 'proximo_mes':
        if hoje.month == 12:
            ini = date(hoje.year + 1, 1, 1)
            fim = date(hoje.year + 1, 2, 1) - timedelta(days=1)
        else:
            ini = date(hoje.year, hoje.month + 1, 1)
            if hoje.month == 11:
                fim = date(hoje.year + 1, 1, 1) - timedelta(days=1)
            else:
                fim = date(hoje.year, hoje.month + 2, 1) - timedelta(days=1)
        return ini, fim
    # mes (padrão)
    ini = hoje.replace(day=1)
    if hoje.month == 12:
        fim = date(hoje.year + 1, 1, 1) - timedelta(days=1)
    else:
        fim = date(hoje.year, hoje.month + 1, 1) - timedelta(days=1)
    return ini, fim


def _ids_nfe_saida_canceladas() -> list[int]:
    from apps.fiscal.models import NFeSaida
    from apps.fiscal.nfe_saida_financeiro import nf_cancelada

    ids: list[int] = []
    for pk, status, sefaz in NFeSaida.objects.values_list('pk', 'status', 'status_emissao_sefaz'):
        nf = NFeSaida(pk=pk, status=status, status_emissao_sefaz=sefaz)
        if nf_cancelada(nf):
            ids.append(pk)
    return ids


def _ids_nfe_entrada_canceladas() -> list[int]:
    from apps.fiscal.models import NFeEntradaHistoricaImportada
    from apps.fiscal.nfe_entrada_financeiro import nfe_entrada_cancelada

    ids: list[int] = []
    for nf in NFeEntradaHistoricaImportada.objects.select_related('conferencia').iterator():
        conf = getattr(nf, 'conferencia', None)
        if nfe_entrada_cancelada(nf, conf):
            ids.append(nf.pk)
    return ids


def filtro_origem_fiscal_cancelada_q() -> Q:
    saida_ids = _ids_nfe_saida_canceladas()
    entrada_ids = _ids_nfe_entrada_canceladas()
    parts = Q()
    if saida_ids:
        parts |= Q(origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA, origem_id__in=saida_ids)
    if entrada_ids:
        parts |= Q(origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA, origem_id__in=entrada_ids)
    return parts if (saida_ids or entrada_ids) else Q(pk__in=[])


def aplicar_filtros_titulo(qs: QuerySet, params) -> QuerySet:
    """Aplica filtros de query string sem alterar regras de baixa/estorno."""
    hoje = _hoje()

    st = (params.get('status') or '').strip()
    if st:
        if st == 'VENCIDO':
            qs = qs.filter(
                cancelado=False,
                valor_aberto__gt=CENTAVO,
                data_vencimento__lt=hoje,
            ).exclude(status__in=_STATUS_FECHADO)
        else:
            qs = qs.filter(status=st)

    venc = (params.get('vencimento') or '').strip().lower()
    if venc == 'hoje':
        qs = qs.filter(data_vencimento=hoje, cancelado=False, valor_aberto__gt=CENTAVO)
    elif venc == 'vencidos':
        qs = qs.filter(data_vencimento__lt=hoje, cancelado=False, valor_aberto__gt=CENTAVO)
    elif venc == 'proximos_7':
        qs = qs.filter(
            data_vencimento__gte=hoje,
            data_vencimento__lte=hoje + timedelta(days=7),
            cancelado=False,
            valor_aberto__gt=CENTAVO,
        )
    elif venc == 'proximos_30':
        qs = qs.filter(
            data_vencimento__gte=hoje,
            data_vencimento__lte=hoje + timedelta(days=30),
            cancelado=False,
            valor_aberto__gt=CENTAVO,
        )
    elif venc == 'mes':
        ini, fim = resolver_periodo('mes')
        qs = qs.filter(data_vencimento__gte=ini, data_vencimento__lte=fim)
    elif venc == 'personalizado':
        ini = _parse_date(params.get('vencimento_de') or params.get('data_inicio'))
        fim = _parse_date(params.get('vencimento_ate') or params.get('data_fim'))
        if ini:
            qs = qs.filter(data_vencimento__gte=ini)
        if fim:
            qs = qs.filter(data_vencimento__lte=fim)

    origem = (params.get('origem_tipo') or params.get('origem') or '').strip().upper()
    if origem:
        qs = qs.filter(origem_tipo=origem)

    tipo_lanc = (params.get('tipo_lancamento') or '').strip()
    if tipo_lanc:
        qs = qs.filter(tipo_lancamento=tipo_lanc)

    cat = params.get('categoria')
    if cat:
        qs = qs.filter(categoria_id=int(cat))

    cc = params.get('centro_custo')
    if cc:
        qs = qs.filter(centro_custo_id=int(cc))

    conta = params.get('conta_financeira_prevista') or params.get('conta_prevista')
    if conta:
        qs = qs.filter(conta_financeira_prevista_id=int(conta))

    if params.get('com_saldo_aberto') in ('1', 'true', 'True', 'sim'):
        qs = qs.filter(cancelado=False, valor_aberto__gt=CENTAVO)

    if params.get('origem_fiscal_cancelada') in ('1', 'true', 'True', 'sim'):
        qs = qs.filter(filtro_origem_fiscal_cancelada_q())

    if params.get('sem_categoria') in ('1', 'true', 'True', 'sim'):
        qs = qs.filter(categoria__isnull=True, cancelado=False, valor_aberto__gt=CENTAVO)

    if params.get('sem_conta_prevista') in ('1', 'true', 'True', 'sim'):
        qs = qs.filter(
            conta_financeira_prevista__isnull=True,
            cancelado=False,
            valor_aberto__gt=CENTAVO,
        )

    periodo_emissao = (params.get('periodo_emissao') or params.get('emissao') or '').strip().lower()
    if periodo_emissao:
        ini, fim = resolver_periodo(
            periodo_emissao,
            data_inicio=params.get('emissao_de') or params.get('emissao_inicio'),
            data_fim=params.get('emissao_ate') or params.get('emissao_fim'),
        )
        qs = qs.filter(data_emissao__gte=ini, data_emissao__lte=fim)
    else:
        emissao_de = _parse_date(params.get('emissao_de') or params.get('emissao_inicio'))
        emissao_ate = _parse_date(params.get('emissao_ate') or params.get('emissao_fim'))
        if emissao_de:
            qs = qs.filter(data_emissao__gte=emissao_de)
        if emissao_ate:
            qs = qs.filter(data_emissao__lte=emissao_ate)

    cliente_id = (params.get('cliente') or params.get('cliente_id') or '').strip()
    if cliente_id:
        try:
            qs = qs.filter(cliente_id=int(cliente_id))
        except ValueError:
            pass

    fornecedor_id = (params.get('fornecedor') or params.get('fornecedor_id') or '').strip()
    if fornecedor_id:
        try:
            qs = qs.filter(fornecedor_id=int(fornecedor_id))
        except ValueError:
            pass

    search = (params.get('search') or '').strip()
    if search:
        from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

        qs = filtrar_queryset_por_numeros_documento(
            qs,
            search,
            'numero',
            'origem_numero',
            'documento_origem',
            q_extra=(
                Q(descricao__icontains=search)
                | Q(origem_descricao__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(cliente__nome_fantasia__icontains=search)
                | Q(cliente__cnpj__icontains=search)
                | Q(fornecedor__razao_social__icontains=search)
                | Q(fornecedor__nome_fantasia__icontains=search)
                | Q(fornecedor__cnpj__icontains=search)
            ),
        )

    return qs


def param_flag(params, key: str) -> bool:
    return (params.get(key) or '').strip().lower() in ('1', 'true', 'sim', 'yes')


def aplicar_filtros_exibicao_relatorio(qs: QuerySet, params, *, tipo: str) -> QuerySet:
    """ERP 4.0.14.6.1 — prioriza títulos ativos; histórico só com flags explícitas."""
    incluir_cancelados = param_flag(params, 'incluir_cancelados')
    incluir_quitados = param_flag(params, 'incluir_quitados')

    if not incluir_cancelados:
        qs = qs.filter(cancelado=False)

    if not incluir_quitados:
        quitado = (
            TituloFinanceiro.Status.RECEBIDO
            if tipo == TituloFinanceiro.Tipo.RECEBER
            else TituloFinanceiro.Status.PAGO
        )
        qs = qs.exclude(status=quitado)
        visiveis = (
            Q(valor_aberto__gt=CENTAVO)
            | Q(
                status__in=(
                    TituloFinanceiro.Status.PARCIALMENTE_RECEBIDO,
                    TituloFinanceiro.Status.PARCIALMENTE_PAGO,
                ),
            )
        )
        if incluir_cancelados:
            visiveis |= Q(cancelado=True)
        qs = qs.filter(visiveis)

    return qs


def queryset_metricas_ativas(qs: QuerySet) -> QuerySet:
    """Títulos com saldo em aberto não cancelados — usado em cards de aberto/vencido."""
    return qs.filter(cancelado=False, valor_aberto__gt=CENTAVO)
