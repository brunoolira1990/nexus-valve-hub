"""Utilitários CNPJ para equivalência por raiz/filial — ERP 4.0.13.7."""

from __future__ import annotations


def cnpj_apenas_digitos(cnpj: str | None) -> str:
    return ''.join(c for c in (cnpj or '') if c.isdigit())


def cnpj_raiz(cnpj: str | None) -> str:
    digits = cnpj_apenas_digitos(cnpj)
    return digits[:8] if len(digits) >= 8 else digits
