"""Filtros de listagem da base NF-e Entrada importada (histórica)."""

from __future__ import annotations

from datetime import date

from django.db.models import Q, QuerySet
from django.http import QueryDict

from apps.fiscal.models import NFeEntradaHistoricaImportada
from apps.fiscal.nfe_entrada_data_entrada import filtrar_entrada_historica_por_competencia
from apps.fiscal.nfe_historica_periodo import PeriodoInvalido, _parse_date, resolver_periodo

STATUS_CONFERENCIA_SEM = 'sem_conferencia'
STATUS_CONFERENCIA_PENDENTE = 'pendente'
STATUS_CONFERENCIA_FINALIZADA = 'finalizada'
STATUS_CONFERENCIA_ESTOQUE = 'estoque_aplicado'

STATUS_CONFERENCIA_VALIDOS = frozenset({
    STATUS_CONFERENCIA_SEM,
    STATUS_CONFERENCIA_PENDENTE,
    STATUS_CONFERENCIA_FINALIZADA,
    STATUS_CONFERENCIA_ESTOQUE,
})


def normalizar_tipo_data(value: str | None) -> str:
    tipo = (value or 'emissao').strip().lower()
    if tipo not in ('emissao', 'entrada'):
        raise PeriodoInvalido(f'tipo_data inválido: {value!r}. Use emissao ou entrada.')
    return tipo


def intervalo_datas_listagem(params: QueryDict) -> tuple[date | None, date | None] | None:
    """Retorna (início, fim) parcial ou completo; None se não houver filtro de período."""
    if params.get('mes') or params.get('trimestre'):
        di, df, _ = resolver_periodo(params)
        return di, df
    di_s = (params.get('data_inicio') or '').strip()
    df_s = (params.get('data_fim') or '').strip()
    if not di_s and not df_s:
        return None
    di = _parse_date(di_s) if di_s else None
    df = _parse_date(df_s) if df_s else None
    if di and df and df < di:
        raise PeriodoInvalido('data_fim não pode ser anterior a data_inicio.')
    return di, df


def aplicar_busca_textual(
    qs: QuerySet[NFeEntradaHistoricaImportada],
    search: str,
) -> QuerySet[NFeEntradaHistoricaImportada]:
    termo = (search or '').strip()
    if not termo:
        return qs
    return qs.filter(
        Q(chave_acesso__icontains=termo)
        | Q(numero__icontains=termo)
        | Q(fornecedor_emitente__razao_social__icontains=termo)
        | Q(emit_json__xNome__icontains=termo),
    )


def aplicar_filtro_periodo(
    qs: QuerySet[NFeEntradaHistoricaImportada],
    *,
    data_inicio: date | None,
    data_fim: date | None,
    tipo_data: str,
) -> QuerySet[NFeEntradaHistoricaImportada]:
    if not data_inicio and not data_fim:
        return qs
    if tipo_data == 'entrada':
        if data_inicio and data_fim:
            return filtrar_entrada_historica_por_competencia(qs, data_inicio, data_fim)
        if data_inicio:
            return qs.filter(conferencia__data_entrada__gte=data_inicio)
        return qs.filter(conferencia__data_entrada__lte=data_fim)
    if data_inicio:
        qs = qs.filter(dh_emissao__date__gte=data_inicio)
    if data_fim:
        qs = qs.filter(dh_emissao__date__lte=data_fim)
    return qs


def aplicar_filtro_status_conferencia(
    qs: QuerySet[NFeEntradaHistoricaImportada],
    status: str | None,
) -> QuerySet[NFeEntradaHistoricaImportada]:
    st = (status or '').strip().lower()
    if not st:
        return qs
    if st not in STATUS_CONFERENCIA_VALIDOS:
        raise PeriodoInvalido(
            f'status_conferencia inválido: {status!r}. '
            f'Valores: {", ".join(sorted(STATUS_CONFERENCIA_VALIDOS))}.',
        )
    if st == STATUS_CONFERENCIA_SEM:
        return qs.filter(conferencia__isnull=True)
    if st == STATUS_CONFERENCIA_PENDENTE:
        return qs.filter(
            conferencia__isnull=False,
            conferencia__preparado_em__isnull=True,
            conferencia__estoque_aplicado_em__isnull=True,
        )
    if st == STATUS_CONFERENCIA_FINALIZADA:
        return qs.filter(
            conferencia__preparado_em__isnull=False,
            conferencia__estoque_aplicado_em__isnull=True,
        )
    return qs.filter(conferencia__estoque_aplicado_em__isnull=False)
