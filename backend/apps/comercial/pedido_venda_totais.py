"""Totais comerciais do Pedido de Venda — derivados dos itens (fonte preferida para PDF/resumo)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.comercial.models import ItemPedidoVenda, PedidoVenda


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _round_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'))


def _round_qty(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.001'))


def _quantidade_pedida_item(item: ItemPedidoVenda) -> Decimal:
    return _round_qty(_dec(item.quantidade_negociada or item.quantidade))


def _preco_unitario_item(item: ItemPedidoVenda) -> Decimal:
    return _dec(item.preco_por_unidade_negociada or item.valor_unitario)


@dataclass(frozen=True)
class TotaisPedidoVenda:
    subtotal_produtos: Decimal
    desconto_total: Decimal
    frete: Decimal
    outras_despesas: Decimal
    ipi: Decimal
    icms_st: Decimal
    valor_total: Decimal
    valor_total_salvo: Decimal
    divergente_salvo: bool

    @property
    def valor_pendente(self) -> Decimal:
        """Calculado externamente com valor_faturado quando necessário."""
        return self.valor_total


def calcular_totais_pedido_venda(
    pedido: PedidoVenda,
    *,
    itens: list[ItemPedidoVenda] | None = None,
) -> TotaisPedidoVenda:
    """
    Total comercial do pedido a partir dos itens ativos:

    valor_total = subtotal_produtos - desconto_total - desconto_cabecalho + frete + outras + IPI + ICMS ST

    Pedido de Venda não possui frete/IPI/ST no cabeçalho nesta fase — apenas itens.
    """
    if itens is None:
        itens = list(
            pedido.itens.exclude(status_item=ItemPedidoVenda.StatusItem.CANCELADO).order_by('id'),
        )

    subtotal = Decimal('0')
    desconto = Decimal('0')
    for it in itens:
        q = _quantidade_pedida_item(it)
        p = _preco_unitario_item(it)
        subtotal += q * p
        desconto += _dec(it.desconto)

    desconto_cabecalho_bruto = _dec(getattr(pedido, 'desconto_cabecalho', Decimal('0')) or Decimal('0'))
    desconto_cabecalho_tipo = getattr(pedido, 'desconto_cabecalho_tipo', 'valor') or 'valor'
    base_desconto_cabecalho = subtotal - desconto
    if desconto_cabecalho_tipo == 'percentual':
        desconto_cabecalho = _round_money(base_desconto_cabecalho * desconto_cabecalho_bruto / Decimal('100'))
    else:
        desconto_cabecalho = _round_money(desconto_cabecalho_bruto)
    # Clamp: nao pode passar do subtotal - desconto_itens, nem ser negativo
    desconto_cabecalho = max(Decimal('0'), min(desconto_cabecalho, max(Decimal('0'), base_desconto_cabecalho)))

    frete = Decimal('0')
    outras = Decimal('0')
    ipi = Decimal('0')
    icms_st = Decimal('0')
    valor_total = _round_money(max(Decimal('0'), subtotal - desconto - desconto_cabecalho + frete + outras + ipi + icms_st))
    salvo = _round_money(_dec(pedido.valor_total))

    return TotaisPedidoVenda(
        subtotal_produtos=_round_money(subtotal),
        desconto_total=_round_money(desconto),
        frete=frete,
        outras_despesas=outras,
        ipi=ipi,
        icms_st=icms_st,
        valor_total=valor_total,
        valor_total_salvo=salvo,
        divergente_salvo=abs(valor_total - salvo) > Decimal('0.01'),
    )
