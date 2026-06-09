"""Registro de histórico financeiro."""

from __future__ import annotations

from typing import Any

from apps.financeiro.models import FinanceiroEvento, TituloFinanceiro


def registrar_evento_financeiro(
    titulo: TituloFinanceiro,
    *,
    acao: str,
    descricao: str,
    usuario=None,
    dados_anteriores: dict[str, Any] | None = None,
    dados_novos: dict[str, Any] | None = None,
) -> FinanceiroEvento:
    return FinanceiroEvento.objects.create(
        titulo=titulo,
        acao=acao,
        descricao=descricao[:512],
        usuario=usuario,
        dados_anteriores=dados_anteriores or {},
        dados_novos=dados_novos or {},
    )
