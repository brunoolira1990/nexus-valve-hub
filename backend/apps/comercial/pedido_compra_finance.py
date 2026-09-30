from __future__ import annotations

from decimal import Decimal


def _q(v: Decimal, places: str = '0.01') -> Decimal:
    return v.quantize(Decimal(places))


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is None else Decimal('0')


def _desconto_item(q: Decimal, preco: Decimal, desconto_tipo: str, desconto_valor: Decimal) -> Decimal:
    if desconto_tipo == 'percentual':
        return _q(q * preco * desconto_valor / Decimal('100'))
    return _round(desconto_valor)


def calcular_desconto_item(it) -> Decimal:
    """Calcula o desconto propio de um item (igual ao get_desconto_valor_calculado do serializer)."""
    q = _dec(it.quantidade_negociada) or _dec(it.quantidade)
    preco = _dec(it.preco_por_unidade_negociada) or _dec(it.valor_unitario)
    if it.desconto_tipo == 'percentual':
        return _q(q * preco * it.desconto_valor / Decimal('100'))
    return _round(it.desconto_valor)


def calcular_rateio_desconto_cabecalho(pedido) -> dict[int, Decimal]:
    """Retorna {item_id: valor_desconto_rateado} proporcional ao valor do item.
    Vazio se nao ha desconto de cabecalho ou se ja ha desconto em item."""
    if not pedido:
        return {}
    itens = list(pedido.itens.all())
    if not itens:
        return {}
    if any((it.desconto_valor or Decimal('0')) > Decimal('0') for it in itens):
        return {}  # regra um-ou-outro: nao rateia se ha desconto proprio

    subtotal = Decimal('0')
    for it in itens:
        q = _dec(it.quantidade_negociada) or _dec(it.quantidade)
        p_it = _dec(it.preco_por_unidade_negociada) or _dec(it.valor_unitario)
        subtotal += q * p_it
    desc_cab_bruto = _dec(pedido.desconto_cabecalho)
    if pedido.desconto_cabecalho_tipo == 'percentual':
        desc_cab_valor = (subtotal * desc_cab_bruto / Decimal('100')).quantize(Decimal('0.01'))
    else:
        desc_cab_valor = desc_cab_bruto.quantize(Decimal('0.01'))
    desc_cab_valor = max(Decimal('0'), min(desc_cab_valor, subtotal))
    if desc_cab_valor <= 0:
        return {}

    pesos = {}
    total_peso = Decimal('0')
    for it in itens:
        q = _dec(it.quantidade_negociada) or _dec(it.quantidade)
        p_it = _dec(it.preco_por_unidade_negociada) or _dec(it.valor_unitario)
        peso = q * p_it
        pesos[it.id] = peso
        total_peso += peso
    if total_peso <= 0:
        return {}

    rateio = {}
    acumulado = Decimal('0')
    itens_ordenados = sorted(itens, key=lambda x: x.id)
    for idx, it in enumerate(itens_ordenados):
        if idx == len(itens_ordenados) - 1:
            valor = desc_cab_valor - acumulado  # ultimo absorve diferenca
        else:
            valor = (desc_cab_valor * pesos[it.id] / total_peso).quantize(Decimal('0.01'))
            acumulado += valor
        rateio[it.id] = valor
    return rateio


def desconto_final_item_compra(item, rateio: dict[int, Decimal]) -> Decimal:
    """Desconto proprio do item. Se vazio, usa o rateado do cabecalho."""
    proprio = calcular_desconto_item(item)  # ja existe
    if proprio and proprio > Decimal('0'):
        return proprio
    return rateio.get(item.id, Decimal('0'))


def calcular_financeiro_item_pedido_compra(
    *,
    quantidade_negociada,
    preco_por_unidade_negociada,
    ipi_percentual,
    ipi_valor_informado,
    icms_st_percentual,
    icms_st_valor_informado,
    desconto_tipo,
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

    desconto = _desconto_item(q, preco, desconto_tipo, _dec(desconto_valor))
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
