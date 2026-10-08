"""Recálculo de parcelas financeiras."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.financeiro.models import ParcelaFinanceira

CENTAVO = Decimal('0.01')


def somar_baixas_parcela(parcela: ParcelaFinanceira) -> Decimal:
    total = Decimal('0')
    for bx in parcela.baixas.filter(estornada=False):
        total += bx.valor
    return total.quantize(CENTAVO, rounding=ROUND_HALF_UP)
