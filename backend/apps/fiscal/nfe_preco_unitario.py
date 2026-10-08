"""Precisão do preço unitário fiscal (ItemNFeSaida.valor / vUnCom / vUnTrib)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.comercial.valor_unitario_precisao import (
    MAX_CASAS_VALOR_UNITARIO,
    MSG_VALOR_UNITARIO_MAX_3_CASAS,
    casas_decimais_significativas,
    validar_max_casas_valor_unitario,
)

# Espelho da regra comercial: DB pode ter 4 casas; aplicação limita a 3.
MSG_PRECO_UNITARIO_NFE_MAX_3_CASAS = MSG_VALOR_UNITARIO_MAX_3_CASAS
MAX_CASAS_PRECO_UNITARIO_NFE = MAX_CASAS_VALOR_UNITARIO

__all__ = [
    'MAX_CASAS_PRECO_UNITARIO_NFE',
    'MSG_PRECO_UNITARIO_NFE_MAX_3_CASAS',
    'casas_decimais_significativas',
    'format_preco_unitario_nfe_xml',
    'format_preco_unitario_nfe_api',
    'validar_max_casas_valor_unitario',
    'validar_preco_unitario_nfe',
]


def validar_preco_unitario_nfe(valor) -> Decimal:
    """Valida e retorna Decimal com no máximo 3 casas significativas."""
    return validar_max_casas_valor_unitario(valor)


def format_preco_unitario_nfe_xml(valor) -> str:
    """
    Formata preço unitário para vUnCom/vUnTrib.
    Preserva até 3 casas; não força 2; remove zeros à direita desnecessários.
    """
    if valor is None or valor == '':
        return '0'
    d = Decimal(str(valor))
    d = d.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
    txt = format(d, 'f')
    if '.' in txt:
        txt = txt.rstrip('0').rstrip('.')
    return txt or '0'


def format_preco_unitario_nfe_api(valor) -> str:
    """String estável para API/conferência (até 3 casas, sem forçar 2)."""
    return format_preco_unitario_nfe_xml(valor)
