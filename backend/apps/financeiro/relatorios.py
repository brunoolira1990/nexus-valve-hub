"""Relatórios financeiros operacionais — ERP 4.0.14.6 (somente leitura)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Max, QuerySet, Sum
from django.utils import timezone

from apps.financeiro.filtragem import (
    aplicar_filtros_exibicao_relatorio,
    aplicar_filtros_titulo,
    param_flag,
    queryset_metricas_ativas,
    resolver_periodo,
)
from apps.financeiro.models import BaixaFinanceira, TituloFinanceiro
from apps.financeiro.serializers import _titulo_origem_exibicao, status_label
from apps.financeiro.status import CENTAVO, calcular_status_titulo
from apps.financeiro.vencimento_exibicao import vencimento_exibicao_titulo

def _hoje() -> date:
    return timezone.localdate()


def _dec_str(v: Decimal | None) -> str:
    return str((v or Decimal('0')).quantize(Decimal('0.01')))


def _metrica_valor_qs(qs: QuerySet, campo: str = 'valor_aberto') -> dict[str, Any]:
    agg = qs.aggregate(total=Sum(campo), quantidade=Count('id'))
    return {
        'valor': _dec_str(agg['total']),
        'quantidade': agg['quantidade'] or 0,
    }


def _periodo_resposta(params, *, padrao: str = 'mes') -> dict[str, str]:
    periodo = (params.get('periodo') or padrao).strip().lower()
    ini, fim = resolver_periodo(
        periodo,
        data_inicio=params.get('data_inicio') or params.get('vencimento_de'),
        data_fim=params.get('data_fim') or params.get('vencimento_ate'),
    )
    return {
        'periodo': periodo,
        'data_inicio': ini.isoformat(),
        'data_fim': fim.isoformat(),
    }


def _periodo_baixa(params) -> tuple[date, date]:
    periodo = (params.get('periodo_baixa') or params.get('periodo') or 'mes').strip().lower()
    return resolver_periodo(
        periodo,
        data_inicio=params.get('baixa_de') or params.get('data_inicio'),
        data_fim=params.get('baixa_ate') or params.get('data_fim'),
    )


def _qs_base(tipo: str) -> QuerySet:
    return TituloFinanceiro.objects.filter(tipo=tipo).select_related(
        'cliente',
        'fornecedor',
        'categoria',
        'centro_custo',
        'conta_financeira_prevista',
    )


AVISO_HISTORICO = (
    'Este relatório inclui títulos quitados ou cancelados. '
    'Eles aparecem para histórico e não representam saldo em aberto.'
)


def _aviso_historico(params) -> str | None:
    if param_flag(params, 'incluir_cancelados') or param_flag(params, 'incluir_quitados'):
        return AVISO_HISTORICO
    return None


def _filtrar(qs: QuerySet, params, tipo: str) -> QuerySet:
    qs = aplicar_filtros_titulo(qs, params)
    qs = aplicar_filtros_exibicao_relatorio(qs, params, tipo=tipo)
    return qs.order_by('data_vencimento', 'numero', 'id')


def _filtrar_sem_exibicao(qs: QuerySet, params) -> QuerySet:
    return aplicar_filtros_titulo(qs, params)


def _incluir_resumo_contraparte(row: dict, params) -> bool:
    if param_flag(params, 'incluir_sem_saldo'):
        return True
    aberto = Decimal(row['total_aberto'])
    vencido = Decimal(row['total_vencido'])
    periodo = Decimal(
        row.get('recebido_periodo') or row.get('pago_periodo') or '0',
    )
    return aberto > CENTAVO or vencido > CENTAVO or periodo > CENTAVO


def _status_operacional(titulo: TituloFinanceiro, hoje: date | None = None) -> str:
    hoje = hoje or _hoje()
    return calcular_status_titulo(
        tipo=titulo.tipo,
        valor_original=titulo.valor_original,
        valor_aberto=titulo.valor_aberto,
        valor_baixado=titulo.valor_baixado,
        data_vencimento=titulo.data_vencimento,
        cancelado=titulo.cancelado,
        hoje=hoje,
    )


def _linha_titulo(titulo: TituloFinanceiro, *, modo: str, hoje: date) -> dict[str, Any]:
    st = _status_operacional(titulo, hoje)
    counterparty = ''
    if modo == TituloFinanceiro.Tipo.RECEBER:
        counterparty = (titulo.cliente.razao_social if titulo.cliente_id else '') or ''
    else:
        if titulo.fornecedor_id:
            counterparty = titulo.fornecedor.razao_social
        elif (titulo.descricao or '').strip():
            counterparty = titulo.descricao.strip()

    from apps.fiscal.nfe_entrada_financeiro import titulo_origem_nfe_entrada_cancelada
    from apps.fiscal.nfe_saida_financeiro import titulo_origem_nfe_cancelada

    origem_cancelada = titulo_origem_nfe_cancelada(titulo) or titulo_origem_nfe_entrada_cancelada(titulo)
    pode_baixar = not titulo.cancelado and (titulo.valor_aberto or Decimal('0')) > CENTAVO
    ven = vencimento_exibicao_titulo(titulo, hoje=hoje)

    return {
        'id': titulo.id,
        'vencimento': ven['vencimento'] or titulo.data_vencimento.isoformat(),
        'vencimento_exibicao': ven['vencimento'],
        'vencimento_label': ven['vencimento_label'],
        'vencimento_ausente': ven['vencimento_ausente'],
        'emissao': titulo.data_emissao.isoformat(),
        'cliente_nome': (titulo.cliente.razao_social if titulo.cliente_id else '') or None,
        'fornecedor_nome': (titulo.fornecedor.razao_social if titulo.fornecedor_id else None),
        'descricao': (titulo.descricao or '').strip() or None,
        'tipo_lancamento': titulo.tipo_lancamento or None,
        'tipo_lancamento_label': titulo.get_tipo_lancamento_display() if titulo.tipo_lancamento else None,
        'documento': (titulo.numero or '').strip() or '—',
        'origem': _titulo_origem_exibicao(titulo),
        'origem_tipo': titulo.origem_tipo,
        'valor_original': _dec_str(titulo.valor_original),
        'valor_baixado': _dec_str(titulo.valor_baixado),
        'saldo': _dec_str(titulo.valor_aberto),
        'status': st,
        'status_label': status_label(st),
        'categoria_nome': (titulo.categoria.nome if titulo.categoria_id else None),
        'centro_custo_nome': (titulo.centro_custo.nome if titulo.centro_custo_id else None),
        'conta_prevista_nome': (
            titulo.conta_financeira_prevista.nome if titulo.conta_financeira_prevista_id else None
        ),
        'origem_fiscal_cancelada': origem_cancelada,
        'pode_baixar': pode_baixar,
        'cliente_id': titulo.cliente_id,
        'fornecedor_id': titulo.fornecedor_id,
    }


def _cards_cr_cp(qs_listagem: QuerySet, tipo: str, params, hoje: date) -> dict[str, Any]:
    qs_ativas = queryset_metricas_ativas(qs_listagem)
    vencido_qs = qs_ativas.filter(data_vencimento__lt=hoje)
    parcial_st = (
        TituloFinanceiro.Status.PARCIALMENTE_RECEBIDO
        if tipo == TituloFinanceiro.Tipo.RECEBER
        else TituloFinanceiro.Status.PARCIALMENTE_PAGO
    )
    parcial_qs = qs_listagem.filter(status=parcial_st, cancelado=False, valor_aberto__gt=CENTAVO)
    periodo_ini, periodo_fim = _periodo_baixa(params)
    qs_baixa_escopo = _filtrar_sem_exibicao(_qs_base(tipo), params).filter(cancelado=False)
    baixas = BaixaFinanceira.objects.filter(
        titulo__in=qs_baixa_escopo,
        estornada=False,
        data_baixa__gte=periodo_ini,
        data_baixa__lte=periodo_fim,
    )
    recebido_pago = baixas.aggregate(t=Sum('valor'))['t'] or Decimal('0')
    tributos = Decimal('0')
    if tipo == TituloFinanceiro.Tipo.PAGAR:
        trib_qs = qs_ativas.filter(tipo_lancamento=TituloFinanceiro.TipoLancamentoPagar.TRIBUTO_IMPOSTO)
        tributos = trib_qs.aggregate(t=Sum('valor_aberto'))['t'] or Decimal('0')

    label_periodo = 'recebido_periodo' if tipo == TituloFinanceiro.Tipo.RECEBER else 'pago_periodo'
    return {
        'total_aberto': _metrica_valor_qs(qs_ativas),
        'total_vencido': _metrica_valor_qs(vencido_qs),
        label_periodo: {
            'valor': _dec_str(recebido_pago),
            'quantidade': baixas.values('titulo_id').distinct().count(),
        },
        'total_parcial': _metrica_valor_qs(parcial_qs, 'valor_aberto'),
        'total_tributos': {'valor': _dec_str(tributos), 'quantidade': 0},
        'quantidade_titulos': qs_listagem.count(),
    }


def _agrupar_linhas(linhas: list[dict], agrupamento: str, modo: str) -> list[dict]:
    if not agrupamento:
        return []
    buckets: dict[str, dict] = {}
    for ln in linhas:
        if agrupamento == 'cliente':
            key = str(ln.get('cliente_id') or 'sem_cliente')
            label = ln.get('cliente_nome') or 'Sem cliente'
        elif agrupamento == 'fornecedor':
            key = str(ln.get('fornecedor_id') or ln.get('descricao') or 'sem_fornecedor')
            label = ln.get('fornecedor_nome') or ln.get('descricao') or 'Sem fornecedor'
        elif agrupamento == 'categoria':
            key = ln.get('categoria_nome') or 'sem_categoria'
            label = key
        elif agrupamento == 'origem':
            key = ln.get('origem_tipo') or 'MANUAL'
            label = ln.get('origem') or key
        elif agrupamento == 'vencimento_mes':
            key = (ln.get('vencimento') or '')[:7]
            label = key
        elif agrupamento == 'tipo' and modo == TituloFinanceiro.Tipo.PAGAR:
            key = ln.get('tipo_lancamento') or 'OUTROS'
            label = ln.get('tipo_lancamento_label') or key
        else:
            continue
        if key not in buckets:
            buckets[key] = {
                'chave': key,
                'titulo': label,
                'quantidade': 0,
                'valor_original': Decimal('0'),
                'saldo': Decimal('0'),
            }
        buckets[key]['quantidade'] += 1
        buckets[key]['valor_original'] += Decimal(ln['valor_original'])
        buckets[key]['saldo'] += Decimal(ln['saldo'])

    out = []
    for b in buckets.values():
        out.append(
            {
                'chave': b['chave'],
                'titulo': b['titulo'],
                'quantidade': b['quantidade'],
                'valor_original': _dec_str(b['valor_original']),
                'saldo': _dec_str(b['saldo']),
            },
        )
    out.sort(key=lambda x: Decimal(x['saldo']), reverse=True)
    return out


def relatorio_contas_receber(params) -> dict[str, Any]:
    hoje = _hoje()
    tipo = TituloFinanceiro.Tipo.RECEBER
    qs = _filtrar(_qs_base(tipo), params, tipo)
    linhas = [_linha_titulo(t, modo=tipo, hoje=hoje) for t in qs[:2000]]
    agrupamento = (params.get('agrupamento') or '').strip().lower()
    return {
        'tipo': 'contas_receber',
        'periodo': _periodo_resposta(params),
        'aviso_historico': _aviso_historico(params),
        'cards': _cards_cr_cp(qs, tipo, params, hoje),
        'linhas': linhas,
        'agrupamentos': _agrupar_linhas(linhas, agrupamento, tipo),
    }


def relatorio_contas_pagar(params) -> dict[str, Any]:
    hoje = _hoje()
    tipo = TituloFinanceiro.Tipo.PAGAR
    qs = _filtrar(_qs_base(tipo), params, tipo)
    linhas = [_linha_titulo(t, modo=tipo, hoje=hoje) for t in qs[:2000]]
    agrupamento = (params.get('agrupamento') or '').strip().lower()
    return {
        'tipo': 'contas_pagar',
        'periodo': _periodo_resposta(params),
        'aviso_historico': _aviso_historico(params),
        'cards': _cards_cr_cp(qs, tipo, params, hoje),
        'linhas': linhas,
        'agrupamentos': _agrupar_linhas(linhas, agrupamento, tipo),
    }


def _resolver_periodo_fluxo(params) -> tuple[date, date]:
    periodo = (params.get('periodo') or 'proximos_30').strip().lower()
    return resolver_periodo(
        periodo,
        data_inicio=params.get('data_inicio'),
        data_fim=params.get('data_fim'),
    )


def relatorio_fluxo_previsto(params) -> dict[str, Any]:
    """Fluxo previsto: títulos em aberto por data de vencimento (não é conciliação bancária).

    Títulos vencidos com vencimento anterior ao início do período são projetados no primeiro dia
    do período para facilitar a leitura do saldo acumulado.
    """
    hoje = _hoje()
    ini, fim = _resolver_periodo_fluxo(params)
    qs = TituloFinanceiro.objects.filter(cancelado=False, valor_aberto__gt=CENTAVO).exclude(
        status__in=(
            TituloFinanceiro.Status.RECEBIDO,
            TituloFinanceiro.Status.PAGO,
            TituloFinanceiro.Status.CANCELADO,
        ),
    )
    if params.get('categoria'):
        qs = qs.filter(categoria_id=int(params['categoria']))
    if params.get('centro_custo'):
        qs = qs.filter(centro_custo_id=int(params['centro_custo']))
    conta = params.get('conta_financeira_prevista') or params.get('conta_prevista')
    if conta:
        qs = qs.filter(conta_financeira_prevista_id=int(conta))

    por_dia: dict[date, dict[str, Decimal]] = defaultdict(
        lambda: {'receber': Decimal('0'), 'pagar': Decimal('0')},
    )
    total_receber = Decimal('0')
    total_pagar = Decimal('0')

    for titulo in qs.iterator():
        dv = titulo.data_vencimento
        if dv < ini:
            dv = ini
        if dv > fim:
            continue
        val = titulo.valor_aberto or Decimal('0')
        if titulo.tipo == TituloFinanceiro.Tipo.RECEBER:
            por_dia[dv]['receber'] += val
            total_receber += val
        else:
            por_dia[dv]['pagar'] += val
            total_pagar += val

    dias_ordenados = sorted(por_dia.keys())
    if not dias_ordenados and ini <= fim:
        dias_ordenados = [ini]

    linhas_fluxo = []
    acumulado = Decimal('0')
    maior_entrada = {'data': None, 'valor': Decimal('0')}
    maior_saida = {'data': None, 'valor': Decimal('0')}

    cur = ini
    while cur <= fim:
        rec = por_dia.get(cur, {}).get('receber', Decimal('0'))
        pag = por_dia.get(cur, {}).get('pagar', Decimal('0'))
        saldo_dia = rec - pag
        acumulado += saldo_dia
        if rec > maior_entrada['valor']:
            maior_entrada = {'data': cur.isoformat(), 'valor': rec}
        if pag > maior_saida['valor']:
            maior_saida = {'data': cur.isoformat(), 'valor': pag}
        if rec > CENTAVO or pag > CENTAVO or cur in por_dia:
            linhas_fluxo.append(
                {
                    'data': cur.isoformat(),
                    'a_receber': _dec_str(rec),
                    'a_pagar': _dec_str(pag),
                    'saldo_dia': _dec_str(saldo_dia),
                    'saldo_acumulado': _dec_str(acumulado),
                },
            )
        cur += timedelta(days=1)

    return {
        'tipo': 'fluxo_previsto',
        'nota': (
            'Previsão com títulos em aberto por vencimento. Não é conciliação bancária. '
            'Cancelados e quitados não entram. Vencidos antes do período aparecem no primeiro dia.'
        ),
        'periodo': {'periodo': params.get('periodo') or 'proximos_30', 'data_inicio': ini.isoformat(), 'data_fim': fim.isoformat()},
        'cards': {
            'total_receber': {'valor': _dec_str(total_receber), 'quantidade': 0},
            'total_pagar': {'valor': _dec_str(total_pagar), 'quantidade': 0},
            'saldo_previsto': {'valor': _dec_str(total_receber - total_pagar), 'quantidade': 0},
            'maior_entrada': {
                'valor': _dec_str(maior_entrada['valor']),
                'data': maior_entrada['data'],
            },
            'maior_saida': {
                'valor': _dec_str(maior_saida['valor']),
                'data': maior_saida['data'],
            },
        },
        'linhas': linhas_fluxo,
    }


def relatorio_categorias(params) -> dict[str, Any]:
    periodo_ini, periodo_fim = _periodo_baixa(params)
    st_filtro = (params.get('status') or '').strip().lower()

    def _filtra_status(qs):
        if st_filtro == 'aberto':
            return qs.filter(cancelado=False, valor_aberto__gt=CENTAVO)
        if st_filtro in ('baixado', 'recebido_pago'):
            return qs.filter(cancelado=False, valor_baixado__gt=CENTAVO)
        return qs

    receitas = []
    despesas = []
    sem_classificacao = {'receitas': 0, 'despesas': 0}

    for tipo_titulo, destino, tipo_label in (
        (TituloFinanceiro.Tipo.RECEBER, receitas, 'Receita'),
        (TituloFinanceiro.Tipo.PAGAR, despesas, 'Despesa'),
    ):
        qs = _filtra_status(_qs_base(tipo_titulo))
        qs = aplicar_filtros_titulo(qs, params)
        qs = aplicar_filtros_exibicao_relatorio(qs, params, tipo=tipo_titulo)

        rows = qs.values('categoria_id', 'categoria__nome').annotate(
            qtd=Count('id'),
            aberto=Sum('valor_aberto'),
            original=Sum('valor_original'),
        )
        for row in rows:
            nome = row['categoria__nome'] or 'Sem categoria'
            if not row['categoria_id']:
                sem_classificacao['receitas' if tipo_titulo == TituloFinanceiro.Tipo.RECEBER else 'despesas'] += (
                    row['qtd'] or 0
                )
            baixado_periodo = BaixaFinanceira.objects.filter(
                titulo__tipo=tipo_titulo,
                titulo__categoria_id=row['categoria_id'],
                estornada=False,
                data_baixa__gte=periodo_ini,
                data_baixa__lte=periodo_fim,
            ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            em_aberto = row['aberto'] or Decimal('0')
            original = row['original'] or Decimal('0')
            total_considerado = em_aberto + baixado_periodo
            if not param_flag(params, 'incluir_sem_saldo') and total_considerado <= CENTAVO:
                continue
            item = {
                'categoria_id': row['categoria_id'],
                'categoria_nome': nome,
                'tipo': tipo_label,
                'quantidade': row['qtd'] or 0,
                'valor_original': _dec_str(original),
                'em_aberto': _dec_str(em_aberto),
                'baixado_periodo': _dec_str(baixado_periodo),
                'total_considerado': _dec_str(total_considerado),
                'baixado': _dec_str(baixado_periodo),
                'total': _dec_str(total_considerado),
            }
            destino.append(item)

    total_rec = sum(Decimal(x['total_considerado']) for x in receitas)
    total_desp = sum(Decimal(x['total_considerado']) for x in despesas)
    aberto_rec = sum(Decimal(x['em_aberto']) for x in receitas)
    aberto_desp = sum(Decimal(x['em_aberto']) for x in despesas)

    return {
        'tipo': 'categorias',
        'periodo': {
            'periodo': params.get('periodo') or 'mes',
            'data_inicio': periodo_ini.isoformat(),
            'data_fim': periodo_fim.isoformat(),
        },
        'aviso_historico': _aviso_historico(params),
        'cards': {
            'total_receitas': {'valor': _dec_str(total_rec), 'quantidade': len(receitas)},
            'total_despesas': {'valor': _dec_str(total_desp), 'quantidade': len(despesas)},
            'diferenca_prevista': {'valor': _dec_str(total_rec - total_desp), 'quantidade': 0},
            'sem_classificacao': sem_classificacao,
        },
        'receitas': receitas,
        'despesas': despesas,
        'linhas': receitas + despesas,
    }


def _ultima_baixa(titulo_ids: list[int], tipo: str) -> dict[int, str | None]:
    if not titulo_ids:
        return {}
    rows = (
        BaixaFinanceira.objects.filter(
            titulo_id__in=titulo_ids,
            titulo__tipo=tipo,
            estornada=False,
        )
        .values('titulo_id')
        .annotate(ultima=Max('data_baixa'))
    )
    return {r['titulo_id']: r['ultima'].isoformat() if r['ultima'] else None for r in rows}


def relatorio_clientes(params) -> dict[str, Any]:
    hoje = _hoje()
    tipo = TituloFinanceiro.Tipo.RECEBER
    qs = _filtrar(_qs_base(tipo), params, tipo)
    cliente_id = (params.get('cliente') or params.get('cliente_id') or '').strip()

    if cliente_id:
        linhas = [_linha_titulo(t, modo=TituloFinanceiro.Tipo.RECEBER, hoje=hoje) for t in qs[:2000]]
        ultimas = _ultima_baixa([t.id for t in qs[:500]], TituloFinanceiro.Tipo.RECEBER)
        ultima_data = max(ultimas.values()) if ultimas else None
        aberto_qs = qs.filter(cancelado=False, valor_aberto__gt=CENTAVO)
        vencido_qs = aberto_qs.filter(data_vencimento__lt=hoje)
        periodo_ini, periodo_fim = _periodo_baixa(params)
        recebido = (
            BaixaFinanceira.objects.filter(
                titulo__in=qs,
                estornada=False,
                data_baixa__gte=periodo_ini,
                data_baixa__lte=periodo_fim,
            ).aggregate(t=Sum('valor'))['t']
            or Decimal('0')
        )
        cli = qs.first().cliente if qs.exists() else None
        resumo = [
            {
                'cliente_id': int(cliente_id),
                'cliente_nome': cli.razao_social if cli else 'Cliente',
                'total_aberto': _dec_str(aberto_qs.aggregate(t=Sum('valor_aberto'))['t']),
                'total_vencido': _dec_str(vencido_qs.aggregate(t=Sum('valor_aberto'))['t']),
                'recebido_periodo': _dec_str(recebido),
                'quantidade_titulos': qs.count(),
                'ultimo_recebimento': ultima_data,
            },
        ]
        return {
            'tipo': 'clientes',
            'detalhe_cliente_id': int(cliente_id),
            'periodo': _periodo_resposta(params),
            'aviso_historico': _aviso_historico(params),
            'resumo': resumo,
            'linhas': linhas,
        }

    resumo_map: dict[int, dict] = {}
    for titulo in qs.iterator():
        cid = titulo.cliente_id or 0
        if cid not in resumo_map:
            nome = titulo.cliente.razao_social if titulo.cliente_id else 'Sem cliente'
            resumo_map[cid] = {
                'cliente_id': cid or None,
                'cliente_nome': nome,
                'total_aberto': Decimal('0'),
                'total_vencido': Decimal('0'),
                'quantidade_titulos': 0,
            }
        resumo_map[cid]['quantidade_titulos'] += 1
        if not titulo.cancelado and (titulo.valor_aberto or Decimal('0')) > CENTAVO:
            resumo_map[cid]['total_aberto'] += titulo.valor_aberto
            if titulo.data_vencimento < hoje:
                resumo_map[cid]['total_vencido'] += titulo.valor_aberto

    periodo_ini, periodo_fim = _periodo_baixa(params)
    for cid, row in resumo_map.items():
        if not cid:
            row['recebido_periodo'] = '0.00'
            row['ultimo_recebimento'] = None
            continue
        baixas = BaixaFinanceira.objects.filter(
            titulo__cliente_id=cid,
            titulo__tipo=TituloFinanceiro.Tipo.RECEBER,
            estornada=False,
            data_baixa__gte=periodo_ini,
            data_baixa__lte=periodo_fim,
        )
        row['recebido_periodo'] = _dec_str(baixas.aggregate(t=Sum('valor'))['t'])
        ult = baixas.aggregate(u=Max('data_baixa'))['u']
        row['ultimo_recebimento'] = ult.isoformat() if ult else None

    resumo = []
    for row in resumo_map.values():
        item = {
            'cliente_id': row['cliente_id'],
            'cliente_nome': row['cliente_nome'],
            'total_aberto': _dec_str(row['total_aberto']),
            'total_vencido': _dec_str(row['total_vencido']),
            'recebido_periodo': row.get('recebido_periodo', '0.00'),
            'quantidade_titulos': row['quantidade_titulos'],
            'ultimo_recebimento': row.get('ultimo_recebimento'),
        }
        if _incluir_resumo_contraparte(item, params):
            resumo.append(item)
    resumo.sort(key=lambda x: Decimal(x['total_aberto']), reverse=True)

    return {
        'tipo': 'clientes',
        'periodo': _periodo_resposta(params),
        'aviso_historico': _aviso_historico(params),
        'resumo': resumo,
        'linhas': [],
    }


def relatorio_fornecedores(params) -> dict[str, Any]:
    hoje = _hoje()
    tipo = TituloFinanceiro.Tipo.PAGAR
    qs = _filtrar(_qs_base(tipo), params, tipo)
    fornecedor_id = (params.get('fornecedor') or params.get('fornecedor_id') or '').strip()

    if fornecedor_id:
        linhas = [_linha_titulo(t, modo=TituloFinanceiro.Tipo.PAGAR, hoje=hoje) for t in qs[:2000]]
        ultimas = _ultima_baixa([t.id for t in qs[:500]], TituloFinanceiro.Tipo.PAGAR)
        ultima_data = max((v for v in ultimas.values() if v), default=None)
        aberto_qs = qs.filter(cancelado=False, valor_aberto__gt=CENTAVO)
        vencido_qs = aberto_qs.filter(data_vencimento__lt=hoje)
        periodo_ini, periodo_fim = _periodo_baixa(params)
        pago = (
            BaixaFinanceira.objects.filter(
                titulo__in=qs,
                estornada=False,
                data_baixa__gte=periodo_ini,
                data_baixa__lte=periodo_fim,
            ).aggregate(t=Sum('valor'))['t']
            or Decimal('0')
        )
        forn = qs.first().fornecedor if qs.exists() else None
        resumo = [
            {
                'fornecedor_id': int(fornecedor_id),
                'fornecedor_nome': forn.razao_social if forn else 'Fornecedor',
                'total_aberto': _dec_str(aberto_qs.aggregate(t=Sum('valor_aberto'))['t']),
                'total_vencido': _dec_str(vencido_qs.aggregate(t=Sum('valor_aberto'))['t']),
                'pago_periodo': _dec_str(pago),
                'quantidade_titulos': qs.count(),
                'ultimo_pagamento': ultima_data,
            },
        ]
        return {
            'tipo': 'fornecedores',
            'detalhe_fornecedor_id': int(fornecedor_id),
            'periodo': _periodo_resposta(params),
            'aviso_historico': _aviso_historico(params),
            'resumo': resumo,
            'linhas': linhas,
        }

    resumo_map: dict[int, dict] = {}
    for titulo in qs.iterator():
        fid = titulo.fornecedor_id or 0
        if fid not in resumo_map:
            nome = titulo.fornecedor.razao_social if titulo.fornecedor_id else (titulo.descricao or 'Sem fornecedor')
            resumo_map[fid] = {
                'fornecedor_id': fid or None,
                'fornecedor_nome': nome,
                'total_aberto': Decimal('0'),
                'total_vencido': Decimal('0'),
                'quantidade_titulos': 0,
            }
        resumo_map[fid]['quantidade_titulos'] += 1
        if not titulo.cancelado and (titulo.valor_aberto or Decimal('0')) > CENTAVO:
            resumo_map[fid]['total_aberto'] += titulo.valor_aberto
            if titulo.data_vencimento < hoje:
                resumo_map[fid]['total_vencido'] += titulo.valor_aberto

    periodo_ini, periodo_fim = _periodo_baixa(params)
    for fid, row in resumo_map.items():
        if not fid:
            row['pago_periodo'] = '0.00'
            row['ultimo_pagamento'] = None
            continue
        baixas = BaixaFinanceira.objects.filter(
            titulo__fornecedor_id=fid,
            titulo__tipo=TituloFinanceiro.Tipo.PAGAR,
            estornada=False,
            data_baixa__gte=periodo_ini,
            data_baixa__lte=periodo_fim,
        )
        row['pago_periodo'] = _dec_str(baixas.aggregate(t=Sum('valor'))['t'])
        ult = baixas.aggregate(u=Max('data_baixa'))['u']
        row['ultimo_pagamento'] = ult.isoformat() if ult else None

    resumo = []
    for row in resumo_map.values():
        item = {
            'fornecedor_id': row['fornecedor_id'],
            'fornecedor_nome': row['fornecedor_nome'],
            'total_aberto': _dec_str(row['total_aberto']),
            'total_vencido': _dec_str(row['total_vencido']),
            'pago_periodo': row.get('pago_periodo', '0.00'),
            'quantidade_titulos': row['quantidade_titulos'],
            'ultimo_pagamento': row.get('ultimo_pagamento'),
        }
        if _incluir_resumo_contraparte(item, params):
            resumo.append(item)
    resumo.sort(key=lambda x: Decimal(x['total_aberto']), reverse=True)

    return {
        'tipo': 'fornecedores',
        'periodo': _periodo_resposta(params),
        'aviso_historico': _aviso_historico(params),
        'resumo': resumo,
        'linhas': [],
    }
