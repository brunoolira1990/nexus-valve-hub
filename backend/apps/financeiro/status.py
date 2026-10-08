"""Cálculo de status financeiros operacionais."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.utils import timezone

CENTAVO = Decimal('0.01')


def _hoje() -> date:
    return timezone.localdate()


def calcular_status_titulo(
    *,
    tipo: str,
    valor_original: Decimal,
    valor_aberto: Decimal,
    valor_baixado: Decimal,
    data_vencimento: date,
    cancelado: bool,
    hoje: date | None = None,
) -> str:
    from apps.financeiro.models import TituloFinanceiro

    hoje = hoje or _hoje()
    if cancelado:
        return TituloFinanceiro.Status.CANCELADO
    if valor_original <= 0:
        return TituloFinanceiro.Status.EM_ABERTO
    if valor_aberto <= CENTAVO:
        if tipo == TituloFinanceiro.Tipo.PAGAR:
            return TituloFinanceiro.Status.PAGO
        return TituloFinanceiro.Status.RECEBIDO
    if valor_baixado > CENTAVO:
        if tipo == TituloFinanceiro.Tipo.PAGAR:
            return TituloFinanceiro.Status.PARCIALMENTE_PAGO
        return TituloFinanceiro.Status.PARCIALMENTE_RECEBIDO
    if data_vencimento < hoje:
        return TituloFinanceiro.Status.VENCIDO
    return TituloFinanceiro.Status.EM_ABERTO
