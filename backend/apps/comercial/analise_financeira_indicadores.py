"""Indicadores do dossiê interno — Liberação Financeira (schema v2).

Não inventa zeros para dados ausentes. Snapshot imutável na solicitação.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.comercial.faturamento_pedido_venda import (
    STATUS_PEDIDO_CANCELADO,
    STATUS_PEDIDO_FATURADO,
    quantidade_pendente_item,
    preco_unitario_item,
)
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.financeiro.constants import TipoMovimentoFinanceiro
from apps.financeiro.models import BaixaFinanceira, TituloFinanceiro

CENTAVO = Decimal('0.01')
ZERO = Decimal('0')
SCHEMA_VERSAO = 2

PERIODOS_MESES = (
    ('6_MESES', 6),
    ('12_MESES', 12),
    ('24_MESES', 24),
    ('TOTAL', None),
)

MSG_SEM_BAIXAS = 'Não há pagamentos válidos suficientes no período analisado.'
MSG_LIMITE_AMBIGUO = 'Limite não informado ou definido como zero.'
MSG_FREQ_UMA_COMPRA = 'Frequência média indisponível: há apenas uma compra no período.'


def _dec(v) -> Decimal:
    if v is None:
        return ZERO
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _dec_str(v: Decimal | None, *, disponivel: bool = True) -> str | None:
    if not disponivel or v is None:
        return None
    return format(_dec(v).quantize(Decimal('0.01')), 'f')


def _pct_str(v: Decimal | None, *, disponivel: bool) -> str | None:
    if not disponivel or v is None:
        return None
    return format(v.quantize(Decimal('0.01')), 'f')


def subtrair_meses_calendario(d: date, meses: int) -> date:
    """Subtrai meses de calendário (não aproxima 30/365 dias)."""
    y = d.year
    m = d.month - meses
    while m <= 0:
        m += 12
        y -= 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def _metrica(
    *,
    nome: str,
    disponivel: bool,
    valor,
    unidade: str,
    universo: int,
    periodo: str,
    fonte: str,
    motivo: str | None = None,
) -> dict[str, Any]:
    return {
        'nome': nome,
        'disponivel': disponivel,
        'valor': valor if disponivel else None,
        'unidade': unidade,
        'universo': universo,
        'periodo': periodo,
        'fonte': fonte,
        'motivo_indisponibilidade': None if disponivel else (motivo or 'Indisponível'),
    }


# ---------------------------------------------------------------------------
# Contas a receber
# ---------------------------------------------------------------------------


def _titulos_receber_abertos(cliente_id: int):
    return TituloFinanceiro.objects.filter(
        tipo=TituloFinanceiro.Tipo.RECEBER,
        cliente_id=cliente_id,
        cancelado=False,
        valor_aberto__gt=CENTAVO,
    ).exclude(
        status__in=(
            TituloFinanceiro.Status.RECEBIDO,
            TituloFinanceiro.Status.PAGO,
            TituloFinanceiro.Status.CANCELADO,
        )
    )


def saldo_receber_cliente(cliente_id: int, *, hoje: date | None = None) -> dict[str, Any]:
    hoje = hoje or timezone.localdate()
    qs = _titulos_receber_abertos(cliente_id)
    total = qs.aggregate(t=Sum('valor_aberto'))['t']
    vencido_qs = qs.filter(data_vencimento__lt=hoje)
    vencido = vencido_qs.aggregate(t=Sum('valor_aberto'))['t']
    a_vencer = qs.filter(data_vencimento__gte=hoje).aggregate(t=Sum('valor_aberto'))['t']
    qtd_vencidos = vencido_qs.count()
    datas = [d for d in vencido_qs.values_list('data_vencimento', flat=True) if d is not None]
    maior_atraso = (hoje - min(datas)).days if datas else None
    mais_antigo = min(datas).isoformat() if datas else None
    return {
        'disponivel': True,
        'fonte': 'TituloFinanceiro',
        'saldo_aberto': _dec(total),
        'saldo_vencido': _dec(vencido),
        'saldo_a_vencer': _dec(a_vencer),
        'quantidade_titulos_abertos': qs.count(),
        'quantidade_titulos_vencidos': qtd_vencidos,
        'maior_atraso_dias': maior_atraso,
        'titulo_mais_antigo_vencimento': mais_antigo,
        'universo': qs.count(),
    }


# ---------------------------------------------------------------------------
# Pedidos residual + divergência
# ---------------------------------------------------------------------------


def pedidos_nao_faturados_cliente(cliente_id: int) -> dict[str, Any]:
    pedidos = (
        PedidoVenda.objects.filter(cliente_id=cliente_id)
        .exclude(status__in=[*STATUS_PEDIDO_CANCELADO, *STATUS_PEDIDO_FATURADO])
        .prefetch_related('itens')
    )
    total = ZERO
    qtd_pedidos = 0
    qtd_itens = 0
    pedido_ids: list[int] = []
    for pedido in pedidos:
        residual = ZERO
        itens_residual = 0
        for item in pedido.itens.all():
            if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
                continue
            pend = quantidade_pendente_item(item)
            if pend <= ZERO:
                continue
            residual += (pend * preco_unitario_item(item)).quantize(Decimal('0.01'))
            itens_residual += 1
        if residual > CENTAVO:
            qtd_pedidos += 1
            qtd_itens += itens_residual
            total += residual
            pedido_ids.append(pedido.pk)
    return {
        'disponivel': True,
        'fonte': 'PedidoVenda/ItemPedidoVenda',
        'valor_residual': total,
        'quantidade_pedidos': qtd_pedidos,
        'quantidade_itens_residual': qtd_itens,
        'pedido_ids': pedido_ids,
    }


def detectar_divergencias_pedido_cr(cliente_id: int, pedido_ids_residual: list[int]) -> list[dict[str, str]]:
    """Detecta CR aberto ligado a pedido que ainda tem residual material — sem auto-corrigir."""
    alertas: list[dict[str, str]] = []
    if not pedido_ids_residual:
        return alertas
    ids = set(pedido_ids_residual)

    # origem PEDIDO_VENDA → origem_id = pedido
    conflitos = (
        TituloFinanceiro.objects.filter(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=cliente_id,
            cancelado=False,
            valor_aberto__gt=CENTAVO,
            origem_tipo=TituloFinanceiro.OrigemTipo.PEDIDO_VENDA,
            origem_id__in=ids,
        )
        .exclude(
            status__in=(
                TituloFinanceiro.Status.RECEBIDO,
                TituloFinanceiro.Status.PAGO,
                TituloFinanceiro.Status.CANCELADO,
            )
        )
        .count()
    )
    if conflitos:
        alertas.append(
            {
                'codigo': 'CR_PEDIDO_COM_RESIDUAL',
                'motivo': (
                    'Há conta a receber aberta vinculada a Pedido que ainda possui residual '
                    'não faturado. Componentes foram mantidos separados para conferência manual.'
                ),
            }
        )

    # origem FATURAMENTO → origem_id = FaturamentoPedidoVenda
    from apps.comercial.models import FaturamentoPedidoVenda

    fat_ids = list(
        FaturamentoPedidoVenda.objects.filter(pedido_id__in=ids).values_list('id', flat=True)
    )
    if fat_ids:
        conflitos_fat = (
            TituloFinanceiro.objects.filter(
                tipo=TituloFinanceiro.Tipo.RECEBER,
                cliente_id=cliente_id,
                cancelado=False,
                valor_aberto__gt=CENTAVO,
                origem_tipo=TituloFinanceiro.OrigemTipo.FATURAMENTO,
                origem_id__in=fat_ids,
            )
            .exclude(
                status__in=(
                    TituloFinanceiro.Status.RECEBIDO,
                    TituloFinanceiro.Status.PAGO,
                    TituloFinanceiro.Status.CANCELADO,
                )
            )
            .count()
        )
        if conflitos_fat:
            alertas.append(
                {
                    'codigo': 'CR_FATURAMENTO_COM_RESIDUAL',
                    'motivo': (
                        'Há conta a receber aberta de faturamento ligada a Pedido com residual '
                        'não faturado. Risco de sobreposição — conferência manual necessária.'
                    ),
                }
            )
    return alertas


# ---------------------------------------------------------------------------
# Baixas / pontualidade
# ---------------------------------------------------------------------------


def _vencimento_referencia_baixa(baixa: BaixaFinanceira) -> date | None:
    if baixa.parcela_id and baixa.parcela and baixa.parcela.data_vencimento:
        return baixa.parcela.data_vencimento
    if baixa.titulo_id and baixa.titulo and baixa.titulo.data_vencimento:
        return baixa.titulo.data_vencimento
    return None


def _baixas_receber_cliente(cliente_id: int):
    return (
        BaixaFinanceira.objects.filter(
            estornada=False,
            valor__gt=CENTAVO,
            titulo__tipo=TituloFinanceiro.Tipo.RECEBER,
            titulo__cliente_id=cliente_id,
            titulo__cancelado=False,
        )
        .select_related('titulo', 'parcela')
        .order_by('data_baixa')
    )


def _agregar_baixas_periodo(baixas: list[BaixaFinanceira], *, periodo: str) -> dict[str, Any]:
    validas: list[tuple[BaixaFinanceira, date, int]] = []
    excluidas = 0
    parciais = 0
    for bx in baixas:
        venc = _vencimento_referencia_baixa(bx)
        if venc is None:
            excluidas += 1
            continue
        atraso = max(0, (bx.data_baixa - venc).days)
        if bx.tipo_movimento in (
            TipoMovimentoFinanceiro.RECEBIMENTO_PARCIAL,
            TipoMovimentoFinanceiro.PAGAMENTO_PARCIAL,
        ):
            parciais += 1
        validas.append((bx, venc, atraso))

    universo = len(validas)
    if universo == 0:
        base = {
            'quantidade_baixas_analisadas': 0,
            'quantidade_excluidas': excluidas,
            'valor_total_recebido': None,
            'quantidade_no_prazo': None,
            'quantidade_com_atraso': None,
            'pontualidade_quantidade': _metrica(
                nome=f'pontualidade_quantidade_{periodo.lower()}',
                disponivel=False,
                valor=None,
                unidade='PERCENTUAL',
                universo=0,
                periodo=periodo,
                fonte='BaixaFinanceira',
                motivo=MSG_SEM_BAIXAS,
            ),
            'pontualidade_valor': _metrica(
                nome=f'pontualidade_valor_{periodo.lower()}',
                disponivel=False,
                valor=None,
                unidade='PERCENTUAL',
                universo=0,
                periodo=periodo,
                fonte='BaixaFinanceira',
                motivo=MSG_SEM_BAIXAS,
            ),
            'atraso_medio_dias': _metrica(
                nome=f'atraso_medio_{periodo.lower()}',
                disponivel=False,
                valor=None,
                unidade='DIAS',
                universo=0,
                periodo=periodo,
                fonte='BaixaFinanceira',
                motivo=MSG_SEM_BAIXAS,
            ),
            'maior_atraso_historico_dias': _metrica(
                nome=f'maior_atraso_historico_{periodo.lower()}',
                disponivel=False,
                valor=None,
                unidade='DIAS',
                universo=0,
                periodo=periodo,
                fonte='BaixaFinanceira',
                motivo=MSG_SEM_BAIXAS,
            ),
            'data_ultimo_pagamento': _metrica(
                nome=f'ultimo_pagamento_{periodo.lower()}',
                disponivel=False,
                valor=None,
                unidade='DATA',
                universo=0,
                periodo=periodo,
                fonte='BaixaFinanceira',
                motivo=MSG_SEM_BAIXAS,
            ),
            'quantidade_pagamentos_parciais': 0,
        }
        return base

    valor_total = sum((_dec(b.valor) for b, _, _ in validas), ZERO)
    no_prazo = [t for t in validas if t[2] == 0]
    com_atraso = [t for t in validas if t[2] > 0]
    valor_prazo = sum((_dec(b.valor) for b, _, _ in no_prazo), ZERO)
    pct_qtd = (Decimal(len(no_prazo)) * Decimal('100') / Decimal(universo)).quantize(Decimal('0.01'))
    pct_val = (
        (valor_prazo * Decimal('100') / valor_total).quantize(Decimal('0.01'))
        if valor_total > ZERO
        else ZERO
    )
    atrasos = [a for _, _, a in com_atraso]
    atraso_medio = (
        (Decimal(sum(atrasos)) / Decimal(len(atrasos))).quantize(Decimal('0.01')) if atrasos else ZERO
    )
    maior_atraso = max((a for _, _, a in validas), default=0)
    ultimo = max(b.data_baixa for b, _, _ in validas)

    return {
        'quantidade_baixas_analisadas': universo,
        'quantidade_excluidas': excluidas,
        'valor_total_recebido': _dec_str(valor_total),
        'quantidade_no_prazo': len(no_prazo),
        'quantidade_com_atraso': len(com_atraso),
        'pontualidade_quantidade': _metrica(
            nome=f'pontualidade_quantidade_{periodo.lower()}',
            disponivel=True,
            valor=_pct_str(pct_qtd, disponivel=True),
            unidade='PERCENTUAL',
            universo=universo,
            periodo=periodo,
            fonte='BaixaFinanceira',
        ),
        'pontualidade_valor': _metrica(
            nome=f'pontualidade_valor_{periodo.lower()}',
            disponivel=True,
            valor=_pct_str(pct_val, disponivel=True),
            unidade='PERCENTUAL',
            universo=universo,
            periodo=periodo,
            fonte='BaixaFinanceira',
        ),
        'atraso_medio_dias': _metrica(
            nome=f'atraso_medio_{periodo.lower()}',
            disponivel=True,
            valor=str(atraso_medio) if atrasos else '0',
            unidade='DIAS',
            universo=len(atrasos) if atrasos else universo,
            periodo=periodo,
            fonte='BaixaFinanceira',
        ),
        'maior_atraso_historico_dias': _metrica(
            nome=f'maior_atraso_historico_{periodo.lower()}',
            disponivel=True,
            valor=maior_atraso,
            unidade='DIAS',
            universo=universo,
            periodo=periodo,
            fonte='BaixaFinanceira',
        ),
        'data_ultimo_pagamento': _metrica(
            nome=f'ultimo_pagamento_{periodo.lower()}',
            disponivel=True,
            valor=ultimo.isoformat(),
            unidade='DATA',
            universo=universo,
            periodo=periodo,
            fonte='BaixaFinanceira',
        ),
        'quantidade_pagamentos_parciais': parciais,
    }


def historico_baixas_cliente(cliente_id: int, *, data_corte: date) -> dict[str, Any]:
    todas = list(_baixas_receber_cliente(cliente_id))
    por_periodo: dict[str, Any] = {}
    for chave, meses in PERIODOS_MESES:
        if meses is None:
            subset = todas
        else:
            inicio = subtrair_meses_calendario(data_corte, meses)
            subset = [b for b in todas if b.data_baixa >= inicio]
        por_periodo[chave] = _agregar_baixas_periodo(subset, periodo=chave)
    return {
        'fonte': 'BaixaFinanceira',
        'periodos': por_periodo,
        'total_baixas_cliente': len(todas),
    }


# ---------------------------------------------------------------------------
# Histórico comercial
# ---------------------------------------------------------------------------

MSG_FALLBACK_HOMOLOG = (
    'Documentos fiscais de homologação não foram considerados como vendas reais. '
    'O histórico comercial foi calculado pelos Pedidos de Venda.'
)
MSG_FALLBACK_SEM_NFE_PRODUCAO = (
    'Não há NF-e autorizada em produção elegível. '
    'O histórico comercial foi calculado pelos Pedidos de Venda.'
)
MSG_SOMENTE_HOMOLOG_SEM_PEDIDO = (
    'Há apenas documentos fiscais de homologação (ignorados) e nenhum Pedido de Venda '
    'elegível. Histórico comercial indisponível.'
)


def _ambiente_emissao_nfe(nf) -> str:
    return (getattr(nf, 'ambiente_emissao', None) or '').strip().lower()


def _classificar_nfes_cliente(cliente_id: int) -> dict[str, Any]:
    """
    Separa NF-e por ambiente fiscal real (`NFeSaida.ambiente_emissao`).

    Produção autorizada pode compor histórico; homologação e ambiente indefinido não.
    """
    from apps.fiscal.models import NFeSaida
    from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_producao, nf_cancelada_operacional
    from apps.fiscal.nfe_saida_financeiro import _STATUS_CANCELADA_LISTAGEM

    qs = NFeSaida.objects.filter(cliente_id=cliente_id).only(
        'id',
        'data',
        'valor_total',
        'status',
        'status_emissao_sefaz',
        'autorizada_em',
        'cancelada_em',
        'ambiente_emissao',
    )
    producao: list = []
    homolog_ignoradas = 0
    indeterminadas = 0

    for nf in qs:
        if nf.cancelada_em is not None:
            continue
        st = (nf.status or '').strip().upper()
        if st in _STATUS_CANCELADA_LISTAGEM or nf_cancelada_operacional(nf):
            continue

        amb = _ambiente_emissao_nfe(nf)
        if amb == NFeSaida.AmbienteEmissao.HOMOLOGACAO:
            # Homologação nunca entra no universo comercial, mesmo se "autorizada".
            homolog_ignoradas += 1
            continue
        if amb != NFeSaida.AmbienteEmissao.PRODUCAO:
            # Ambiente vazio/inválido: não tratar como produção.
            indeterminadas += 1
            continue
        # Ambiente produção: só se autorizada em produção.
        if nf_autorizada_producao(nf):
            producao.append(nf)
        # Demais documentos de produção não autorizados: ignorados sem contar como homolog.

    return {
        'producao': producao,
        'documentos_homologacao_ignorados': homolog_ignoradas,
        'documentos_ambiente_indeterminado': indeterminadas,
    }


def _pedidos_venda_historico(cliente_id: int):
    return list(
        PedidoVenda.objects.filter(cliente_id=cliente_id)
        .exclude(status__in=[*STATUS_PEDIDO_CANCELADO])
        .only('id', 'data', 'valor_total', 'status')
    )


def _pedidos_cancelados_count(cliente_id: int) -> int:
    return PedidoVenda.objects.filter(cliente_id=cliente_id).filter(
        status__in=[*STATUS_PEDIDO_CANCELADO]
    ).count()


def _agregar_vendas(
    vendas: list[tuple[date, Decimal]],
    *,
    periodo: str,
    inicio: date | None,
    data_corte: date,
    fonte: str,
) -> dict[str, Any]:
    if inicio is not None:
        subset = [(d, v) for d, v in vendas if inicio <= d <= data_corte]
    else:
        subset = [(d, v) for d, v in vendas if d <= data_corte]

    n = len(subset)
    if n == 0:
        return {
            'quantidade_vendas': 0,
            'valor_vendido': _dec_str(ZERO),
            'ticket_medio': _dec_str(ZERO),
            'maior_venda': _dec_str(ZERO),
            'primeira_compra': None,
            'ultima_compra': None,
            'frequencia_media_dias': _metrica(
                nome=f'frequencia_media_{periodo.lower()}',
                disponivel=False,
                valor=None,
                unidade='DIAS',
                universo=0,
                periodo=periodo,
                fonte=fonte,
                motivo='Não há vendas no período analisado.',
            ),
            'universo': 0,
        }

    valores = [v for _, v in subset]
    datas = [d for d, _ in subset]
    total = sum(valores, ZERO)
    ticket = (total / Decimal(n)).quantize(Decimal('0.01'))
    maior = max(valores)
    primeira = min(datas)
    ultima = max(datas)
    if n >= 2:
        span = (ultima - primeira).days
        freq = (Decimal(span) / Decimal(n - 1)).quantize(Decimal('0.01'))
        freq_m = _metrica(
            nome=f'frequencia_media_{periodo.lower()}',
            disponivel=True,
            valor=str(freq),
            unidade='DIAS',
            universo=n,
            periodo=periodo,
            fonte=fonte,
        )
    else:
        freq_m = _metrica(
            nome=f'frequencia_media_{periodo.lower()}',
            disponivel=False,
            valor=None,
            unidade='DIAS',
            universo=1,
            periodo=periodo,
            fonte=fonte,
            motivo=MSG_FREQ_UMA_COMPRA,
        )
    return {
        'quantidade_vendas': n,
        'valor_vendido': _dec_str(total),
        'ticket_medio': _dec_str(ticket),
        'maior_venda': _dec_str(maior),
        'primeira_compra': primeira.isoformat(),
        'ultima_compra': ultima.isoformat(),
        'frequencia_media_dias': freq_m,
        'universo': n,
    }


def historico_comercial_cliente(cliente_id: int, *, data_corte: date) -> dict[str, Any]:
    classif = _classificar_nfes_cliente(cliente_id)
    nfes_prod = classif['producao']
    homolog_ign = int(classif['documentos_homologacao_ignorados'] or 0)
    indeterminadas = int(classif['documentos_ambiente_indeterminado'] or 0)
    cancelados = _pedidos_cancelados_count(cliente_id)

    motivo_fallback: str | None = None
    ambiente_fiscal = 'NAO_APLICAVEL'

    if nfes_prod:
        fonte = 'NFE_SAIDA_PRODUCAO'
        ambiente_fiscal = 'PRODUCAO'
        vendas: list[tuple[date, Decimal]] = []
        for nf in nfes_prod:
            d = nf.data
            if nf.autorizada_em:
                d = nf.autorizada_em.date()
            if d is None:
                continue
            vendas.append((d, _dec(nf.valor_total)))
        limitacao = None
    else:
        pedidos = _pedidos_venda_historico(cliente_id)
        if pedidos:
            fonte = 'PEDIDO_VENDA'
            ambiente_fiscal = 'NAO_APLICAVEL'
            vendas = [(p.data, _dec(p.valor_total)) for p in pedidos if p.data]
            if homolog_ign > 0:
                motivo_fallback = MSG_FALLBACK_HOMOLOG
            elif indeterminadas > 0:
                motivo_fallback = (
                    'Ambiente fiscal de documentos NF-e não identificável com segurança; '
                    'não foram tratados como produção. '
                    + MSG_FALLBACK_SEM_NFE_PRODUCAO
                )
            else:
                motivo_fallback = MSG_FALLBACK_SEM_NFE_PRODUCAO
            limitacao = (
                'Histórico baseado em PedidoVenda (fallback): pode incluir pedidos ainda não faturados.'
            )
        else:
            fonte = 'INDISPONIVEL'
            vendas = []
            limitacao = None
            if homolog_ign > 0 or indeterminadas > 0:
                ambiente_fiscal = 'INDETERMINADO' if indeterminadas > 0 and homolog_ign == 0 else 'NAO_APLICAVEL'
                motivo_fallback = (
                    MSG_SOMENTE_HOMOLOG_SEM_PEDIDO
                    if homolog_ign > 0
                    else (
                        'Ambiente fiscal de documentos NF-e não identificável e sem Pedido de Venda elegível. '
                        'Histórico comercial indisponível.'
                    )
                )
            else:
                ambiente_fiscal = 'NAO_APLICAVEL'
                motivo_fallback = None

    periodos: dict[str, Any] = {}
    for chave, meses in PERIODOS_MESES:
        inicio = None if meses is None else subtrair_meses_calendario(data_corte, meses)
        periodos[chave] = _agregar_vendas(
            vendas, periodo=chave, inicio=inicio, data_corte=data_corte, fonte=fonte
        )

    total_block = periodos['TOTAL']
    relacionamento_dias = None
    if total_block.get('primeira_compra') and total_block.get('ultima_compra'):
        p0 = date.fromisoformat(total_block['primeira_compra'])
        relacionamento_dias = (data_corte - p0).days

    return {
        'fonte': fonte,
        'fonte_historico_comercial': fonte,
        'ambiente_fiscal_considerado': ambiente_fiscal,
        'documentos_homologacao_ignorados': homolog_ign,
        'documentos_ambiente_indeterminado': indeterminadas,
        'motivo_fallback_comercial': motivo_fallback,
        'limitacao': limitacao,
        'quantidade_pedidos_cancelados': cancelados,
        'tempo_relacionamento_dias': relacionamento_dias,
        'periodos': periodos,
        'vendas_totais_universo': len(vendas),
    }


# ---------------------------------------------------------------------------
# Qualidade
# ---------------------------------------------------------------------------


def _avaliar_qualidade(
    *,
    comercial: dict[str, Any],
    cr: dict[str, Any],
    baixas: dict[str, Any],
    divergencias: list[dict[str, str]],
    indisponiveis: list[dict[str, str]],
    data_corte: date,
) -> dict[str, Any]:
    vendas_total = (comercial.get('periodos') or {}).get('TOTAL', {}).get('quantidade_vendas') or 0
    baixas_total = baixas.get('total_baixas_cliente') or 0
    titulos_abertos = cr.get('quantidade_titulos_abertos') or 0

    if divergencias:
        status = 'DIVERGENTE'
        mensagem = (
            'Foram detectadas inconsistências entre Pedido residual e Contas a Receber. '
            'A decisão deve ser revisada manualmente pelo Financeiro.'
        )
    elif vendas_total == 0 and titulos_abertos == 0 and baixas_total == 0:
        status = 'INSUFICIENTE'
        mensagem = (
            'Não há histórico comercial ou financeiro suficiente para este cliente. '
            'Não classificar risco automaticamente.'
        )
    elif indisponiveis:
        status = 'PARCIAL'
        mensagem = (
            'Alguns indicadores não puderam ser calculados com os dados disponíveis. '
            'A decisão deve ser revisada manualmente pelo Financeiro.'
        )
    else:
        status = 'COMPLETA'
        mensagem = 'Indicadores principais disponíveis sem divergências materiais.'

    periodo_inicio = None
    if comercial.get('periodos', {}).get('TOTAL', {}).get('primeira_compra'):
        periodo_inicio = comercial['periodos']['TOTAL']['primeira_compra']

    excluidos = 0
    for p in (baixas.get('periodos') or {}).values():
        excluidos += int(p.get('quantidade_excluidas') or 0)

    return {
        'status': status,
        'mensagem': mensagem,
        # compat string
        'qualidade_dados': status,
        'indicadores_disponiveis': [],  # preenchido depois
        'indisponiveis': indisponiveis,
        'dados_indisponiveis': [i['indicador'] for i in indisponiveis],
        'pedidos_analisados': vendas_total,
        'titulos_analisados': titulos_abertos,
        'baixas_analisadas': baixas_total,
        'registros_excluidos': excluidos,
        'periodo_inicio': periodo_inicio,
        'periodo_fim': data_corte.isoformat(),
        'fonte_historico_comercial': comercial.get('fonte') or comercial.get('fonte_historico_comercial'),
        'ambiente_fiscal_considerado': comercial.get('ambiente_fiscal_considerado'),
        'documentos_homologacao_ignorados': comercial.get('documentos_homologacao_ignorados', 0),
        'motivo_fallback_comercial': comercial.get('motivo_fallback_comercial'),
        'divergencias': divergencias,
        'data_corte': data_corte.isoformat(),
    }


# ---------------------------------------------------------------------------
# Montagem final
# ---------------------------------------------------------------------------


def montar_indicadores(
    *,
    cliente,
    valor_proposta: Decimal,
    proposta_id: int | None = None,
) -> dict[str, Any]:
    data_corte = timezone.localdate()
    cliente_id = cliente.pk
    valor_prop = _dec(valor_proposta)

    cr = saldo_receber_cliente(cliente_id, hoje=data_corte)
    ped = pedidos_nao_faturados_cliente(cliente_id)
    divergencias = detectar_divergencias_pedido_cr(cliente_id, ped.get('pedido_ids') or [])
    comercial = historico_comercial_cliente(cliente_id, data_corte=data_corte)
    baixas = historico_baixas_cliente(cliente_id, data_corte=data_corte)

    exposicao_atual = cr['saldo_aberto'] + ped['valor_residual']
    exposicao_projetada = exposicao_atual + valor_prop

    limite = _dec(getattr(cliente, 'limite_credito', None))
    limite_ambiguo = limite == ZERO
    if limite_ambiguo:
        limite_block = {
            'cadastrado': _dec_str(limite),
            'ambiguo': True,
            'mensagem': MSG_LIMITE_AMBIGUO,
            'disponivel_antes': _metrica(
                nome='limite_disponivel_antes',
                disponivel=False,
                valor=None,
                unidade='BRL',
                universo=0,
                periodo='ATUAL',
                fonte='Cliente.limite_credito',
                motivo=MSG_LIMITE_AMBIGUO,
            ),
            'disponivel_depois': _metrica(
                nome='limite_disponivel_depois',
                disponivel=False,
                valor=None,
                unidade='BRL',
                universo=0,
                periodo='ATUAL',
                fonte='Cliente.limite_credito',
                motivo=MSG_LIMITE_AMBIGUO,
            ),
            'excesso_sobre_limite': _metrica(
                nome='excesso_sobre_limite',
                disponivel=False,
                valor=None,
                unidade='BRL',
                universo=0,
                periodo='ATUAL',
                fonte='Cliente.limite_credito',
                motivo=MSG_LIMITE_AMBIGUO,
            ),
        }
    else:
        disp_antes = limite - exposicao_atual
        disp_depois = limite - exposicao_projetada
        excesso = max(ZERO, exposicao_projetada - limite)
        limite_block = {
            'cadastrado': _dec_str(limite),
            'ambiguo': False,
            'mensagem': None,
            'disponivel_antes': _metrica(
                nome='limite_disponivel_antes',
                disponivel=True,
                valor=_dec_str(disp_antes),
                unidade='BRL',
                universo=1,
                periodo='ATUAL',
                fonte='Cliente.limite_credito',
            ),
            'disponivel_depois': _metrica(
                nome='limite_disponivel_depois',
                disponivel=True,
                valor=_dec_str(disp_depois),
                unidade='BRL',
                universo=1,
                periodo='ATUAL',
                fonte='Cliente.limite_credito',
            ),
            'excesso_sobre_limite': _metrica(
                nome='excesso_sobre_limite',
                disponivel=True,
                valor=_dec_str(excesso),
                unidade='BRL',
                universo=1,
                periodo='ATUAL',
                fonte='Cliente.limite_credito',
            ),
        }

    indisponiveis: list[dict[str, str]] = []
    # pontualidade 12m como indicador material de referência
    pont_12 = baixas['periodos']['12_MESES']['pontualidade_quantidade']
    if not pont_12['disponivel']:
        indisponiveis.append(
            {'indicador': 'pontualidade_12_meses', 'motivo': pont_12['motivo_indisponibilidade']}
        )
    if comercial['fonte'] in ('INDISPONIVEL',):
        indisponiveis.append(
            {
                'indicador': 'historico_comercial',
                'motivo': comercial.get('motivo_fallback_comercial')
                or 'Não há NF-e autorizada em produção nem Pedido de Venda elegível para o cliente.',
            }
        )
    elif comercial['fonte'] == 'PEDIDO_VENDA':
        indisponiveis.append(
            {
                'indicador': 'historico_comercial_nfe_producao',
                'motivo': comercial.get('motivo_fallback_comercial')
                or MSG_FALLBACK_SEM_NFE_PRODUCAO,
            }
        )

    freq_12 = comercial['periodos']['12_MESES']['frequencia_media_dias']
    if not freq_12['disponivel'] and comercial['periodos']['12_MESES']['quantidade_vendas'] == 1:
        indisponiveis.append(
            {'indicador': 'frequencia_media_12_meses', 'motivo': freq_12['motivo_indisponibilidade']}
        )

    qualidade = _avaliar_qualidade(
        comercial=comercial,
        cr=cr,
        baixas=baixas,
        divergencias=divergencias,
        indisponiveis=indisponiveis,
        data_corte=data_corte,
    )

    # Remover IDs técnicos do bloco público de pedidos
    ped_publico = {
        'disponivel': True,
        'fonte': ped['fonte'],
        'valor_residual': _dec_str(ped['valor_residual']),
        'quantidade_pedidos': ped['quantidade_pedidos'],
        'quantidade_itens_residual': ped['quantidade_itens_residual'],
    }

    indicadores = {
        'comercial': comercial,
        'contas_receber': {
            'disponivel': True,
            'fonte': cr['fonte'],
            'saldo_aberto': _dec_str(cr['saldo_aberto']),
            'saldo_vencido': _dec_str(cr['saldo_vencido']),
            'saldo_a_vencer': _dec_str(cr['saldo_a_vencer']),
            'quantidade_titulos_abertos': cr['quantidade_titulos_abertos'],
            'quantidade_titulos_vencidos': cr['quantidade_titulos_vencidos'],
            'maior_atraso_dias': cr['maior_atraso_dias'],
            'titulo_mais_antigo_vencimento': cr['titulo_mais_antigo_vencimento'],
            'universo': cr['universo'],
        },
        'baixas': baixas,
        'pedidos_nao_faturados': ped_publico,
        'exposicao': {
            'formula': (
                'exposicao_atual = CR aberto + residual pedidos não faturados; '
                'exposicao_projetada = exposicao_atual + valor da proposta'
            ),
            'contas_receber': _dec_str(cr['saldo_aberto']),
            'pedidos_nao_faturados': _dec_str(ped['valor_residual']),
            'atual': _dec_str(exposicao_atual),
            'valor_proposta': _dec_str(valor_prop),
            'projetada': _dec_str(exposicao_projetada),
            'proposta_id': proposta_id,
        },
        'limite': limite_block,
    }

    # Compatibilidade com consumidores do schema v1 / UI anterior
    b12 = baixas['periodos']['12_MESES']
    c12 = comercial['periodos']['12_MESES']
    return {
        'schema_versao': SCHEMA_VERSAO,
        'data_corte': data_corte.isoformat(),
        'indicadores': indicadores,
        'qualidade': qualidade,
        # --- campos planos (compat) ---
        'qualidade_dados': qualidade['status'],
        'dados_indisponiveis': qualidade['dados_indisponiveis'],
        'limite_credito_cadastrado': {
            'disponivel': not limite_ambiguo,
            'valor': _dec_str(limite) if not limite_ambiguo else None,
            'fonte': 'Cliente.limite_credito',
            'ambiguo': limite_ambiguo,
            'mensagem': MSG_LIMITE_AMBIGUO if limite_ambiguo else None,
        },
        'contas_receber': indicadores['contas_receber'],
        'pedidos_nao_faturados': ped_publico,
        'exposicao': indicadores['exposicao'],
        'percentual_pontualidade': {
            'disponivel': b12['pontualidade_quantidade']['disponivel'],
            'valor': b12['pontualidade_quantidade']['valor'],
            'motivo': b12['pontualidade_quantidade']['motivo_indisponibilidade'],
        },
        'atraso_medio_dias': {
            'disponivel': b12['atraso_medio_dias']['disponivel'],
            'valor': b12['atraso_medio_dias']['valor'],
            'motivo': b12['atraso_medio_dias']['motivo_indisponibilidade'],
        },
        'data_ultima_compra': {
            'disponivel': bool(c12.get('ultima_compra')),
            'valor': c12.get('ultima_compra'),
            'motivo': None if c12.get('ultima_compra') else 'Não há vendas no período de 12 meses.',
        },
        'valor_comprado_12_meses': {
            'disponivel': True,
            'valor': c12.get('valor_vendido'),
            'motivo': None,
        },
    }
