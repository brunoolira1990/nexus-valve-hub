"""Utilitários CNPJ para equivalência por raiz/filial — ERP 4.0.13.7."""

from __future__ import annotations

from apps.cadastros.utils import normalizar_cnpj


def cnpj_apenas_digitos(cnpj: str | None) -> str:
    """Retorna o CNPJ canônico; o nome é mantido por compatibilidade legada."""
    return normalizar_cnpj(cnpj)


def cnpj_raiz(cnpj: str | None) -> str:
    """Retorna os oito caracteres-base, numéricos ou alfanuméricos."""
    canonico = normalizar_cnpj(cnpj)
    return canonico[:8] if len(canonico) >= 8 else canonico
