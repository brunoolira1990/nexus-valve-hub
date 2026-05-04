from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from apps.produtos.conversao_medidas import ConversaoErro, converter_quantidade_produto
from apps.produtos.models import Produto

QTY_Q = Decimal('0.001')
PRICE_Q = Decimal('0.0001')
MONEY_Q = Decimal('0.01')
FACTOR_Q = Decimal('0.000001')


def _dec(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    if v is None:
        return Decimal('0')
    return Decimal(str(v))


def _q(value: Decimal, q: Decimal) -> Decimal:
    return value.quantize(q, rounding=ROUND_HALF_UP)


def _allowed_unidades_negociacao(produto: Produto, contexto: str) -> set[str]:
    if contexto == 'compra':
        own = {str(u).strip().upper() for u in (produto.unidades_compra_permitidas or []) if str(u).strip()}
        fam = set()
        if produto.familia_id:
            fam = {
                str(u).strip().upper()
                for u in (produto.familia.unidades_compra_permitidas or [])
                if str(u).strip()
            }
        base = own or fam
        if not base:
            # Fallback solicitado: compra -> venda permitida.
            own_venda = {str(u).strip().upper() for u in (produto.unidades_venda_permitidas or []) if str(u).strip()}
            fam_venda = set()
            if produto.familia_id:
                fam_venda = {
                    str(u).strip().upper()
                    for u in (produto.familia.unidades_venda_permitidas or [])
                    if str(u).strip()
                }
            base = own_venda or fam_venda
        if not base:
            fallback = (
                produto.get_unidade_compra_efetiva()
                or produto.get_unidade_venda_efetiva()
                or produto.unidade
                or 'PC'
            ).strip().upper()
            return {fallback}
        return base

    own = {str(u).strip().upper() for u in (produto.unidades_venda_permitidas or []) if str(u).strip()}
    fam = set()
    if produto.familia_id:
        fam = {str(u).strip().upper() for u in (produto.familia.unidades_venda_permitidas or []) if str(u).strip()}
    base = own or fam
    if not base:
        fallback = (produto.get_unidade_venda_efetiva() or produto.unidade or 'PC').strip().upper()
        return {fallback}
    return base


def _safe_convert(
    produto: Produto,
    quantidade: Decimal,
    unidade_origem: str,
    unidade_destino: str,
    alerts: list[str],
) -> Decimal | None:
    try:
        return converter_quantidade_produto(
            produto=produto,
            quantidade=quantidade,
            unidade_origem=unidade_origem,
            unidade_destino=unidade_destino,
        ).quantidade_destino
    except ConversaoErro as exc:
        alerts.append(str(exc))
        return None


def calcular_item_comercial_com_conversao(
    *,
    produto: Produto | None,
    quantidade_negociada,
    unidade_negociada: str,
    preco_por_unidade_negociada,
    contexto: str = 'venda',
) -> dict:
    qtd_neg = _q(_dec(quantidade_negociada), QTY_Q)
    preco_un = _q(_dec(preco_por_unidade_negociada), PRICE_Q)
    if qtd_neg <= 0:
        raise serializers.ValidationError({'quantidade_negociada': 'Quantidade deve ser maior que zero.'})
    if preco_un < 0:
        raise serializers.ValidationError({'preco_por_unidade_negociada': 'Preço deve ser maior ou igual a zero.'})

    unidade_neg = (unidade_negociada or '').strip().upper()
    alerts: list[str] = []
    is_dimensional = bool(produto and produto.get_usa_conversao_dimensional_efetivo())

    if not unidade_neg:
        if produto:
            if contexto == 'compra':
                unidade_neg = (
                    produto.get_unidade_compra_efetiva()
                    or produto.get_unidade_venda_efetiva()
                    or produto.unidade
                    or 'PC'
                ).strip().upper()
            else:
                unidade_neg = (produto.get_unidade_venda_efetiva() or produto.unidade or 'PC').strip().upper()
        else:
            unidade_neg = 'PC'

    unidade_estoque = (produto.get_unidade_estoque_efetiva().strip().upper() if produto else '') or unidade_neg
    qtd_estoque = qtd_neg
    peso_total_kg = Decimal('0')
    metros_total = Decimal('0')
    barras_total = Decimal('0')
    fator = Decimal('1')
    preco_kg = Decimal('0')
    preco_m = Decimal('0')

    if produto and is_dimensional:
        allowed = _allowed_unidades_negociacao(produto, contexto)
        if unidade_neg not in allowed:
            ctx_msg = 'compra' if contexto == 'compra' else 'venda'
            raise serializers.ValidationError(
                {'unidade_negociada': f"Unidade '{unidade_neg}' não está permitida para {ctx_msg} neste produto."}
            )
        try:
            conv_estoque = converter_quantidade_produto(produto, qtd_neg, unidade_neg, unidade_estoque)
            qtd_estoque = _q(_dec(conv_estoque.quantidade_destino), QTY_Q)
            peso_total_kg = _q(_dec(conv_estoque.peso_kg or Decimal('0')), QTY_Q)
            metros_total = _q(_dec(conv_estoque.metros or Decimal('0')), QTY_Q)
            barras_total = _q(_dec(conv_estoque.barras or Decimal('0')), QTY_Q)
            if qtd_neg > 0:
                fator = _q(qtd_estoque / qtd_neg, FACTOR_Q)
        except ConversaoErro as exc:
            raise serializers.ValidationError({'unidade_negociada': str(exc)}) from exc

        kg_for_one = _safe_convert(produto, Decimal('1'), unidade_neg, 'KG', alerts)
        m_for_one = _safe_convert(produto, Decimal('1'), unidade_neg, 'M', alerts)
        if kg_for_one and kg_for_one > 0:
            preco_kg = _q(preco_un / kg_for_one, PRICE_Q)
        if m_for_one and m_for_one > 0:
            preco_m = _q(preco_un / m_for_one, PRICE_Q)
    else:
        if produto and unidade_neg != unidade_estoque:
            alerts.append('Produto sem conversão dimensional habilitada; usando quantidade negociada como estoque.')
        unidade_estoque = unidade_neg or unidade_estoque
        qtd_estoque = qtd_neg

    valor_total = _q(qtd_neg * preco_un, MONEY_Q)
    return {
        'unidade_negociada': unidade_neg,
        'quantidade_negociada': qtd_neg,
        'unidade_estoque_calculada': unidade_estoque,
        'quantidade_estoque_calculada': qtd_estoque,
        'peso_total_kg': peso_total_kg,
        'metros_total': metros_total,
        'barras_total': barras_total,
        'preco_por_unidade_negociada': preco_un,
        'preco_por_kg': preco_kg,
        'preco_por_metro': preco_m,
        'fator_conversao': fator,
        'valor_unitario': _q(preco_un, MONEY_Q),
        'quantidade': qtd_neg,
        'valor_total_calculado': valor_total,
        'alertas_conversao': list(dict.fromkeys(alerts)),
    }
