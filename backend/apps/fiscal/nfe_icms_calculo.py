"""Cálculo de base e valor ICMS na NF-e Saída (CST 00, CST 20 com redução de BC)."""

from __future__ import annotations

from decimal import Decimal


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal('0.01'))


def calcular_base_valor_icms_saida(
    valor_base_original: Decimal,
    aliquota_pct: Decimal,
    *,
    reducao_bc_pct: Decimal | None = None,
    cst_icms: str = '',
) -> tuple[Decimal, Decimal]:
    """
    Retorna (base_icms, valor_icms).

    CST 20 (ou redução > 0): base_reduzida = valor × (1 - pRedBC/100); vICMS = base × pICMS/100.
    Demais CST: base = valor integral; vICMS = base × pICMS/100.
    """
    base = valor_base_original
    reducao = reducao_bc_pct if reducao_bc_pct is not None else Decimal('0')
    cst = (cst_icms or '').strip().zfill(2)[:2]

    if cst == '20' or reducao > 0:
        if reducao > 0:
            fator = Decimal('1') - reducao / Decimal('100')
            base = _q2(valor_base_original * fator)

    if not aliquota_pct:
        return base, Decimal('0')

    valor = _q2(base * aliquota_pct / Decimal('100'))
    return base, valor
