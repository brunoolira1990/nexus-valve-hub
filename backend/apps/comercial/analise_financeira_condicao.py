"""Normalização canônica da condição de pagamento para liberação financeira."""

from __future__ import annotations

from typing import Any

from apps.comercial.payment_terms import (
    _is_indeterminate_payment,
    _normalize_text,
    pagamento_integralmente_a_vista,
    parse_payment_condition,
)
from rest_framework import serializers


class CondicaoAmbiguaError(ValueError):
    """Condição vazia, indeterminada ou não normalizável com segurança."""


def modalidade_de_dias(dias: list[int]) -> str:
    if pagamento_integralmente_a_vista(dias):
        return 'AVISTA'
    if dias and 0 in dias and any(d > 0 for d in dias):
        return 'ENTRADA_E_SALDO'
    if dias and all(d > 0 for d in dias):
        return 'PARCELADO'
    return 'INDEFINIDA'


def texto_exibicao_dias(dias: list[int]) -> str:
    if not dias:
        return ''
    if pagamento_integralmente_a_vista(dias):
        return 'À vista'
    return '/'.join(str(d) for d in dias)


def normalizar_condicao_de_proposta(
    *,
    texto: str | None,
    dias_parcelas: list[int] | None,
) -> dict[str, Any]:
    """
    Representação canônica usada na análise e no guard de conversão.

    Não altera o parser global: apenas consome o plano já persistido ou tenta
    parse seguro. Lista vazia / indeterminada → CondicaoAmbíguaError.
    """
    dias = [int(d) for d in (dias_parcelas or [])]
    texto_limpo = (texto or '').strip()

    if not dias and texto_limpo:
        normalized = _normalize_text(texto_limpo)
        if _is_indeterminate_payment(normalized):
            raise CondicaoAmbiguaError(
                'Condição de pagamento indeterminada. Solicite análise financeira.'
            )
        try:
            dias = parse_payment_condition(texto_limpo)
        except serializers.ValidationError as exc:
            raise CondicaoAmbiguaError(
                'Condição de pagamento não reconhecida. Solicite análise financeira.'
            ) from exc

    if not dias:
        raise CondicaoAmbiguaError(
            'Condição de pagamento ausente ou ambígua. Solicite análise financeira.'
        )

    if any(d < 0 for d in dias):
        raise CondicaoAmbiguaError('Condição de pagamento inválida (dias negativos).')

    dias_ord = sorted(dias)
    return {
        'texto': texto_exibicao_dias(dias_ord) or texto_limpo,
        'dias': dias_ord,
        'quantidade_parcelas': len(dias_ord),
        'modalidade': modalidade_de_dias(dias_ord),
        'maior_prazo_dias': max(dias_ord) if dias_ord else 0,
    }


def condicoes_iguais(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if not a or not b:
        return False
    return list(a.get('dias') or []) == list(b.get('dias') or [])


def possui_pagamento_futuro(condicao: dict[str, Any]) -> bool:
    dias = list(condicao.get('dias') or [])
    if not dias:
        return True  # ambígua → exige análise
    return any(int(d) > 0 for d in dias)


def condicao_aprovada_permitida_mvp(dias: list[int]) -> bool:
    """MVP: qualquer lista não vazia de dias >= 0, ordenada, sem percentuais custom."""
    if not dias:
        return False
    if any(int(d) < 0 for d in dias):
        return False
    return True
