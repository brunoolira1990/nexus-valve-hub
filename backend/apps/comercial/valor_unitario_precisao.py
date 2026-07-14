"""Precisão decimal do preço unitário comercial do Pedido de Venda."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

MSG_VALOR_UNITARIO_MAX_3_CASAS = 'O valor unitário aceita no máximo 3 casas decimais.'

# Fonte comercial: preco_por_unidade_negociada (DB numeric(14,4)).
MAX_CASAS_VALOR_UNITARIO = 3


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v).strip().replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def casas_decimais_significativas(valor: Decimal | str | int | float | None) -> int:
    """Conta casas fracionárias significativas (zeros à direita não contam)."""
    d = _dec(valor)
    t = d.normalize().as_tuple()
    if t.exponent >= 0:
        return 0
    return min(-t.exponent, 20)


def validar_max_casas_valor_unitario(valor) -> Decimal:
    """Retorna Decimal ou levanta ValueError com mensagem de UX."""
    d = _dec(valor)
    if casas_decimais_significativas(d) > MAX_CASAS_VALOR_UNITARIO:
        raise ValueError(MSG_VALOR_UNITARIO_MAX_3_CASAS)
    return d
