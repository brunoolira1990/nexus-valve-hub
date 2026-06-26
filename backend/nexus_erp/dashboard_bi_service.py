"""Serviços BI por módulo — KPIs, gráficos, rankings e alertas (ERP 4.0.8)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.cadastros.models import Empresa, Fornecedor
from apps.comercial.models import ItemPedidoVenda, PedidoCompra, PedidoVenda, Proposta
from apps.fiscal.central_dfe.service import resumo_central_dfe_dashboard
from apps.expedicao.models import Expedicao, StatusExpedicao, TipoOperacaoExpedicao
from apps.expedicao.services.expedicao_service import resumo_expedicoes_por_status
from apps.fiscal.models import (
    AtendimentoEstoque,
    CTeHistoricoImportado,
    EstoqueCorrida,
    NFeEntrada,
    NFeSaida,
    NFeSefazStatusConsulta,
)
from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida
from apps.produtos.models import Produto
from apps.qualidade.models import CertificadoQualidade

from nexus_erp.dashboard_filters import DashboardFilters, periodo_dict
from nexus_erp.dashboard_operacional_resumo import (
    resumo_pendencias_produto_estoque,
    resumo_pendencias_qualidade,
)
from nexus_erp.dashboard_permissions import modulos_permitidos, permissoes_dashboard, usuario_pode_ver_dashboard_modulo

RANKING_LIMIT = 5
ULTIMOS_LIMIT = 5


def _dec(v) -> Decimal:
    if v is None:
        return Decimal('0')
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _kpi(kid: str, titulo: str, valor, formato: str = 'numero', link: str | None = None, subtitulo: str = '') -> dict:
    return {
        'id': kid,
        'titulo': titulo,
        'valor': valor,
        'formato': formato,
        'link': link,
        'subtitulo': subtitulo,
    }


def _chart(cid: str, titulo: str, tipo: str, dados: list[dict]) -> dict:
    return {'id': cid, 'titulo': titulo, 'tipo': tipo, 'dados': dados}


def _ranking(rid: str, titulo: str, itens: list[dict]) -> dict:
    return {'id': rid, 'titulo': titulo, 'itens': itens[:RANKING_LIMIT]}


def _alerta(modulo: str, severidade: str, titulo: str, mensagem: str, link: str) -> dict:
    return {
        'modulo': modulo,
        'severidade': severidade,
        'titulo': titulo,
        'mensagem': mensagem,
        'link': link,
    }


def _filtro_empresa_pv(qs, f: DashboardFilters):
    if f.empresa_id:
        qs = qs.filter(empresa_emitente_id=f.empresa_id)
    return qs


def _filtro_empresa_nfe(qs, f: DashboardFilters):
    if f.empresa_id:
        qs = qs.filter(empresa_emitente_id=f.empresa_id)
    return qs


def _filtro_periodo_data(qs, f: DashboardFilters, campo: str = 'data'):
    return qs.filter(**{f'{campo}__gte': f.data_inicio, f'{campo}__lte': f.data_fim})


def _base_bi(modulo: str, f: DashboardFilters) -> dict:
    return {
        'modulo': modulo,
        'periodo': periodo_dict(f),
        'kpis': [],
        'graficos': [],
        'rankings': [],
        'alertas': [],
        'ultimos': [],
        'links': [],
    }


# ---------------------------------------------------------------------------
# Comercial
# ---------------------------------------------------------------------------

def montar_bi_comercial(f: DashboardFilters) -> dict:
    out = _base_bi('comercial', f)
    pv_qs = PedidoVenda.objects.select_related('cliente')
    pv_qs = _filtro_empresa_pv(pv_qs, f)
    prop_qs = Proposta.objects.select_related('cliente')
    if f.empresa_id:
        prop_qs = prop_qs.filter(empresa_emitente_id=f.empresa_id)

    abertos = pv_qs.filter(status__icontains='ABERTO').exclude(status__icontains='CANCEL').count()
    parciais = pv_qs.filter(
        Q(status__icontains='PARCIAL') | Q(status__icontains='EM_FATURAMENTO'),
    ).count()
    pv_periodo = _filtro_periodo_data(pv_qs, f)
    faturados = pv_periodo.filter(status__icontains='FATURADO').count()
    valor_faturado = pv_periodo.filter(status__icontains='FATURADO').aggregate(t=Sum('valor_total'))['t'] or Decimal('0')

    pv_aberto_qs = pv_qs.exclude(status__icontains='FATURADO').exclude(status__icontains='CANCEL')
    valor_aberto = _dec(pv_aberto_qs.aggregate(t=Sum('valor_total'))['t'])

    propostas_abertas = prop_qs.filter(
        Q(status__icontains='ABERT') | Q(status__icontains='PEND'),
    ).exclude(status__icontains='CANCEL').count()
    propostas_convertidas = prop_qs.filter(status__icontains='CONVERT').count()

    out['kpis'] = [
        _kpi('pedidos_abertos', 'Pedidos abertos', abertos, link='/pedidos-venda?status=aberto'),
        _kpi('pedidos_parciais', 'Parcialmente faturados', parciais, link='/pedidos-venda?status=parcialmente_faturado'),
        _kpi('pedidos_faturados', 'Faturados no período', faturados),
        _kpi('valor_aberto', 'Valor a faturar', str(valor_aberto), 'moeda', '/pedidos-venda?status=aberto'),
        _kpi('valor_faturado', 'Faturado no período', str(_dec(valor_faturado)), 'moeda'),
        _kpi('propostas_abertas', 'Propostas abertas', propostas_abertas, link='/propostas?status=aberta'),
        _kpi('propostas_convertidas', 'Propostas convertidas', propostas_convertidas),
    ]

    status_rows = (
        pv_qs.values('status')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )
    out['graficos'].append(
        _chart(
            'pedidos_por_status',
            'Pedidos por status',
            'bar',
            [{'label': (r['status'] or '—'), 'valor': r['total']} for r in status_rows],
        ),
    )

    evolucao = (
        _filtro_periodo_data(pv_qs, f)
        .annotate(mes=TruncMonth('data'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    out['graficos'].append(
        _chart(
            'evolucao_pedidos',
            'Evolução de pedidos',
            'line',
            [{'label': (r['mes'].strftime('%m/%Y') if r['mes'] else '—'), 'valor': r['total']} for r in evolucao],
        ),
    )

    prop_status = (
        prop_qs.values('status')
        .annotate(total=Count('id'))
        .order_by('-total')[:6]
    )
    out['graficos'].append(
        _chart(
            'propostas_por_status',
            'Propostas por status',
            'donut',
            [{'label': (r['status'] or '—'), 'valor': r['total']} for r in prop_status],
        ),
    )

    top_clientes = (
        pv_qs.filter(cliente_id__isnull=False)
        .values('cliente__razao_social')
        .annotate(total=Sum('valor_total'))
        .order_by('-total')[:RANKING_LIMIT]
    )
    out['rankings'].append(
        _ranking(
            'top_clientes',
            'Top clientes por valor',
            [
                {
                    'label': r['cliente__razao_social'] or '—',
                    'valor': str(_dec(r['total'])),
                    'link': '/pedidos-venda',
                }
                for r in top_clientes
            ],
        ),
    )

    top_produtos = (
        ItemPedidoVenda.objects.filter(pedido__in=pv_qs.values('pk'))
        .values('produto__descricao', 'produto__codigo_completo')
        .annotate(qtd=Sum('quantidade'))
        .order_by('-qtd')[:RANKING_LIMIT]
    )
    out['rankings'].append(
        _ranking(
            'top_produtos',
            'Top produtos vendidos',
            [
                {
                    'label': r['produto__codigo_completo'] or r['produto__descricao'] or '—',
                    'valor': str(_dec(r['qtd'])),
                    'link': '/produtos',
                }
                for r in top_produtos
            ],
        ),
    )

    maiores_abertos = pv_qs.filter(status__icontains='ABERTO').order_by('-valor_total')[:RANKING_LIMIT]
    out['rankings'].append(
        _ranking(
            'maiores_pedidos_abertos',
            'Maiores pedidos em aberto',
            [
                {
                    'label': p.numero,
                    'valor': str(_dec(p.valor_total)),
                    'link': f'/pedidos-venda?pedido={p.pk}',
                }
                for p in maiores_abertos
            ],
        ),
    )

    for p in pv_qs.order_by('-data', '-id')[:ULTIMOS_LIMIT]:
        out['ultimos'].append(
            {
                'tipo': 'pedido_venda',
                'titulo': p.numero,
                'subtitulo': p.cliente.razao_social if p.cliente_id else '',
                'valor': str(_dec(p.valor_total)),
                'status': p.status or '',
                'data': p.data.isoformat(),
                'link': f'/pedidos-venda?pedido={p.pk}',
            },
        )

    for pr in prop_qs.order_by('-data', '-id')[:ULTIMOS_LIMIT]:
        out['ultimos'].append(
            {
                'tipo': 'proposta',
                'titulo': pr.numero,
                'subtitulo': pr.cliente.razao_social if pr.cliente_id else (pr.cliente_avulso_nome or ''),
                'valor': '',
                'status': pr.status or '',
                'data': pr.data.isoformat(),
                'link': '/propostas',
            },
        )

    if abertos:
        out['alertas'].append(
            _alerta('comercial', 'aviso', 'Pedidos abertos', f'{abertos} pedido(s) aberto(s).', '/pedidos-venda?status=aberto'),
        )
    if parciais:
        out['alertas'].append(
            _alerta(
                'comercial',
                'info',
                'Parcialmente faturados',
                f'{parciais} pedido(s) parcialmente faturado(s).',
                '/pedidos-venda?status=parcialmente_faturado',
            ),
        )
    vencidas = prop_qs.filter(validade__lt=timezone.localdate()).exclude(status__icontains='CONVERT').count()
    if vencidas:
        out['alertas'].append(
            _alerta('comercial', 'aviso', 'Propostas vencidas', f'{vencidas} proposta(s) vencida(s).', '/propostas'),
        )

    return out


# ---------------------------------------------------------------------------
# Fiscal
# ---------------------------------------------------------------------------


def _hero_kpi_id_fiscal(
    *,
    auth_prod: int,
    rej_prod: int,
    enviada_prod: int,
    auth_homolog: int,
    rej_homolog: int,
) -> str:
    tem_producao = auth_prod > 0 or rej_prod > 0 or enviada_prod > 0
    if tem_producao:
        if rej_prod > 0 and auth_prod == 0:
            return 'nfe_rej_prod'
        return 'nfe_auth_prod'
    if rej_homolog > 0 and auth_homolog == 0:
        return 'nfe_rej_homolog'
    return 'nfe_auth_homolog'


def montar_bi_fiscal(f: DashboardFilters) -> dict:
    out = _base_bi('fiscal', f)
    nf_qs = _filtro_empresa_nfe(NFeSaida.objects.select_related('cliente'), f)
    entrada_qs = NFeEntrada.objects.select_related('fornecedor')
    entrada_propria = entrada_qs.filter(
        tipo_origem__in=(
            NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_IMPORTADA,
            NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
        ),
    ).count()
    cte_historico = CTeHistoricoImportado.objects.count()

    rascunhos = nf_qs.filter(status__icontains='RASCUNHO').count()
    prontas = nf_qs.filter(status_conferencia='PRONTA_PARA_EMISSAO').count()
    auth_homolog = nf_qs.filter(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO).count()
    rej_homolog = nf_qs.filter(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO).count()
    auth_prod = nf_qs.filter(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO).count()
    rej_prod = nf_qs.filter(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO).count()
    enviada_prod = nf_qs.filter(
        status_emissao_sefaz__in=(
            NFeSaida.StatusEmissaoSefaz.ENVIADA_PRODUCAO,
            NFeSaida.StatusEmissaoSefaz.AGUARDANDO_PROCESSAMENTO,
        ),
    ).count()
    erro = nf_qs.filter(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO).count()
    canceladas = nf_qs.filter(status__icontains='CANCEL').count()

    dfe = resumo_central_dfe_dashboard(f.empresa_id)

    out['hero_kpi_id'] = _hero_kpi_id_fiscal(
        auth_prod=auth_prod,
        rej_prod=rej_prod,
        enviada_prod=enviada_prod,
        auth_homolog=auth_homolog,
        rej_homolog=rej_homolog,
    )
    out['kpis'] = [
        _kpi('nfe_auth_prod', 'Autorizadas produção', auth_prod, link='/nfe-saida?status_emissao=autorizada_producao'),
        _kpi('nfe_rej_prod', 'Rejeitadas produção', rej_prod, link='/nfe-saida?status_emissao=rejeitada_producao'),
        _kpi('nfe_enviada_prod', 'Enviadas produção', enviada_prod, link='/nfe-saida?status_emissao=enviada_producao'),
        _kpi('nfe_auth_homolog', 'Autorizadas homologação', auth_homolog, link='/nfe-saida?status_emissao=autorizada_homologacao'),
        _kpi('nfe_rej_homolog', 'Rejeitadas homologação', rej_homolog, link='/nfe-saida?status_emissao=rejeitada_homologacao'),
        _kpi('nfe_rascunhos', 'Rascunhos', rascunhos, link='/nfe-saida?status=rascunho'),
        _kpi('nfe_prontas', 'Prontas para emissão', prontas, link='/nfe-saida'),
        _kpi('nfe_erro_tx', 'Erro transmissão', erro, link='/nfe-saida?status_emissao=erro_transmissao'),
        _kpi('nfe_canceladas', 'Canceladas', canceladas),
        _kpi('dfe_pendentes_entrada', 'DF-e pendentes de entrada', dfe['pendentes_entrada'], link='/central-dfe'),
        _kpi(
            'dfe_aguardando_manifestacao',
            'NF-e aguardando manifestação',
            dfe['aguardando_manifestacao'],
            link='/central-dfe',
        ),
        _kpi('dfe_xml_pendente', 'XML DF-e pendente', dfe['xml_pendente'], link='/central-dfe'),
        _kpi('dfe_cte_pendentes', 'CT-e pendentes', dfe['cte_pendentes'], link='/central-dfe'),
        _kpi('nfe_entrada_total', 'NF-e entrada', entrada_qs.count(), link='/nfe-entrada'),
        _kpi(
            'nfe_entrada_propria',
            'Entrada própria',
            entrada_propria,
            link='/nfe-entrada?tipo_origem=entrada_propria',
        ),
        _kpi('cte_historico_importado', 'CT-e importados', cte_historico, link='/central-dfe'),
    ]

    status_chart_homolog = [
        {'label': 'Rascunho', 'valor': rascunhos},
        {'label': 'Pronta emissão', 'valor': prontas},
        {'label': 'Auth. homolog.', 'valor': auth_homolog},
        {'label': 'Rej. homolog.', 'valor': rej_homolog},
        {'label': 'Erro transmissão', 'valor': erro},
        {'label': 'Cancelada', 'valor': canceladas},
    ]
    out['graficos'].append(_chart('nfe_saida_homologacao', 'NF-e saída — homologação', 'bar', status_chart_homolog))

    status_chart_prod = [
        {'label': 'Auth. produção', 'valor': auth_prod},
        {'label': 'Rej. produção', 'valor': rej_prod},
        {'label': 'Enviada produção', 'valor': enviada_prod},
    ]
    out['graficos'].append(_chart('nfe_saida_producao', 'NF-e saída — produção', 'bar', status_chart_prod))

    dfe_chart = [
        {'label': 'Pend. entrada', 'valor': dfe['pendentes_entrada']},
        {'label': 'Aguard. manifest.', 'valor': dfe['aguardando_manifestacao']},
        {'label': 'XML pendente', 'valor': dfe['xml_pendente']},
        {'label': 'CT-e pendente', 'valor': dfe['cte_pendentes']},
    ]
    out['graficos'].append(_chart('dfe_recebidos_alertas', 'DF-e recebidos — fila', 'donut', dfe_chart))

    nf_periodo = _filtro_periodo_data(nf_qs, f)
    evolucao = (
        nf_periodo.annotate(mes=TruncMonth('data'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    out['graficos'].append(
        _chart(
            'evolucao_nfe',
            'NF-e no período',
            'line',
            [{'label': (r['mes'].strftime('%m/%Y') if r['mes'] else '—'), 'valor': r['total']} for r in evolucao],
        ),
    )

    cstat_rows = (
        nf_qs.filter(cstat_autorizacao__gt='')
        .exclude(cstat_autorizacao='100')
        .values('cstat_autorizacao')
        .annotate(total=Count('id'))
        .order_by('-total')[:RANKING_LIMIT]
    )
    out['rankings'].append(
        _ranking(
            'top_cstat_rejeicao',
            'Top cStat de rejeição',
            [{'label': r['cstat_autorizacao'], 'valor': str(r['total']), 'link': '/nfe-saida?status_emissao=rejeitada_homologacao'} for r in cstat_rows],
        ),
    )

    if dfe['total']:
        out['links'].append(
            {
                'id': 'central_dfe',
                'titulo': 'DF-e Recebidos',
                'descricao': (
                    f"{dfe['total']} documento(s) na fila — "
                    f"{dfe['pendentes_entrada']} pendente(s) de entrada, "
                    f"{dfe['aguardando_manifestacao']} aguardando manifestação."
                ),
                'link': '/central-dfe',
            },
        )

    top_clientes = (
        nf_qs.filter(cliente_id__isnull=False)
        .values('cliente__razao_social')
        .annotate(total=Count('id'))
        .order_by('-total')[:RANKING_LIMIT]
    )
    out['rankings'].append(
        _ranking(
            'top_clientes_nfe',
            'Clientes com mais NF-e',
            [{'label': r['cliente__razao_social'] or '—', 'valor': str(r['total']), 'link': '/nfe-saida'} for r in top_clientes],
        ),
    )

    top_forn = (
        entrada_qs.filter(fornecedor_id__isnull=False)
        .values('fornecedor__razao_social')
        .annotate(total=Count('id'))
        .order_by('-total')[:RANKING_LIMIT]
    )
    out['rankings'].append(
        _ranking(
            'top_fornecedores_entrada',
            'Fornecedores com mais NF-e entrada',
            [{'label': r['fornecedor__razao_social'] or '—', 'valor': str(r['total']), 'link': '/nfe-entrada'} for r in top_forn],
        ),
    )

    for nf in nf_qs.order_by('-id')[:ULTIMOS_LIMIT]:
        ap = montar_apresentacao_nfe_saida(nf)
        out['ultimos'].append(
            {
                'tipo': 'nfe_saida',
                'titulo': ap['listagem_titulo'],
                'subtitulo': nf.cliente.razao_social if nf.cliente_id else '',
                'valor': str(_dec(nf.valor_total)),
                'status': ap['badge_principal']['label'],
                'data': nf.data.isoformat() if nf.data else '',
                'link': f'/nfe-saida?nfe={nf.pk}',
            },
        )

    sefaz = NFeSefazStatusConsulta.objects.select_related('empresa').order_by('-consultado_em').first()
    if sefaz:
        out['links'].append(
            {
                'id': 'sefaz_status',
                'titulo': 'Status SEFAZ',
                'descricao': f"{sefaz.ambiente}: cStat {sefaz.c_stat} — {sefaz.x_motivo}",
                'link': '/nfe-sefaz',
            },
        )

    hoje = timezone.localdate()
    cert_vencendo = Empresa.objects.filter(
        certificado_validade__lte=hoje + timedelta(days=30),
        certificado_validade__gte=hoje,
    ).count()
    cert_vencido = Empresa.objects.filter(certificado_validade__lt=hoje).count()
    if cert_vencido:
        out['alertas'].append(
            _alerta('fiscal', 'critico', 'Certificado vencido', f'{cert_vencido} empresa(s) com certificado vencido.', '/empresas'),
        )
    elif cert_vencendo:
        out['alertas'].append(
            _alerta('fiscal', 'aviso', 'Certificado vencendo', f'{cert_vencendo} certificado(s) vence(m) em 30 dias.', '/empresas'),
        )
    if rej_homolog:
        out['alertas'].append(
            _alerta('fiscal', 'critico', 'NF-e rejeitada (homologação)', f'{rej_homolog} NF-e rejeitada(s) em homologação.', '/nfe-saida?status_emissao=rejeitada_homologacao'),
        )
    if rej_prod:
        out['alertas'].append(
            _alerta('fiscal', 'critico', 'NF-e rejeitada (produção)', f'{rej_prod} NF-e rejeitada(s) em produção.', '/nfe-saida?status_emissao=rejeitada_producao'),
        )
    if erro:
        out['alertas'].append(
            _alerta('fiscal', 'critico', 'Erro transmissão', f'{erro} NF-e com erro de transmissão.', '/nfe-saida?status_emissao=erro_transmissao'),
        )
    if dfe['aguardando_manifestacao']:
        out['alertas'].append(
            _alerta(
                'fiscal',
                'aviso',
                'Manifestação pendente',
                f"{dfe['aguardando_manifestacao']} NF-e destinada(s) aguardando manifestação.",
                '/central-dfe',
            ),
        )
    if dfe['xml_pendente']:
        out['alertas'].append(
            _alerta(
                'fiscal',
                'aviso',
                'XML DF-e pendente',
                f"{dfe['xml_pendente']} documento(s) com XML ainda não armazenado.",
                '/central-dfe',
            ),
        )
    if dfe['pendentes_entrada']:
        out['alertas'].append(
            _alerta(
                'fiscal',
                'info',
                'DF-e pendentes de entrada',
                f"{dfe['pendentes_entrada']} documento(s) na fila de entrada.",
                '/central-dfe',
            ),
        )

    sem_ncm = Produto.objects.filter(Q(ncm='') | Q(ncm__isnull=True)).count()
    if sem_ncm:
        out['alertas'].append(
            _alerta('fiscal', 'info', 'Produtos sem NCM', f'{sem_ncm} produto(s) sem NCM.', '/produtos?sem_ncm=1'),
        )

    return out


# ---------------------------------------------------------------------------
# Estoque
# ---------------------------------------------------------------------------


def montar_bi_estoque(f: DashboardFilters) -> dict:
    out = _base_bi('estoque', f)
    total_produtos = Produto.objects.count()
    operacional = resumo_pendencias_produto_estoque()
    sem_ncm = operacional['sem_ncm']
    saldo_map = {
        row['produto_id']: _dec(row['total'])
        for row in EstoqueCorrida.objects.values('produto_id').annotate(total=Sum('saldo'))
    }
    baixo = 0
    for p in Produto.objects.filter(estoque_minimo__gt=0).only('id', 'estoque_minimo').iterator(chunk_size=500):
        saldo = saldo_map.get(p.pk, Decimal('0'))
        if saldo < _dec(p.estoque_minimo):
            baixo += 1
    negativo = sum(1 for saldo in saldo_map.values() if saldo < Decimal('0'))

    atend_pendentes = AtendimentoEstoque.objects.filter(status='PENDENTE').count()
    sem_corrida_com_saldo = operacional['sem_corrida_com_saldo']
    produtos_sem_corrida = operacional['produtos_sem_corrida']
    sem_ncm_com_saldo = operacional['sem_ncm_com_saldo']

    out['hero_kpi_id'] = 'produtos_cadastrados'
    if sem_corrida_com_saldo > 0:
        out['hero_kpi_id'] = 'sem_corrida_com_saldo'
    elif produtos_sem_corrida > 0 and total_produtos <= 50:
        out['hero_kpi_id'] = 'produtos_sem_corrida'
    elif baixo > 0:
        out['hero_kpi_id'] = 'estoque_baixo'

    out['kpis'] = [
        _kpi('produtos_cadastrados', 'Produtos cadastrados', total_produtos, link='/produtos'),
        _kpi('produtos_com_saldo', 'Com saldo em estoque', operacional['produtos_com_saldo'], link='/estoque'),
        _kpi('produtos_sem_corrida', 'Sem corrida cadastrada', produtos_sem_corrida, link='/produtos'),
        _kpi('sem_corrida_com_saldo', 'Saldo sem corrida do produto', sem_corrida_com_saldo, link='/produtos'),
        _kpi('produtos_sem_ncm', 'Sem NCM', sem_ncm, link='/produtos?sem_ncm=1'),
        _kpi('sem_ncm_com_saldo', 'Sem NCM com saldo', sem_ncm_com_saldo, link='/produtos?sem_ncm=1'),
        _kpi('estoque_baixo', 'Abaixo do mínimo', baixo, link='/estoque?filtro=baixo_estoque'),
        _kpi('saldo_negativo', 'Saldo negativo', negativo, link='/estoque?filtro=saldo_negativo'),
        _kpi('atendimentos_pendentes', 'Atendimentos pendentes', atend_pendentes, link='/atendimentos-estoque'),
    ]

    familias = (
        Produto.objects.filter(familia_id__isnull=False)
        .values('familia__codigo_figura')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )
    out['graficos'].append(
        _chart(
            'produtos_por_familia',
            'Produtos por família',
            'bar',
            [{'label': r['familia__codigo_figura'] or '—', 'valor': r['total']} for r in familias],
        ),
    )

    alertas_tipos = [
        {'label': 'Baixo estoque', 'valor': baixo},
        {'label': 'Sem corrida', 'valor': produtos_sem_corrida},
        {'label': 'Sem NCM', 'valor': sem_ncm},
        {'label': 'Saldo negativo', 'valor': negativo},
    ]
    out['graficos'].append(_chart('alertas_estoque', 'Alertas por tipo', 'donut', alertas_tipos))

    menores = []
    for p in Produto.objects.order_by('descricao')[:200]:
        saldo = saldo_map.get(p.pk, Decimal('0'))
        if saldo <= Decimal('0'):
            continue
        menores.append((p, saldo))
    menores.sort(key=lambda x: x[1])
    out['rankings'].append(
        _ranking(
            'menor_saldo',
            'Produtos com menor saldo',
            [
                {
                    'label': p.codigo_completo or p.descricao,
                    'valor': str(saldo),
                    'link': f'/produtos?produto={p.pk}',
                }
                for p, saldo in menores[:RANKING_LIMIT]
            ],
        ),
    )

    for att in AtendimentoEstoque.objects.select_related('produto', 'nf_saida').order_by('-criado_em')[:ULTIMOS_LIMIT]:
        out['ultimos'].append(
            {
                'tipo': 'atendimento_estoque',
                'titulo': att.produto.codigo_completo if att.produto_id else '—',
                'subtitulo': att.nf_saida.numero if att.nf_saida_id else '',
                'valor': str(_dec(att.quantidade_comprometida)),
                'status': att.status,
                'data': att.criado_em.date().isoformat() if att.criado_em else '',
                'link': '/atendimentos-estoque',
            },
        )

    if produtos_sem_corrida:
        out['alertas'].append(
            _alerta(
                'estoque',
                'info',
                'Produtos sem corrida',
                f'{produtos_sem_corrida} produto(s) sem corrida/lote cadastrada.',
                '/produtos',
            ),
        )
    if sem_corrida_com_saldo:
        out['alertas'].append(
            _alerta(
                'estoque',
                'aviso',
                'Saldo sem corrida',
                f'{sem_corrida_com_saldo} produto(s) com saldo sem corrida/lote cadastrada.',
                '/produtos',
            ),
        )
    if sem_ncm_com_saldo:
        out['alertas'].append(
            _alerta(
                'estoque',
                'info',
                'Sem NCM com saldo',
                f'{sem_ncm_com_saldo} produto(s) com saldo e sem NCM.',
                '/produtos?sem_ncm=1',
            ),
        )
    if baixo:
        out['alertas'].append(
            _alerta('estoque', 'aviso', 'Baixo estoque', f'{baixo} produto(s) abaixo do mínimo.', '/estoque?filtro=baixo_estoque'),
        )
    if negativo:
        out['alertas'].append(
            _alerta('estoque', 'critico', 'Saldo negativo', f'{negativo} produto(s) com saldo negativo.', '/estoque?filtro=saldo_negativo'),
        )

    return out


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------


def montar_bi_compras(f: DashboardFilters) -> dict:
    out = _base_bi('compras', f)
    pc_qs = PedidoCompra.objects.select_related('fornecedor')
    pc_all = pc_qs

    abertos = pc_all.filter(status__icontains='ABERT').count()
    aprovados = pc_all.filter(status__icontains='APROV').count()
    parcial = pc_all.filter(Q(status__icontains='PARCIAL') | Q(status__icontains='RECEB_PAR')).count()
    recebidos = pc_all.filter(status__icontains='RECEB').exclude(status__icontains='PARCIAL').count()

    pc_abertos_qs = pc_all.filter(status__icontains='ABERT')
    valor_aberto = _dec(pc_abertos_qs.aggregate(t=Sum('valor_total'))['t'])

    entrada_qs = NFeEntrada.objects.all()
    entrada_total = entrada_qs.count()
    entrada_propria = entrada_qs.filter(
        tipo_origem__in=(
            NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_IMPORTADA,
            NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
        ),
    ).count()
    cte_historico = CTeHistoricoImportado.objects.count()

    out['kpis'] = [
        _kpi('pc_abertos', 'Pedidos abertos', abertos, link='/pedidos-compra?status=aberto'),
        _kpi('pc_aprovados', 'Aprovados', aprovados, link='/pedidos-compra?status=aprovado'),
        _kpi('pc_parcial', 'Recebido parcial', parcial, link='/pedidos-compra?status=recebido_parcial'),
        _kpi('pc_recebidos', 'Recebidos', recebidos, link='/pedidos-compra?status=recebido'),
        _kpi('valor_aberto_compras', 'Valor em aberto', str(valor_aberto), 'moeda', '/pedidos-compra?status=aberto'),
        _kpi('nfe_entrada', 'NF-e entrada', entrada_total, link='/nfe-entrada'),
        _kpi(
            'nfe_entrada_propria',
            'Entrada própria',
            entrada_propria,
            link='/nfe-entrada?tipo_origem=entrada_propria',
        ),
        _kpi('cte_historico_importado', 'CT-e importados', cte_historico, link='/central-dfe'),
    ]

    status_rows = pc_all.values('status').annotate(total=Count('id')).order_by('-total')[:8]
    out['graficos'].append(
        _chart(
            'pc_por_status',
            'Pedidos de compra por status',
            'bar',
            [{'label': r['status'] or '—', 'valor': r['total']} for r in status_rows],
        ),
    )

    evolucao = (
        _filtro_periodo_data(PedidoCompra.objects.all(), f)
        .annotate(mes=TruncMonth('data'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    out['graficos'].append(
        _chart(
            'compras_periodo',
            'Compras por período',
            'line',
            [{'label': (r['mes'].strftime('%m/%Y') if r['mes'] else '—'), 'valor': r['total']} for r in evolucao],
        ),
    )

    top_forn = (
        PedidoCompra.objects.filter(fornecedor_id__isnull=False)
        .values('fornecedor__razao_social')
        .annotate(total=Sum('valor_total'))
        .order_by('-total')[:RANKING_LIMIT]
    )
    out['rankings'].append(
        _ranking(
            'top_fornecedores',
            'Top fornecedores por valor',
            [{'label': r['fornecedor__razao_social'] or '—', 'valor': str(_dec(r['total'])), 'link': '/pedidos-compra'} for r in top_forn],
        ),
    )

    antigos = pc_all.filter(status__icontains='ABERT').order_by('data')[:RANKING_LIMIT]
    out['rankings'].append(
        _ranking(
            'pc_antigos_abertos',
            'Pedidos abertos mais antigos',
            [{'label': p.numero, 'valor': p.data.isoformat(), 'link': f'/pedidos-compra?pedido={p.pk}'} for p in antigos],
        ),
    )

    for p in PedidoCompra.objects.select_related('fornecedor').order_by('-data', '-id')[:ULTIMOS_LIMIT]:
        out['ultimos'].append(
            {
                'tipo': 'pedido_compra',
                'titulo': p.numero,
                'subtitulo': p.fornecedor.razao_social if p.fornecedor_id else '',
                'valor': str(_dec(p.valor_total)),
                'status': p.status or '',
                'data': p.data.isoformat(),
                'link': '/pedidos-compra',
            },
        )

    if abertos:
        out['alertas'].append(
            _alerta('compras', 'aviso', 'Pedidos em aberto', f'{abertos} pedido(s) de compra aberto(s).', '/pedidos-compra?status=aberto'),
        )

    return out


# ---------------------------------------------------------------------------
# Qualidade
# ---------------------------------------------------------------------------


def montar_bi_qualidade(f: DashboardFilters) -> dict:
    out = _base_bi('qualidade', f)
    pend = resumo_pendencias_qualidade()
    cq_qs = CertificadoQualidade.objects.all()

    out['hero_kpi_id'] = 'cq_rastreabilidade_pendente' if pend['cq_rastreabilidade_pendente'] else 'cq_rascunho'

    out['kpis'] = [
        _kpi('cq_emitidos', 'Certificados emitidos', pend['cq_emitidos'], link='/certificados'),
        _kpi('cq_rascunho', 'CQ em rascunho', pend['cq_rascunho'], link='/certificados?status=rascunho'),
        _kpi(
            'cq_rastreabilidade_pendente',
            'CQ com rastreabilidade pendente',
            pend['cq_rastreabilidade_pendente'],
            link='/certificados?status=rascunho',
        ),
        _kpi(
            'itens_rastreabilidade_pendente',
            'Itens CQ pendentes',
            pend['itens_rastreabilidade_pendente'],
            link='/certificados?status=rascunho',
        ),
        _kpi('cf_rascunho', 'CF fornecedor em rascunho', pend['cf_rascunho'], link='/certificados-fornecedor'),
        _kpi('cf_registrados', 'CF fornecedor registrados', pend['cf_registrados'], link='/certificados-fornecedor'),
        _kpi('corridas_lotes', 'Corridas / lotes', pend['corridas'], link='/corridas'),
        _kpi('pendencias_total', 'Pendências totais', pend['pendencias_total']),
    ]

    cq_status = cq_qs.values('status').annotate(total=Count('id')).order_by('-total')
    out['graficos'].append(
        _chart(
            'cert_por_status',
            'Certificados CQ por status',
            'donut',
            [{'label': r['status'] or '—', 'valor': r['total']} for r in cq_status],
        ),
    )

    pendencias_chart = [
        {'label': 'CQ rascunho', 'valor': pend['cq_rascunho']},
        {'label': 'CQ rastreab. pend.', 'valor': pend['cq_rastreabilidade_pendente']},
        {'label': 'CF rascunho', 'valor': pend['cf_rascunho']},
        {'label': 'Itens pendentes', 'valor': pend['itens_rastreabilidade_pendente']},
    ]
    out['graficos'].append(_chart('pendencias_qualidade', 'Pendências de qualidade', 'donut', pendencias_chart))

    evolucao = (
        _filtro_periodo_data(cq_qs, f, 'data_emissao')
        .annotate(mes=TruncMonth('data_emissao'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    out['graficos'].append(
        _chart(
            'cert_periodo',
            'Certificados no período',
            'line',
            [{'label': (r['mes'].strftime('%m/%Y') if r['mes'] else '—'), 'valor': r['total']} for r in evolucao],
        ),
    )

    top_prod = (
        cq_qs.filter(itens__produto_id__isnull=False)
        .values('itens__produto__descricao')
        .annotate(total=Count('id', distinct=True))
        .order_by('-total')[:RANKING_LIMIT]
    )
    out['rankings'].append(
        _ranking(
            'top_produtos_cert',
            'Produtos com mais certificados',
            [{'label': r['itens__produto__descricao'] or '—', 'valor': str(r['total']), 'link': '/certificados'} for r in top_prod],
        ),
    )

    for c in cq_qs.order_by('-criado_em')[:ULTIMOS_LIMIT]:
        out['ultimos'].append(
            {
                'tipo': 'certificado_qualidade',
                'titulo': c.numero or f'CQ #{c.pk}',
                'subtitulo': c.cliente_nome_snapshot or '',
                'valor': '',
                'status': c.status,
                'data': c.data_emissao.isoformat() if c.data_emissao else '',
                'link': '/certificados',
            },
        )

    if pend['cq_rascunho']:
        out['alertas'].append(
            _alerta(
                'qualidade',
                'aviso',
                'CQ em rascunho',
                f"{pend['cq_rascunho']} certificado(s) de qualidade em rascunho.",
                '/certificados?status=rascunho',
            ),
        )
    if pend['cq_rastreabilidade_pendente']:
        out['alertas'].append(
            _alerta(
                'qualidade',
                'critico',
                'Rastreabilidade pendente',
                f"{pend['cq_rastreabilidade_pendente']} CQ com itens de rastreabilidade pendente.",
                '/certificados?status=rascunho',
            ),
        )
    if pend['cf_rascunho']:
        out['alertas'].append(
            _alerta(
                'qualidade',
                'aviso',
                'CF fornecedor em rascunho',
                f"{pend['cf_rascunho']} certificado(s) de fornecedor em rascunho.",
                '/certificados-fornecedor',
            ),
        )

    return out


# ---------------------------------------------------------------------------
# Expedição
# ---------------------------------------------------------------------------

_STATUS_EXPEDICAO_LABEL = dict(StatusExpedicao.choices)
_TIPO_OPERACAO_LABEL = dict(TipoOperacaoExpedicao.choices)


def _hero_kpi_id_expedicao(*, ocorrencia: int, em_andamento: int) -> str:
    if ocorrencia > 0:
        return 'exp_ocorrencia'
    if em_andamento > 0:
        return 'exp_em_andamento'
    return 'exp_total'


def montar_bi_expedicao(f: DashboardFilters) -> dict:
    out = _base_bi('expedicao', f)
    resumo = resumo_expedicoes_por_status()
    em_andamento = (
        resumo['aguardando_separacao']
        + resumo['aguardando_retirada_fornecedor']
        + resumo['motorista_enviado']
        + resumo['em_transito']
    )

    out['hero_kpi_id'] = _hero_kpi_id_expedicao(
        ocorrencia=resumo['ocorrencia'],
        em_andamento=em_andamento,
    )
    out['kpis'] = [
        _kpi('exp_total', 'Total de expedições', resumo['total'], link='/expedicao'),
        _kpi('exp_em_andamento', 'Em andamento', em_andamento, link='/expedicao'),
        _kpi(
            'exp_aguardando_separacao',
            'Aguardando separação',
            resumo['aguardando_separacao'],
            link='/expedicao?status=AGUARDANDO_SEPARACAO',
        ),
        _kpi(
            'exp_aguardando_retirada',
            'Aguardando retirada',
            resumo['aguardando_retirada_fornecedor'],
            link='/expedicao?status=AGUARDANDO_RETIRADA_FORNECEDOR',
        ),
        _kpi(
            'exp_motorista_enviado',
            'Motorista enviado',
            resumo['motorista_enviado'],
            link='/expedicao?status=MOTORISTA_ENVIADO',
        ),
        _kpi('exp_em_transito', 'Em trânsito', resumo['em_transito'], link='/expedicao?status=EM_TRANSITO'),
        _kpi(
            'exp_entregue',
            'Entregues ao cliente',
            resumo['entregue_cliente'],
            link='/expedicao?status=ENTREGUE_CLIENTE',
        ),
        _kpi('exp_ocorrencia', 'Ocorrências', resumo['ocorrencia'], link='/expedicao?status=OCORRENCIA'),
        _kpi('exp_cancelado', 'Canceladas', resumo['cancelado'], link='/expedicao?status=CANCELADO'),
    ]

    status_chart = [
        {'label': _STATUS_EXPEDICAO_LABEL.get(status, status), 'valor': total}
        for status, total in sorted(resumo['por_status'].items(), key=lambda x: -x[1])
        if total > 0
    ][:10]
    out['graficos'].append(_chart('expedicoes_por_status', 'Expedições por status', 'bar', status_chart))

    tipo_rows = (
        Expedicao.objects.values('tipo_operacao')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )
    out['graficos'].append(
        _chart(
            'expedicoes_por_tipo',
            'Expedições por tipo de operação',
            'donut',
            [
                {
                    'label': _TIPO_OPERACAO_LABEL.get(r['tipo_operacao'], r['tipo_operacao'] or '—'),
                    'valor': r['total'],
                }
                for r in tipo_rows
            ],
        ),
    )

    exp_periodo = Expedicao.objects.filter(
        criado_em__date__gte=f.data_inicio,
        criado_em__date__lte=f.data_fim,
    )
    evolucao = (
        exp_periodo.annotate(mes=TruncMonth('criado_em'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    out['graficos'].append(
        _chart(
            'expedicoes_periodo',
            'Expedições no período',
            'line',
            [{'label': (r['mes'].strftime('%m/%Y') if r['mes'] else '—'), 'valor': r['total']} for r in evolucao],
        ),
    )

    top_clientes = (
        Expedicao.objects.filter(cliente_id__isnull=False)
        .values('cliente__razao_social')
        .annotate(total=Count('id'))
        .order_by('-total')[:RANKING_LIMIT]
    )
    out['rankings'].append(
        _ranking(
            'top_clientes_expedicao',
            'Clientes com mais expedições',
            [
                {
                    'label': r['cliente__razao_social'] or '—',
                    'valor': str(r['total']),
                    'link': '/expedicao',
                }
                for r in top_clientes
            ],
        ),
    )

    atrasadas = Expedicao.objects.filter(
        data_prevista_entrega__lt=timezone.localdate(),
    ).exclude(
        status__in=(
            StatusExpedicao.ENTREGUE_CLIENTE,
            StatusExpedicao.CANCELADO,
        ),
    ).count()
    if atrasadas:
        out['rankings'].append(
            _ranking(
                'expedicoes_atrasadas',
                'Entregas previstas atrasadas',
                [{'label': 'Total atrasadas', 'valor': str(atrasadas), 'link': '/expedicao'}],
            ),
        )

    for exp in Expedicao.objects.select_related('cliente', 'fornecedor').order_by('-criado_em')[:ULTIMOS_LIMIT]:
        out['ultimos'].append(
            {
                'tipo': 'expedicao',
                'titulo': exp.codigo,
                'subtitulo': (
                    exp.cliente.razao_social
                    if exp.cliente_id
                    else (exp.fornecedor.razao_social if exp.fornecedor_id else '')
                ),
                'valor': '',
                'status': _STATUS_EXPEDICAO_LABEL.get(exp.status, exp.status),
                'data': exp.criado_em.date().isoformat() if exp.criado_em else '',
                'link': f'/expedicao?expedicao={exp.pk}',
            },
        )

    if resumo['ocorrencia']:
        out['alertas'].append(
            _alerta(
                'expedicao',
                'critico',
                'Ocorrências em expedição',
                f"{resumo['ocorrencia']} expedição(ões) com ocorrência.",
                '/expedicao?status=OCORRENCIA',
            ),
        )
    if resumo['aguardando_separacao']:
        out['alertas'].append(
            _alerta(
                'expedicao',
                'aviso',
                'Aguardando separação',
                f"{resumo['aguardando_separacao']} expedição(ões) aguardando separação.",
                '/expedicao?status=AGUARDANDO_SEPARACAO',
            ),
        )
    if atrasadas:
        out['alertas'].append(
            _alerta(
                'expedicao',
                'aviso',
                'Entregas atrasadas',
                f'{atrasadas} expedição(ões) com data prevista vencida.',
                '/expedicao',
            ),
        )

    return out


# ---------------------------------------------------------------------------
# Financeiro (resumo operacional — ERP 4.0.14.5)
# ---------------------------------------------------------------------------

_ALERTA_FIN_LINKS = {
    'titulos_vencidos': '/financeiro',
    'vencendo_hoje': '/financeiro',
    'origem_fiscal_cancelada': '/financeiro/contas-receber?origem_fiscal_cancelada=1',
    'sem_categoria': '/financeiro/contas-receber?sem_categoria=1',
    'sem_conta_prevista': '/financeiro/contas-receber?sem_conta_prevista=1',
    'creditos_disponiveis': '/financeiro/creditos',
}

_ALERTA_FIN_TITULOS = {
    'titulos_vencidos': 'Títulos vencidos',
    'vencendo_hoje': 'Vencendo hoje',
    'origem_fiscal_cancelada': 'Origem fiscal cancelada',
    'sem_categoria': 'Sem categoria',
    'sem_conta_prevista': 'Sem conta prevista',
    'creditos_disponiveis': 'Créditos disponíveis',
}


def montar_bi_financeiro(f: DashboardFilters) -> dict:
    from apps.financeiro.resumo import montar_resumo_financeiro

    resumo = montar_resumo_financeiro(
        periodo='personalizado',
        data_inicio=f.data_inicio.isoformat(),
        data_fim=f.data_fim.isoformat(),
    )
    rec = resumo['receber']
    pag = resumo['pagar']
    saldo = resumo['saldo_previsto']['em_aberto']
    periodo_curto = f.label if f.periodo != 'mes_atual' else 'no período'

    out = _base_bi('financeiro', f)
    out['em_preparacao'] = False
    out['kpis'] = [
        _kpi('saldo_previsto', 'Saldo previsto em aberto', saldo, 'moeda', '/financeiro'),
        _kpi(
            'cr_aberto',
            'A receber em aberto',
            rec['em_aberto']['valor'],
            'moeda',
            '/financeiro/contas-receber?saldo_aberto=1',
        ),
        _kpi(
            'cp_aberto',
            'A pagar em aberto',
            pag['em_aberto']['valor'],
            'moeda',
            '/financeiro/contas-pagar?saldo_aberto=1',
        ),
        _kpi(
            'cr_vencido',
            'A receber vencido',
            rec['vencido']['valor'],
            'moeda',
            '/financeiro/contas-receber?vencimento=vencidos',
            subtitulo=f"{rec['vencido']['quantidade']} título(s)",
        ),
        _kpi(
            'cp_vencido',
            'A pagar vencido',
            pag['vencido']['valor'],
            'moeda',
            '/financeiro/contas-pagar?vencimento=vencidos',
            subtitulo=f"{pag['vencido']['quantidade']} título(s)",
        ),
        _kpi(
            'recebido_periodo',
            f'Recebido {periodo_curto}',
            rec['recebido_periodo']['valor'],
            'moeda',
            '/financeiro/contas-receber?status=recebido',
        ),
        _kpi(
            'pago_periodo',
            f'Pago {periodo_curto}',
            pag['pago_periodo']['valor'],
            'moeda',
            '/financeiro/contas-pagar?status=pago',
        ),
    ]
    out['links'] = [
        {
            'id': 'visao_financeiro',
            'titulo': 'Visão geral financeira',
            'descricao': 'Vencimentos, saldo previsto, alertas e resumo por conta/categoria.',
            'link': '/financeiro',
        },
        {
            'id': 'contas_receber',
            'titulo': 'Contas a Receber',
            'descricao': 'Títulos em aberto, vencidos e recebimentos.',
            'link': '/financeiro/contas-receber',
        },
        {
            'id': 'contas_pagar',
            'titulo': 'Contas a Pagar',
            'descricao': 'Títulos em aberto, vencidos e pagamentos.',
            'link': '/financeiro/contas-pagar',
        },
        {
            'id': 'creditos',
            'titulo': 'Créditos',
            'descricao': 'Créditos de clientes e fornecedores disponíveis para aplicar.',
            'link': '/financeiro/creditos',
        },
    ]

    for alerta in resumo.get('alertas', []):
        codigo = alerta.get('codigo', '')
        sev = 'critico' if codigo in ('titulos_vencidos', 'origem_fiscal_cancelada') else 'aviso'
        titulo = _ALERTA_FIN_TITULOS.get(codigo, 'Financeiro')
        out['alertas'].append(
            _alerta(
                'financeiro',
                sev,
                titulo,
                alerta.get('mensagem', ''),
                _ALERTA_FIN_LINKS.get(codigo, '/financeiro'),
            ),
        )

    return out


# ---------------------------------------------------------------------------
# Home personalizada
# ---------------------------------------------------------------------------

MODULO_BUILDERS = {
    'comercial': montar_bi_comercial,
    'fiscal': montar_bi_fiscal,
    'estoque': montar_bi_estoque,
    'expedicao': montar_bi_expedicao,
    'compras': montar_bi_compras,
    'qualidade': montar_bi_qualidade,
    'financeiro': montar_bi_financeiro,
}

MODULO_TITULOS = {
    'comercial': 'Comercial',
    'fiscal': 'Fiscal',
    'estoque': 'Estoque',
    'expedicao': 'Expedição',
    'compras': 'Compras',
    'qualidade': 'Qualidade',
    'financeiro': 'Financeiro',
}


def _resumir_modulo_home(bi: dict) -> dict:
    kpis = bi.get('kpis', [])[:4]
    alerta = bi.get('alertas', [None])[0] if bi.get('alertas') else None
    modulo = bi['modulo']
    link_bi = '/financeiro' if modulo == 'financeiro' else f'/dashboard/{modulo}'
    return {
        'modulo': modulo,
        'titulo': MODULO_TITULOS.get(modulo, modulo),
        'kpis': kpis,
        'alerta_principal': alerta,
        'link_bi': link_bi,
        'hero_kpi_id': bi.get('hero_kpi_id'),
    }


def montar_dashboard_home(user, f: DashboardFilters) -> dict:
    permitidos = modulos_permitidos(user)
    modulos = []
    alertas: list[dict] = []

    for modulo in permitidos:
        builder = MODULO_BUILDERS[modulo]
        bi = builder(f)
        modulos.append(_resumir_modulo_home(bi))
        alertas.extend(bi.get('alertas', []))

    return {
        'periodo': periodo_dict(f),
        'permissoes': permissoes_dashboard(user),
        'modulos': modulos,
        'alertas': alertas[:10],
        'nenhum_modulo': len(modulos) == 0,
        'gerado_em': timezone.now().isoformat(),
    }
