"""Filtros comuns do BI (período, empresa, status)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

MESES_PT = {
    1: 'Janeiro',
    2: 'Fevereiro',
    3: 'Março',
    4: 'Abril',
    5: 'Maio',
    6: 'Junho',
    7: 'Julho',
    8: 'Agosto',
    9: 'Setembro',
    10: 'Outubro',
    11: 'Novembro',
    12: 'Dezembro',
}


@dataclass
class DashboardFilters:
    data_inicio: date
    data_fim: date
    label: str
    empresa_id: int | None
    status: str | None
    periodo: str


def _format_data_br(d: date) -> str:
    return d.strftime('%d/%m/%Y')


def _format_mes_ano(d: date) -> str:
    return f'{MESES_PT[d.month]}/{d.year}'


def _mes_atual(hoje: date) -> tuple[date, date, str]:
    inicio = hoje.replace(day=1)
    if hoje.month == 12:
        fim_mes = hoje.replace(day=31)
    else:
        fim_mes = hoje.replace(month=hoje.month + 1, day=1) - timedelta(days=1)
    label = _format_mes_ano(hoje)
    return inicio, min(hoje, fim_mes), label


def _mes_anterior(hoje: date) -> tuple[date, date, str]:
    primeiro = hoje.replace(day=1)
    ultimo = primeiro - timedelta(days=1)
    inicio = ultimo.replace(day=1)
    label = _format_mes_ano(inicio)
    return inicio, ultimo, label


def parse_dashboard_filters(query_params) -> DashboardFilters:
    hoje = timezone.localdate()
    periodo = (query_params.get('periodo') or 'mes_atual').strip().lower()
    data_inicio_raw = (query_params.get('data_inicio') or '').strip()
    data_fim_raw = (query_params.get('data_fim') or '').strip()
    empresa_raw = (query_params.get('empresa_id') or '').strip()
    status = (query_params.get('status') or '').strip() or None

    empresa_id: int | None = None
    if empresa_raw:
        try:
            empresa_id = int(empresa_raw)
        except ValueError:
            empresa_id = None

    if periodo == 'hoje':
        data_inicio = data_fim = hoje
        label = 'Hoje'
    elif periodo == 'ultimos_7_dias':
        data_inicio = hoje - timedelta(days=6)
        data_fim = hoje
        label = 'Últimos 7 dias'
    elif periodo == 'ultimos_30_dias':
        data_inicio = hoje - timedelta(days=29)
        data_fim = hoje
        label = 'Últimos 30 dias'
    elif periodo == 'mes_anterior':
        data_inicio, data_fim, label = _mes_anterior(hoje)
    elif periodo == 'ano_atual':
        data_inicio = hoje.replace(month=1, day=1)
        data_fim = hoje
        label = f'Ano {hoje.year}'
    elif periodo == 'personalizado' and data_inicio_raw and data_fim_raw:
        data_inicio = date.fromisoformat(data_inicio_raw)
        data_fim = date.fromisoformat(data_fim_raw)
        label = f'{_format_data_br(data_inicio)} a {_format_data_br(data_fim)}'
    elif data_inicio_raw and data_fim_raw:
        data_inicio = date.fromisoformat(data_inicio_raw)
        data_fim = date.fromisoformat(data_fim_raw)
        label = f'{_format_data_br(data_inicio)} a {_format_data_br(data_fim)}'
        periodo = 'personalizado'
    else:
        data_inicio, data_fim, label = _mes_atual(hoje)
        periodo = 'mes_atual'

    if data_fim < data_inicio:
        data_inicio, data_fim = data_fim, data_inicio

    return DashboardFilters(
        data_inicio=data_inicio,
        data_fim=data_fim,
        label=label,
        empresa_id=empresa_id,
        status=status,
        periodo=periodo,
    )


def periodo_dict(f: DashboardFilters) -> dict:
    return {
        'data_inicio': f.data_inicio.isoformat(),
        'data_fim': f.data_fim.isoformat(),
        'label': f.label,
        'periodo': f.periodo,
        'empresa_id': f.empresa_id,
        'status': f.status,
    }
