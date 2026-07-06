"""
Normalização de CST ICMS do XML (perspectiva do emitente) para comparação na entrada.

Na NF-e de compra, o fornecedor informa CST de saída; a regra fiscal de entrada
espera o CST do destinatário. O valor no XML pode incluir o dígito de origem
(Tabela A) antes da situação tributária (Tabela B, 2 dígitos).

Em operações com ST retida, códigos distintos podem ser fiscalmente equivalentes
(ex.: 10/30/70 na saída → 60 na entrada).
"""

from __future__ import annotations

# Situação tributária de saída (fornecedor) → equivalente na entrada (destinatário).
# CSTs não listados permanecem iguais (00, 20, 40, 41, 50, 51, 60, 90).
_CST_SAIDA_PARA_ENTRADA: dict[str, str] = {
    '10': '60',  # tributado + ST → recebido com ST retida
    '30': '60',  # isento + ST → recebido com ST retida
    '70': '60',  # redução BC + ST → recebido com ST retida
}


def _situacao_tributaria(cst: str) -> str:
    """
    Extrai os 2 últimos dígitos (Tabela B), ignorando dígito de origem quando presente.

    Ex.: "210" → "10", "060" → "60", "10" → "10", "00" → "00".
    """
    digits = ''.join(ch for ch in (cst or '').strip() if ch.isdigit())
    if not digits:
        return ''
    if len(digits) <= 2:
        return digits.zfill(2)
    return digits[-2:]


def normalizar_cst_icms_xml_para_entrada(cst: str) -> str:
    """Converte CST ICMS lido do XML para a perspectiva de entrada antes de comparar com a regra."""
    situacao = _situacao_tributaria(cst)
    if not situacao:
        return ''
    return _CST_SAIDA_PARA_ENTRADA.get(situacao, situacao)
