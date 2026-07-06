"""
Normalização de CST IPI do XML (perspectiva do emitente) para comparação na entrada.

Na NF-e de compra, o fornecedor informa CST de saída; a regra fiscal de entrada
espera o CST do destinatário. Correlação oficial: saída 50-55 → entrada 00-05, 99 → 49.
CSTs já de entrada (00-05, 49) permanecem iguais.
"""

from __future__ import annotations

# CST de saída (fornecedor) → equivalente na entrada (destinatário).
# CSTs não listados permanecem iguais.
_CST_SAIDA_PARA_ENTRADA: dict[str, str] = {
    '50': '00',  # saída tributada → entrada com recuperação de crédito
    '51': '01',  # saída tributada alíquota zero → entrada
    '52': '02',  # saída isenta → entrada isenta
    '53': '03',  # saída não tributada → entrada não tributada
    '54': '04',  # saída imune → entrada imune
    '55': '05',  # saída com suspensão → entrada com suspensão
    '99': '49',  # outros
}


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
    return _CST_SAIDA_PARA_ENTRADA.get(cod, cod)
