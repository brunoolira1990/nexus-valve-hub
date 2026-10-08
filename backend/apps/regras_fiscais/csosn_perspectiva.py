"""
Conversão de CSOSN (Simples Nacional) para CST ICMS de entrada (regime normal).

Fornecedores optantes do Simples emitem CSOSN; o destinatário no regime normal
escritura a entrada com CST convencional.
"""

from __future__ import annotations

# CSOSN (saída Simples) → CST equivalente antes da normalização saída→entrada.
_CSOSN_PARA_CST_ENTRADA: dict[str, str] = {
    '101': '00',  # tributado integralmente
    '102': '41',  # não tributado
    '103': '40',  # isento
    '201': '10',  # tributado + ST
    '202': '10',
    '203': '10',
    '300': '40',  # isento
    '400': '41',  # não tributado
    '500': '60',  # cobrado anteriormente por ST
    '900': '90',  # outros
}


def _normalizar_csosn(csosn: str) -> str:
    digits = ''.join(ch for ch in (csosn or '').strip() if ch.isdigit())
    if not digits:
        return ''
    if len(digits) <= 3:
        return digits.zfill(3)
    return digits[-3:]


def converter_csosn_para_cst_entrada(csosn: str) -> str:
    """Converte CSOSN (Simples Nacional) para CST ICMS de entrada (regime normal)."""
    code = _normalizar_csosn(csosn)
    if not code:
        return ''
    return _CSOSN_PARA_CST_ENTRADA.get(code, '')
