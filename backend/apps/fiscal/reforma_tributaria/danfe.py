"""DANFE — seção Reforma Tributária (somente quando flag + paridade XML)."""

from __future__ import annotations

from typing import Any

from apps.fiscal.reforma_tributaria.validacoes import reforma_pode_incluir_no_danfe


def montar_secao_reforma_danfe(dados: dict[str, Any], nf) -> str:
    """Texto informativo para DANFE; vazio se RTC não incluída."""
    if not reforma_pode_incluir_no_danfe():
        return ''
    _ = dados, nf
    return ''
