"""
PDF dos relatórios financeiros operacionais — ERP 4.0.14.7.

O motor de relatórios PDF é independente do motor fiscal/DANFE.
Reutiliza dados de apps.financeiro.relatorios (somente leitura).
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.core.pdf.formatters import format_currency_br, format_date_br
from apps.financeiro.relatorios import (
    relatorio_categorias,
    relatorio_clientes,
    relatorio_contas_pagar,
    relatorio_contas_receber,
    relatorio_fluxo_previsto,
    relatorio_fornecedores,
)
from apps.financeiro.relatorios_pdf_filters import _periodo_label, filtros_relatorio_financeiro
from apps.relatorios.definitions import ReportColumn, ReportData, ReportDefinition, ReportMetric
from apps.relatorios.export_service import ReportExportService

logger = logging.getLogger(__name__)


def _vencimento_celula_pdf(ln: dict) -> str:
    if ln.get('vencimento_ausente'):
        return str(ln['vencimento_ausente'])
    raw = ln.get('vencimento_exibicao') or ln.get('vencimento')
    fmt = format_date_br(raw)
    label = (ln.get('vencimento_label') or '').strip()
    if label and fmt != '—':
        try:
            from datetime import date as date_cls
            d = date_cls.fromisoformat(str(raw)[:10])
            return f'Próx.: {d.strftime("%d/%m/%Y")}'
        except ValueError:
            pass
    return fmt


def _empresa_contexto() -> tuple[str, str | None]:
    try:
        emp = Empresa.objects.filter(empresa_pai__isnull=True).order_by('id').first()
        if not emp:
            emp = Empresa.objects.order_by('id').first()
        if emp:
            return (emp.razao_social or emp.nome_fantasia or 'Empresa'), None
    except Exception as exc:
        logger.debug('empresa pdf relatório: %s', exc)
    return ('NEXUS APP', None)


def _usuario_nome(user: AbstractBaseUser | None) -> str:
    if not user or not getattr(user, 'is_authenticated', False):
        return '—'
    full = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    return full or getattr(user, 'username', '—') or '—'


def _metric_valor(metrica: dict | None) -> str:
    if not metrica:
        return 'R$ 0,00'
    v = metrica.get('valor')
    if v is None:
        return 'R$ 0,00'
    try:
        return format_currency_br(Decimal(str(v)))
    except Exception:
        return str(v)


def _metric_qtd(metrica: dict | None, fallback: int | str = 0) -> str:
    if metrica and metrica.get('quantidade') is not None:
        return str(metrica['quantidade'])
    return str(fallback)


def _pdf_filename(slug: str) -> str:
    d = timezone.localdate().strftime('%Y-%m-%d')
    return f'{slug}-{d}.pdf'


def _periodo_from_payload(payload: dict, *, padrao: str = 'mes') -> str:
    p = payload.get('periodo') or {}
    if p.get('data_inicio') and p.get('data_fim'):
        try:
            ini = date.fromisoformat(str(p['data_inicio'])[:10])
            fim = date.fromisoformat(str(p['data_fim'])[:10])
            return f'{ini.strftime("%d/%m/%Y")} a {fim.strftime("%d/%m/%Y")}'
        except ValueError:
            pass
    return _periodo_label({'periodo': p.get('periodo') or padrao})


def _export(defn: ReportDefinition) -> bytes:
    return ReportExportService().export_pdf(defn)


def pdf_relatorio_contas_receber(params, user=None) -> bytes:
    data = relatorio_contas_receber(params)
    empresa, _ = _empresa_contexto()
    cards = data['cards']
    rows = []
    tot_orig = tot_baix = tot_saldo = Decimal('0')
    for ln in data.get('linhas') or []:
        vo = Decimal(str(ln.get('valor_original') or 0))
        vb = Decimal(str(ln.get('valor_baixado') or 0))
        sal = Decimal(str(ln.get('saldo') or 0))
        tot_orig += vo
        tot_baix += vb
        tot_saldo += sal
        rows.append(
            {
                'vencimento': _vencimento_celula_pdf(ln),
                'cliente': ln.get('cliente_nome') or '—',
                'documento': ln.get('documento') or '—',
                'origem': ln.get('origem') or '—',
                'valor_original': format_currency_br(vo),
                'valor_baixado': format_currency_br(vb),
                'saldo': format_currency_br(sal),
                'status': ln.get('status_label') or ln.get('status') or '—',
                'categoria': ln.get('categoria_nome') or '—',
                'centro_custo': ln.get('centro_custo_nome') or '—',
            },
        )
    defn = ReportDefinition(
        module='financeiro',
        report_id='contas-receber',
        title='Relatório de Contas a Receber',
        description='Títulos a receber conforme filtros aplicados.',
        company_name=empresa,
        period_label=_periodo_from_payload(data),
        filters=filtros_relatorio_financeiro(params),
        metrics=[
            ReportMetric('Total em aberto', _metric_valor(cards.get('total_aberto'))),
            ReportMetric('Total vencido', _metric_valor(cards.get('total_vencido'))),
            ReportMetric('Recebido no período', _metric_valor(cards.get('recebido_periodo'))),
            ReportMetric('Parcialmente recebido', _metric_valor(cards.get('total_parcial'))),
            ReportMetric('Quantidade de títulos', _metric_qtd(None, cards.get('quantidade_titulos', 0))),
        ],
        columns=[
            ReportColumn('vencimento', 'Vencimento', width_mm=18),
            ReportColumn('cliente', 'Cliente', width_mm=32),
            ReportColumn('documento', 'Documento', width_mm=22),
            ReportColumn('origem', 'Origem', width_mm=28),
            ReportColumn('valor_original', 'Valor original', align='right', width_mm=22),
            ReportColumn('valor_baixado', 'Valor recebido', align='right', width_mm=22),
            ReportColumn('saldo', 'Saldo', align='right', width_mm=20),
            ReportColumn('status', 'Status', width_mm=24),
            ReportColumn('categoria', 'Categoria', width_mm=26),
            ReportColumn('centro_custo', 'Centro de custo', width_mm=26),
        ],
        data=ReportData(
            rows=rows,
            totals={
                'valor_original': format_currency_br(tot_orig),
                'valor_baixado': format_currency_br(tot_baix),
                'saldo': format_currency_br(tot_saldo),
            },
        ),
        orientation='landscape',
        filename=_pdf_filename('relatorio-contas-a-receber'),
        generated_by=_usuario_nome(user),
        aviso_historico=data.get('aviso_historico'),
    )
    return _export(defn)


def pdf_relatorio_contas_pagar(params, user=None) -> bytes:
    data = relatorio_contas_pagar(params)
    empresa, _ = _empresa_contexto()
    cards = data['cards']
    rows = []
    tot_orig = tot_baix = tot_saldo = Decimal('0')
    for ln in data.get('linhas') or []:
        vo = Decimal(str(ln.get('valor_original') or 0))
        vb = Decimal(str(ln.get('valor_baixado') or 0))
        sal = Decimal(str(ln.get('saldo') or 0))
        tot_orig += vo
        tot_baix += vb
        tot_saldo += sal
        counterparty = ln.get('fornecedor_nome') or ln.get('descricao') or '—'
        rows.append(
            {
                'vencimento': _vencimento_celula_pdf(ln),
                'fornecedor': counterparty,
                'tipo': ln.get('tipo_lancamento_label') or ln.get('tipo_lancamento') or '—',
                'documento': ln.get('documento') or '—',
                'origem': ln.get('origem') or '—',
                'valor_original': format_currency_br(vo),
                'valor_baixado': format_currency_br(vb),
                'saldo': format_currency_br(sal),
                'status': ln.get('status_label') or ln.get('status') or '—',
                'categoria': ln.get('categoria_nome') or '—',
                'centro_custo': ln.get('centro_custo_nome') or '—',
            },
        )
    defn = ReportDefinition(
        module='financeiro',
        report_id='contas-pagar',
        title='Relatório de Contas a Pagar',
        description='Títulos a pagar conforme filtros aplicados.',
        company_name=empresa,
        period_label=_periodo_from_payload(data),
        filters=filtros_relatorio_financeiro(params),
        metrics=[
            ReportMetric('Total em aberto', _metric_valor(cards.get('total_aberto'))),
            ReportMetric('Total vencido', _metric_valor(cards.get('total_vencido'))),
            ReportMetric('Pago no período', _metric_valor(cards.get('pago_periodo'))),
            ReportMetric('Parcialmente pago', _metric_valor(cards.get('total_parcial'))),
            ReportMetric('Tributos em aberto', _metric_valor(cards.get('total_tributos'))),
            ReportMetric('Quantidade de títulos', _metric_qtd(None, cards.get('quantidade_titulos', 0))),
        ],
        columns=[
            ReportColumn('vencimento', 'Vencimento', width_mm=18),
            ReportColumn('fornecedor', 'Fornecedor / descrição', width_mm=32),
            ReportColumn('tipo', 'Tipo', width_mm=20),
            ReportColumn('documento', 'Documento', width_mm=20),
            ReportColumn('origem', 'Origem', width_mm=26),
            ReportColumn('valor_original', 'Valor original', align='right', width_mm=20),
            ReportColumn('valor_baixado', 'Valor pago', align='right', width_mm=20),
            ReportColumn('saldo', 'Saldo', align='right', width_mm=18),
            ReportColumn('status', 'Status', width_mm=22),
            ReportColumn('categoria', 'Categoria', width_mm=24),
            ReportColumn('centro_custo', 'Centro de custo', width_mm=24),
        ],
        data=ReportData(
            rows=rows,
            totals={
                'valor_original': format_currency_br(tot_orig),
                'valor_baixado': format_currency_br(tot_baix),
                'saldo': format_currency_br(tot_saldo),
            },
        ),
        orientation='landscape',
        filename=_pdf_filename('relatorio-contas-a-pagar'),
        generated_by=_usuario_nome(user),
        aviso_historico=data.get('aviso_historico'),
    )
    return _export(defn)


def pdf_relatorio_fluxo_previsto(params, user=None) -> bytes:
    data = relatorio_fluxo_previsto(params)
    empresa, _ = _empresa_contexto()
    cards = data['cards']
    rows = [
        {
            'data': format_date_br(ln.get('data')),
            'a_receber': format_currency_br(ln.get('a_receber')),
            'a_pagar': format_currency_br(ln.get('a_pagar')),
            'saldo_dia': format_currency_br(ln.get('saldo_dia')),
            'saldo_acumulado': format_currency_br(ln.get('saldo_acumulado')),
        }
        for ln in data.get('linhas') or []
    ]
    maior_ent = cards.get('maior_entrada') or {}
    maior_sai = cards.get('maior_saida') or {}
    defn = ReportDefinition(
        module='financeiro',
        report_id='fluxo-previsto',
        title='Fluxo Financeiro Previsto',
        company_name=empresa,
        period_label=_periodo_from_payload(data, padrao='proximos_30'),
        filters=filtros_relatorio_financeiro(params),
        notes=[
            n
            for n in (
                'Previsão baseada em títulos em aberto. Não utiliza saldo bancário real '
                'e não substitui conciliação bancária.',
                (data.get('nota') or '').strip(),
            )
            if n
        ],
        metrics=[
            ReportMetric('A receber no período', _metric_valor(cards.get('total_receber'))),
            ReportMetric('A pagar no período', _metric_valor(cards.get('total_pagar'))),
            ReportMetric('Saldo previsto', _metric_valor(cards.get('saldo_previsto'))),
            ReportMetric(
                'Maior entrada',
                f"{_metric_valor(maior_ent)} ({format_date_br(maior_ent.get('data'))})",
            ),
            ReportMetric(
                'Maior saída',
                f"{_metric_valor(maior_sai)} ({format_date_br(maior_sai.get('data'))})",
            ),
        ],
        columns=[
            ReportColumn('data', 'Data', width_mm=22),
            ReportColumn('a_receber', 'A receber', align='right', width_mm=28),
            ReportColumn('a_pagar', 'A pagar', align='right', width_mm=28),
            ReportColumn('saldo_dia', 'Saldo do dia', align='right', width_mm=28),
            ReportColumn('saldo_acumulado', 'Saldo acumulado', align='right', width_mm=32),
        ],
        data=ReportData(rows=rows),
        filename=_pdf_filename('fluxo-previsto'),
        generated_by=_usuario_nome(user),
    )
    return _export(defn)


def pdf_relatorio_categorias(params, user=None) -> bytes:
    data = relatorio_categorias(params)
    empresa, _ = _empresa_contexto()
    cards = data['cards']
    rows = [
        {
            'categoria': ln.get('categoria_nome') or '—',
            'tipo': ln.get('tipo') or '—',
            'quantidade': str(ln.get('quantidade') or 0),
            'valor_original': format_currency_br(ln.get('valor_original')),
            'em_aberto': format_currency_br(ln.get('em_aberto')),
            'baixado': format_currency_br(ln.get('baixado_periodo') or ln.get('baixado')),
            'total': format_currency_br(ln.get('total_considerado') or ln.get('total')),
        }
        for ln in data.get('linhas') or []
    ]
    sem = cards.get('sem_classificacao') or {}
    defn = ReportDefinition(
        module='financeiro',
        report_id='categorias',
        title='Receitas e Despesas por Categoria',
        company_name=empresa,
        period_label=_periodo_from_payload(data),
        filters=filtros_relatorio_financeiro(params),
        notes=['Relatório operacional por categoria. Não é DRE contábil.'],
        metrics=[
            ReportMetric('Total de receitas', _metric_valor(cards.get('total_receitas'))),
            ReportMetric('Total de despesas', _metric_valor(cards.get('total_despesas'))),
            ReportMetric('Diferença prevista', _metric_valor(cards.get('diferenca_prevista'))),
            ReportMetric(
                'Sem classificação',
                f"{sem.get('receitas', 0)} rec. / {sem.get('despesas', 0)} desp.",
            ),
        ],
        columns=[
            ReportColumn('categoria', 'Categoria', width_mm=36),
            ReportColumn('tipo', 'Tipo', width_mm=18),
            ReportColumn('quantidade', 'Qtd.', align='right', width_mm=12),
            ReportColumn('valor_original', 'Valor original', align='right', width_mm=24),
            ReportColumn('em_aberto', 'Em aberto', align='right', width_mm=22),
            ReportColumn('baixado', 'Baixado no período', align='right', width_mm=26),
            ReportColumn('total', 'Total considerado', align='right', width_mm=24),
        ],
        data=ReportData(rows=rows),
        orientation='landscape',
        filename=_pdf_filename('receitas-despesas-categoria'),
        generated_by=_usuario_nome(user),
        aviso_historico=data.get('aviso_historico'),
    )
    return _export(defn)


def pdf_relatorio_clientes(params, user=None) -> bytes:
    data = relatorio_clientes(params)
    empresa, _ = _empresa_contexto()
    resumo = data.get('resumo') or []
    tot_aberto = sum(Decimal(str(r.get('total_aberto') or 0)) for r in resumo)
    tot_venc = sum(Decimal(str(r.get('total_vencido') or 0)) for r in resumo)
    tot_rec = sum(Decimal(str(r.get('recebido_periodo') or 0)) for r in resumo)
    q_titulos = sum(int(r.get('quantidade_titulos') or 0) for r in resumo)
    rows = [
        {
            'cliente': r.get('cliente_nome') or '—',
            'em_aberto': format_currency_br(r.get('total_aberto')),
            'vencido': format_currency_br(r.get('total_vencido')),
            'recebido_periodo': format_currency_br(r.get('recebido_periodo')),
            'titulos': str(r.get('quantidade_titulos') or 0),
            'ultimo_recebimento': format_date_br(r.get('ultimo_recebimento')),
        }
        for r in resumo
    ]
    defn = ReportDefinition(
        module='financeiro',
        report_id='clientes',
        title='Relatório por Cliente',
        company_name=empresa,
        period_label=_periodo_from_payload(data),
        filters=filtros_relatorio_financeiro(params),
        metrics=[
            ReportMetric('Total em aberto', format_currency_br(tot_aberto)),
            ReportMetric('Total vencido', format_currency_br(tot_venc)),
            ReportMetric('Recebido no período', format_currency_br(tot_rec)),
            ReportMetric('Quantidade de clientes', str(len(resumo))),
            ReportMetric('Quantidade de títulos', str(q_titulos)),
        ],
        columns=[
            ReportColumn('cliente', 'Cliente', width_mm=42),
            ReportColumn('em_aberto', 'Em aberto', align='right', width_mm=24),
            ReportColumn('vencido', 'Vencido', align='right', width_mm=24),
            ReportColumn('recebido_periodo', 'Recebido no período', align='right', width_mm=28),
            ReportColumn('titulos', 'Títulos', align='right', width_mm=14),
            ReportColumn('ultimo_recebimento', 'Último recebimento', width_mm=26),
        ],
        data=ReportData(rows=rows),
        filename=_pdf_filename('relatorio-por-cliente'),
        generated_by=_usuario_nome(user),
        aviso_historico=data.get('aviso_historico'),
    )
    return _export(defn)


def pdf_relatorio_fornecedores(params, user=None) -> bytes:
    data = relatorio_fornecedores(params)
    empresa, _ = _empresa_contexto()
    resumo = data.get('resumo') or []
    tot_aberto = sum(Decimal(str(r.get('total_aberto') or 0)) for r in resumo)
    tot_venc = sum(Decimal(str(r.get('total_vencido') or 0)) for r in resumo)
    tot_pago = sum(Decimal(str(r.get('pago_periodo') or 0)) for r in resumo)
    q_titulos = sum(int(r.get('quantidade_titulos') or 0) for r in resumo)
    rows = [
        {
            'fornecedor': r.get('fornecedor_nome') or '—',
            'em_aberto': format_currency_br(r.get('total_aberto')),
            'vencido': format_currency_br(r.get('total_vencido')),
            'pago_periodo': format_currency_br(r.get('pago_periodo')),
            'titulos': str(r.get('quantidade_titulos') or 0),
            'ultimo_pagamento': format_date_br(r.get('ultimo_pagamento')),
        }
        for r in resumo
    ]
    defn = ReportDefinition(
        module='financeiro',
        report_id='fornecedores',
        title='Relatório por Fornecedor',
        company_name=empresa,
        period_label=_periodo_from_payload(data),
        filters=filtros_relatorio_financeiro(params),
        metrics=[
            ReportMetric('Total em aberto', format_currency_br(tot_aberto)),
            ReportMetric('Total vencido', format_currency_br(tot_venc)),
            ReportMetric('Pago no período', format_currency_br(tot_pago)),
            ReportMetric('Quantidade de fornecedores', str(len(resumo))),
            ReportMetric('Quantidade de títulos', str(q_titulos)),
        ],
        columns=[
            ReportColumn('fornecedor', 'Fornecedor', width_mm=42),
            ReportColumn('em_aberto', 'Em aberto', align='right', width_mm=24),
            ReportColumn('vencido', 'Vencido', align='right', width_mm=24),
            ReportColumn('pago_periodo', 'Pago no período', align='right', width_mm=28),
            ReportColumn('titulos', 'Títulos', align='right', width_mm=14),
            ReportColumn('ultimo_pagamento', 'Último pagamento', width_mm=26),
        ],
        data=ReportData(rows=rows),
        filename=_pdf_filename('relatorio-por-fornecedor'),
        generated_by=_usuario_nome(user),
        aviso_historico=data.get('aviso_historico'),
    )
    return _export(defn)
