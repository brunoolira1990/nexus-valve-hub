"""Data de entrada operacional/fiscal da NF-e Entrada (informada pelo usuário na conferência)."""

from __future__ import annotations

from datetime import date, datetime, time

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.fiscal.models import NFeEntradaConferencia, NFeEntradaHistoricaImportada

MSG_DATA_ENTRADA_OBRIGATORIA = (
    'Informe a data de entrada da NF-e antes de finalizar (preparar estoque, aplicar recebimento ou baixar pedido).'
)
MSG_DATA_ENTRADA_INVALIDA = 'Data de entrada inválida.'


def parse_data_entrada(value: str | date | None) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def resolver_data_entrada_conferencia(conferencia: NFeEntradaConferencia) -> date:
    """Retorna data de entrada informada pelo usuário ou levanta ValueError."""
    data = conferencia.data_entrada
    if not data:
        raise ValueError(MSG_DATA_ENTRADA_OBRIGATORIA)
    return data


def datetime_operacional_data_entrada(data_entrada: date) -> datetime:
    """Combina data de entrada informada com horário local para registros operacionais."""
    tz = timezone.get_current_timezone()
    naive = datetime.combine(data_entrada, time(12, 0))
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, tz)
    return naive.astimezone(tz)


def data_competencia_entrada_nf(nf: NFeEntradaHistoricaImportada) -> date:
    """
    Data de competência da entrada para apuração/relatórios.
    Usa data_entrada da conferência quando informada; caso contrário dh_emissao (legado/documental).
    """
    try:
        conf = nf.conferencia
        if conf and conf.data_entrada:
            return conf.data_entrada
    except NFeEntradaConferencia.DoesNotExist:
        pass
    if nf.dh_emissao:
        return nf.dh_emissao.date()
    return timezone.localdate()


def filtrar_entrada_historica_por_competencia(
    qs: QuerySet[NFeEntradaHistoricaImportada],
    data_inicio: date,
    data_fim: date,
) -> QuerySet[NFeEntradaHistoricaImportada]:
    """
    Filtra NF-e entrada histórica pelo período de competência operacional.
    Prioriza conferencia.data_entrada; sem data informada, usa dh_emissao (notas ainda não finalizadas).
    """
    return qs.filter(
        Q(conferencia__data_entrada__gte=data_inicio, conferencia__data_entrada__lte=data_fim)
        | Q(
            Q(conferencia__data_entrada__isnull=True) | Q(conferencia__isnull=True),
            dh_emissao__date__gte=data_inicio,
            dh_emissao__date__lte=data_fim,
        ),
    )
