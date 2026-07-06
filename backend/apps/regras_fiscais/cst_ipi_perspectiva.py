"""
Normalização de CST IPI do XML (perspectiva do emitente) para comparação na entrada.

Na NF-e de compra, o fornecedor informa CST de saída; a regra fiscal de entrada
espera o CST do destinatário. Correlação típica: saída 5X → entrada 0X (exceto 99→49).
"""

from __future__ import annotations


def _norm_codigo(cst: str) -> str:
    digits = ''.join(ch for ch in (cst or '').strip() if ch.isdigit())
    if not digits:
        return ''
    if len(digits) <= 2:
        return digits.zfill(2)
    return digits[-2:]


def normalizar_cst_ipi_xml_para_entrada(cst: str) -> str:
    """Converte CST IPI de perspectiva de saída para perspectiva de entrada."""
    cod = _norm_codigo(cst)
    if not cod:
        return ''
    if cod == '99':
        return '49'
    if cod.startswith('5') and cod[1] in '012345':
        return str(int(cod) - 50).zfill(2)
    return cod
