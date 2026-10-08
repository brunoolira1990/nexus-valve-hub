"""Base de cálculo PIS/COFINS na saída (dedução opcional de ICMS)."""

from __future__ import annotations

from decimal import Decimal


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal('0.01'))


def calcular_base_pis_cofins_saida(
    valor_base: Decimal,
    valor_icms: Decimal | None,
    *,
    deduzir_icms_base_pis: bool,
    deduzir_icms_base_cofins: bool,
    aliquota_icms_pct: Decimal | None = None,
) -> tuple[Decimal, Decimal, list[str]]:
    """
    Retorna (base_pis, base_cofins, mensagens).
    Se valor_icms for None e houver dedução, tenta derivar de aliquota_icms_pct sobre valor_base.
    """
    mensagens: list[str] = []
    vb = _q2(Decimal(str(valor_base)))

    vi: Decimal | None
    if valor_icms is not None:
        vi = _q2(Decimal(str(valor_icms)))
    elif (deduzir_icms_base_pis or deduzir_icms_base_cofins) and aliquota_icms_pct is not None:
        aliq = Decimal(str(aliquota_icms_pct))
        if aliq > 0:
            vi = _q2(vb * aliq / Decimal('100'))
        else:
            vi = Decimal('0')
    else:
        vi = None

    if (deduzir_icms_base_pis or deduzir_icms_base_cofins) and vi is None:
        mensagens.append(
            'Dedução de ICMS da base PIS/COFINS configurada, mas valor ICMS indisponível.',
        )
        vi = Decimal('0')

    icms_val = vi if vi is not None else Decimal('0')

    base_pis = vb
    base_cofins = vb
    if deduzir_icms_base_pis:
        base_pis = max(Decimal('0'), _q2(vb - icms_val))
    if deduzir_icms_base_cofins:
        base_cofins = max(Decimal('0'), _q2(vb - icms_val))

    return base_pis, base_cofins, mensagens


def percentual_saida_total_com_deducao_icms(
    icms: Decimal,
    pis: Decimal,
    cofins: Decimal,
    ipi_saida: Decimal,
    irpj: Decimal,
    csll: Decimal,
    comissao: Decimal,
    *,
    origem: str,
    deduzir_icms_base_pis: bool,
    deduzir_icms_base_cofins: bool,
) -> tuple[Decimal, list[str]]:
    """
    Equivalente a aplicar PIS/COFINS sobre (base - ICMS), mantendo o modelo de percentual
    sobre o preço de referência da proposta.
    """
    from apps.comercial.pricing import percentual_saida_total

    mensagens: list[str] = []
    pis_eff = pis
    cofins_eff = cofins

    if origem != 'CENARIO_SAIDA':
        return (
            percentual_saida_total(icms, pis, cofins, ipi_saida, irpj, csll, comissao),
            mensagens,
        )

    if deduzir_icms_base_pis and pis > 0:
        if icms > 0:
            pis_eff = _q2(pis * (Decimal('100') - icms) / Decimal('100'))
        else:
            mensagens.append('Dedução ICMS da base PIS ativa, mas alíquota ICMS indisponível.')

    if deduzir_icms_base_cofins and cofins > 0:
        if icms > 0:
            cofins_eff = _q2(cofins * (Decimal('100') - icms) / Decimal('100'))
        else:
            mensagens.append('Dedução ICMS da base COFINS ativa, mas alíquota ICMS indisponível.')

    total = percentual_saida_total(icms, pis_eff, cofins_eff, ipi_saida, irpj, csll, comissao)
    return total, mensagens
