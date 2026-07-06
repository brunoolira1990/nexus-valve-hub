"""
Normalização de CST PIS/COFINS do XML (perspectiva do emitente) para comparação na entrada.

Na NF-e de compra, o fornecedor informa CST de saída; a regra fiscal de entrada
espera o CST do destinatário.
"""

from __future__ import annotations

# CST de saída (fornecedor) → equivalente na entrada (destinatário).
_CST_SAIDA_PARA_ENTRADA: dict[str, str] = {
    '50': '01',
    '51': '02',
    '52': '03',
    '53': '04',
    '54': '05',
    '55': '06',
    '56': '07',
    '60': '08',
    '61': '09',
    '70': '49',
    '71': '50',
    '72': '50',
    '73': '50',
    '74': '50',
    '75': '50',
    '98': '98',
    '99': '99',
}


def _norm_codigo(cst: str) -> str:
    digits = ''.join(ch for ch in (cst or '').strip() if ch.isdigit())
    if not digits:
        return ''
    if len(digits) <= 2:
        return digits.zfill(2)
    return digits[-2:]


def normalizar_cst_pis_cofins_xml_para_entrada(cst: str) -> str:
    """Converte CST PIS/COFINS de perspectiva de saída para perspectiva de entrada."""
    cod = _norm_codigo(cst)
    if not cod:
        return ''
    return _CST_SAIDA_PARA_ENTRADA.get(cod, cod)
