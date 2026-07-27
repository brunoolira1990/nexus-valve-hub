"""Indicadores financeiros para análise de proposta — sem inventar zeros."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.comercial.faturamento_pedido_venda import (
    STATUS_PEDIDO_CANCELADO,
    STATUS_PEDIDO_FATURADO,
    quantidade_pendente_item,
)
from apps.comercial.models import PedidoVenda
from apps.financeiro.models import TituloFinanceiro

CENTAVO = Decimal('0.01')
ZERO = Decimal('0')


def _dec(v) -> Decimal:
    if v is None:
        return ZERO
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _dec_str(v: Decimal | None, *, disponivel: bool) -> str | None:
    if not disponivel:
        return None
    return format(_dec(v), 'f')


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
    maior_atraso = None
    if qtd_vencidos:
        datas = list(vencido_qs.values_list('data_vencimento', flat=True))
        if datas:
            mais_antigo = min(d for d in datas if d is not None)
            maior_atraso = (hoje - mais_antigo).days
    return {
        'disponivel': True,
        'fonte': 'TituloFinanceiro.valor_aberto (RECEBER, não cancelado)',
        'saldo_aberto': _dec(total),
        'saldo_vencido': _dec(vencido),
        'saldo_a_vencer': _dec(a_vencer),
        'quantidade_titulos_abertos': qs.count(),
        'quantidade_titulos_vencidos': qtd_vencidos,
        'maior_atraso_dias': maior_atraso,
    }


def pedidos_nao_faturados_cliente(cliente_id: int) -> dict[str, Any]:
    """
    Residual de pedidos do cliente ainda não totalmente faturados.
    Evita duplicar CR: conta só saldo de item não faturado (qty × preço).
    """
    pedidos = (
        PedidoVenda.objects.filter(cliente_id=cliente_id)
        .exclude(status__in=[*STATUS_PEDIDO_CANCELADO, *STATUS_PEDIDO_FATURADO])
        .prefetch_related('itens')
    )
    total = ZERO
    qtd_pedidos = 0
    for pedido in pedidos:
        residual = ZERO
        for item in pedido.itens.all():
            pend = quantidade_pendente_item(item)
            if pend <= ZERO:
                continue
            preco = _dec(item.preco_por_unidade_negociada or item.valor_unitario)
            residual += pend * preco
        if residual > CENTAVO:
            qtd_pedidos += 1
            total += residual.quantize(Decimal('0.01'))
    return {
        'disponivel': True,
        'fonte': 'PedidoVenda residual (qtd pedida − faturada) × preço; exclui FATURADO/CANCELADO',
        'valor_residual': total,
        'quantidade_pedidos': qtd_pedidos,
    }


def montar_indicadores(
    *,
    cliente,
    valor_proposta: Decimal,
    proposta_id: int | None = None,
) -> dict[str, Any]:
    """
    Monta snapshot de indicadores. Valores indisponíveis ficam null + qualidade.
    Não inventa zero quando a fonte falhar — aqui as fontes CR/pedido são confiáveis.
    """
    hoje = timezone.localdate()
    limite = _dec(getattr(cliente, 'limite_credito', None))
    limite_disponivel = True  # campo cadastral sempre presente (default 0)

    cr = saldo_receber_cliente(cliente.pk, hoje=hoje)
    ped = pedidos_nao_faturados_cliente(cliente.pk)

    exposicao_atual = cr['saldo_aberto'] + ped['valor_residual']
    exposicao_projetada = exposicao_atual + _dec(valor_proposta)

    incompleto = []
    # pontualidade / atraso médio / última compra: não calcular sem regra consolidada
    incompleto.extend(
        [
            'percentual_pontualidade',
            'atraso_medio_dias',
            'valor_pago_periodo',
            'data_ultima_compra',
            'valor_comprado_12_meses',
            'quantidade_pedidos_historico',
        ]
    )

    qualidade = 'PARCIAL' if incompleto else 'COMPLETA'
    if not cr['disponivel'] or not ped['disponivel']:
        qualidade = 'INSUFICIENTE'

    return {
        'data_corte': hoje.isoformat(),
        'qualidade_dados': qualidade,
        'dados_indisponiveis': incompleto,
        'limite_credito_cadastrado': {
            'disponivel': limite_disponivel,
            'valor': _dec_str(limite, disponivel=limite_disponivel),
            'fonte': 'Cliente.limite_credito',
        },
        'contas_receber': {
            'disponivel': cr['disponivel'],
            'fonte': cr['fonte'],
            'saldo_aberto': _dec_str(cr['saldo_aberto'], disponivel=True),
            'saldo_vencido': _dec_str(cr['saldo_vencido'], disponivel=True),
            'saldo_a_vencer': _dec_str(cr['saldo_a_vencer'], disponivel=True),
            'quantidade_titulos_abertos': cr['quantidade_titulos_abertos'],
            'quantidade_titulos_vencidos': cr['quantidade_titulos_vencidos'],
            'maior_atraso_dias': cr['maior_atraso_dias'],
        },
        'pedidos_nao_faturados': {
            'disponivel': ped['disponivel'],
            'fonte': ped['fonte'],
            'valor_residual': _dec_str(ped['valor_residual'], disponivel=True),
            'quantidade_pedidos': ped['quantidade_pedidos'],
        },
        'exposicao': {
            'formula': (
                'exposicao_atual = CR aberto + residual pedidos não faturados; '
                'exposicao_projetada = exposicao_atual + valor da proposta'
            ),
            'atual': _dec_str(exposicao_atual, disponivel=True),
            'projetada': _dec_str(exposicao_projetada, disponivel=True),
            'valor_proposta': _dec_str(valor_proposta, disponivel=True),
            'proposta_id': proposta_id,
        },
        'percentual_pontualidade': {'disponivel': False, 'valor': None, 'motivo': 'Sem regra consolidada no MVP'},
        'atraso_medio_dias': {'disponivel': False, 'valor': None, 'motivo': 'Sem regra consolidada no MVP'},
        'data_ultima_compra': {'disponivel': False, 'valor': None, 'motivo': 'Sem regra consolidada no MVP'},
        'valor_comprado_12_meses': {'disponivel': False, 'valor': None, 'motivo': 'Sem regra consolidada no MVP'},
    }
