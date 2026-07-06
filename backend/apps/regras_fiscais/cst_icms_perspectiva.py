"""
Normalização de CST ICMS do XML (perspectiva do emitente) para comparação na entrada.

Na NF-e de compra, o fornecedor informa CST de saída; a regra fiscal de entrada
espera o CST do destinatário. Em operações com ST retida, códigos distintos podem
ser fiscalmente equivalentes (ex.: 70/72 na saída → 60 na entrada).
"""

from __future__ import annotations

# CST de saída do fornecedor → CST equivalente na entrada do destinatário.
_CST_SAIDA_PARA_ENTRADA: dict[str, str] = {
    '70': '60',
    '72': '60',
}


def _norm_cst(cst: str) -> str:
    digits = ''.join(ch for ch in (cst or '').strip() if ch.isdigit())
    if not digits:
        return ''
    return digits.zfill(2)[-2:]


def normalizar_cst_icms_xml_para_entrada(cst: str) -> str:
    """Converte CST ICMS lido do XML para a perspectiva de entrada antes de comparar com a regra."""
    norm = _norm_cst(cst)
    if not norm:
        return ''
    return _CST_SAIDA_PARA_ENTRADA.get(norm, norm)
