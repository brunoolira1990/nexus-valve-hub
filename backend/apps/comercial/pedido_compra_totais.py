"""Totais comerciais do Pedido de Compra — derivados dos itens (fonte preferida para PDF/resumo)."""

from dataclasses import dataclass
from decimal import Decimal

from apps.comercial.models import ItemPedidoCompra, PedidoCompra


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _round_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'))


def _round_qty(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.001'))


def _quantidade_pedida_item(item: ItemPedidoCompra) -> Decimal:
    return _round_qty(_dec(item.quantidade_negociada or item.quantidade))


def _preco_unitario_item(item: ItemPedidoCompra) -> Decimal:
    return _dec(item.preco_por_unidade_negociada or item.valor_unitario)


@dataclass(frozen=True)
class TotaisPedidoCompra:
    subtotal_produtos: Decimal
    desconto_itens: Decimal
    desconto_cabecalho_valor: Decimal
    frete: Decimal
    outras_despesas: Decimal
    ipi: Decimal
    icms_st: Decimal
    valor_total: Decimal
    valor_total_salvo: Decimal
    divergente_salvo: bool


def calcular_totais_pedido_compra(
    pedido: PedidoCompra,
    *,
    itens: list[ItemPedidoCompra] | None = None,
) -> TotaisPedidoCompra:
    """
    Total comercial do pedido a partir dos itens ativos:

    valor_total = subtotal - desconto_itens - desconto_cabecalho + frete + outras + IPI + ICMS ST

    O desconto de cabecalho e calculado sobre (subtotal - descontos de itens),
    igual ao PedidoVenda.
    """
    if itens is None:
        itens = list(
            pedido.itens.exclude(status_item=ItemPedidoCompra.StatusItem.CANCELADO).order_by('id'),
        )

    subtotal = Decimal('0')
    desconto_itens = Decimal('0')
    for it in itens:
        q = _quantidade_pedida_item(it)
        p = _preco_unitario_item(it)
        subtotal += q * p
        desconto_itens += _dec(it.desconto_valor)

    desconto_cabecalho_bruto = _dec(getattr(pedido, 'desconto_cabecalho', Decimal('0')) or Decimal('0'))
    desconto_cabecalho_tipo = getattr(pedido, 'desconto_cabecalho_tipo', 'valor') or 'valor'
    base_cabecalho = subtotal - desconto_itens

    if desconto_cabecalho_tipo == 'percentual':
        desconto_cabecalho_valor = _round_money(base_cabecalho * desconto_cabecalho_bruto / Decimal('100'))
    else:
        desconto_cabecalho_valor = _round_money(desconto_cabecalho_bruto)

    # Clamp: nao pode passar do base_cabecalho, nem ser negativo
    desconto_cabecalho_valor = max(Decimal('0'), min(desconto_cabecalho_valor, max(Decimal('0'), base_cabecalho)))

    frete = Decimal('0')
    outras = Decimal('0')
    ipi = Decimal('0')
    icms_st = Decimal('0')
    for it in itens:
        ipi += _dec(it.ipi_valor)
        icms_st += _dec(it.icms_st_valor)
        outras += _dec(it.outras_despesas_valor)

    # valor_total = max(0, subtotal - desconto_itens - desconto_cabecalho_valor + frete + ipi + st + outras)
    valor_total = _round_money(max(Decimal('0'), subtotal - desconto_itens - desconto_cabecalho_valor + frete + ipi + icms_st + outras))

    salvo = _round_money(_dec(pedido.valor_total))

    return TotaisPedidoCompra(
        subtotal_produtos=_round_money(subtotal),
        desconto_itens=_round_money(desconto_itens),
        desconto_cabecalho_valor=desconto_cabecalho_valor,
        frete=frete,
        outras_despesas=outras,
        ipi=ipi,
        icms_st=icms_st,
        valor_total=valor_total,
        valor_total_salvo=salvo,
        divergente_salvo=abs(valor_total - salvo) > Decimal('0.01'),
    )