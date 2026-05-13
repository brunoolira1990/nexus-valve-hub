from __future__ import annotations

from decimal import Decimal


def _q(v: Decimal, places: str = '0.01') -> Decimal:
    return v.quantize(Decimal(places))


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def calcular_financeiro_item_pedido_compra(
    *,
    quantidade_negociada,
    preco_por_unidade_negociada,
    ipi_percentual,
    ipi_valor_informado,
    icms_st_percentual,
    icms_st_valor_informado,
    desconto_valor,
    frete_valor,
    outras_despesas_valor,
) -> dict:
    """Alinha com totais típicos de NF-e (vProd, vIPI, vST, vDesc, vFrete, vOutro)."""
    q = _dec(quantidade_negociada)
    preco = _dec(preco_por_unidade_negociada)
    valor_produtos = _q(q * preco)

    ipi_pct = _dec(ipi_percentual)
    ipi_val_inf = _dec(ipi_valor_informado)
    if ipi_val_inf > 0:
        ipi_valor = _q(ipi_val_inf)
    elif ipi_pct > 0:
        ipi_valor = _q(valor_produtos * ipi_pct / Decimal('100'))
    else:
        ipi_valor = Decimal('0')

    st_pct = _dec(icms_st_percentual)
    st_val_inf = _dec(icms_st_valor_informado)
    if st_val_inf > 0:
        icms_st_valor = _q(st_val_inf)
    elif st_pct > 0:
        icms_st_valor = _q(valor_produtos * st_pct / Decimal('100'))
    else:
        icms_st_valor = Decimal('0')

    desconto = _q(max(_dec(desconto_valor), Decimal('0')))
    frete = _q(max(_dec(frete_valor), Decimal('0')))
    outras = _q(max(_dec(outras_despesas_valor), Decimal('0')))

    valor_total_item = valor_produtos + ipi_valor + icms_st_valor + frete + outras - desconto
    if valor_total_item < 0:
        valor_total_item = Decimal('0')
    else:
        valor_total_item = _q(valor_total_item)

    return {
        'valor_produtos': valor_produtos,
        'ipi_valor': ipi_valor,
        'icms_st_valor': icms_st_valor,
        'desconto_valor': desconto,
        'frete_valor': frete,
        'outras_despesas_valor': outras,
        'valor_total_item': valor_total_item,
    }
