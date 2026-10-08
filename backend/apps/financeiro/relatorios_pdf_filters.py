"""Rótulos de filtros para PDF de relatórios financeiros."""

from __future__ import annotations

from apps.financeiro.filtragem import resolver_periodo
from apps.financeiro.models import TituloFinanceiro
from apps.relatorios.definitions import ReportFilterLine


def _sim_nao(params, key: str) -> str:
    v = (params.get(key) or '').strip().lower()
    return 'Sim' if v in ('1', 'true', 'sim', 'yes') else 'Não'


def _periodo_label(params, *, padrao: str = 'mes') -> str:
    periodo = (params.get('periodo') or padrao).strip().lower()
    ini, fim = resolver_periodo(
        periodo,
        data_inicio=params.get('data_inicio') or params.get('vencimento_de'),
        data_fim=params.get('data_fim') or params.get('vencimento_ate'),
    )
    labels = {
        'hoje': 'Hoje',
        'semana': 'Esta semana',
        'mes': 'Este mês',
        'proximos_7': 'Próximos 7 dias',
        'proximos_15': 'Próximos 15 dias',
        'proximos_30': 'Próximos 30 dias',
        'proximo_mes': 'Próximo mês',
        'personalizado': 'Personalizado',
    }
    nome = labels.get(periodo, periodo)
    return f'{nome} ({ini.strftime("%d/%m/%Y")} a {fim.strftime("%d/%m/%Y")})'


def filtros_relatorio_financeiro(params) -> list[ReportFilterLine]:
    lines: list[ReportFilterLine] = []
    venc = (params.get('vencimento') or '').strip().lower()
    if venc:
        venc_map = {
            'hoje': 'Vence hoje',
            'vencidos': 'Vencidos',
            'proximos_7': 'Vence nos próximos 7 dias',
            'proximos_30': 'Vence nos próximos 30 dias',
            'mes': 'Vence neste mês',
            'personalizado': 'Vencimento personalizado',
        }
        lines.append(ReportFilterLine('Vencimento', venc_map.get(venc, venc)))

    st = (params.get('status') or '').strip()
    if st:
        st_map = {
            'EM_ABERTO': 'Em aberto',
            'VENCIDO': 'Vencido',
            'PARCIALMENTE_RECEBIDO': 'Parcialmente recebido',
            'RECEBIDO': 'Recebido',
            'PARCIALMENTE_PAGO': 'Parcialmente pago',
            'PAGO': 'Pago',
            'CANCELADO': 'Cancelado',
        }
        lines.append(ReportFilterLine('Status', st_map.get(st, st)))

    origem = (params.get('origem_tipo') or params.get('origem') or '').strip()
    if origem:
        lines.append(ReportFilterLine('Origem', origem.replace('_', ' ')))

    if params.get('cliente') or params.get('cliente_id'):
        lines.append(
            ReportFilterLine(
                'Cliente',
                str(params.get('cliente') or params.get('cliente_id')),
            ),
        )
    if params.get('fornecedor') or params.get('fornecedor_id'):
        lines.append(
            ReportFilterLine(
                'Fornecedor',
                str(params.get('fornecedor') or params.get('fornecedor_id')),
            ),
        )
    if params.get('categoria'):
        lines.append(ReportFilterLine('Categoria', str(params['categoria'])))
    if params.get('centro_custo'):
        lines.append(ReportFilterLine('Centro de custo', str(params['centro_custo'])))
    conta = params.get('conta_prevista') or params.get('conta_financeira_prevista')
    if conta:
        lines.append(ReportFilterLine('Conta/Caixa prevista', str(conta)))
    if params.get('tipo_lancamento'):
        lines.append(ReportFilterLine('Tipo de lançamento', str(params['tipo_lancamento'])))
    if params.get('agrupamento'):
        lines.append(ReportFilterLine('Agrupamento', str(params['agrupamento'])))
    if params.get('periodo') or params.get('periodo_baixa'):
        padrao = 'proximos_30' if (params.get('periodo') or '') == 'proximos_30' else 'mes'
        lines.append(ReportFilterLine('Período', _periodo_label(params, padrao=padrao)))
    elif params.get('data_inicio') or params.get('data_fim'):
        lines.append(ReportFilterLine('Período', _periodo_label(params)))

    if params.get('origem_fiscal_cancelada') in ('1', 'true', 'sim'):
        lines.append(ReportFilterLine('Origem fiscal cancelada', 'Sim'))

    lines.append(ReportFilterLine('Incluir quitados', _sim_nao(params, 'incluir_quitados')))
    lines.append(ReportFilterLine('Incluir cancelados', _sim_nao(params, 'incluir_cancelados')))
    if params.get('incluir_sem_saldo') is not None:
        lines.append(ReportFilterLine('Incluir registros sem saldo', _sim_nao(params, 'incluir_sem_saldo')))

    return lines
