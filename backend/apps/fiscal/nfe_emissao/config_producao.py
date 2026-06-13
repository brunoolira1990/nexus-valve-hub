"""Feature flag e guards — emissão NF-e Saída produção SEFAZ (Fase 3B)."""

from __future__ import annotations

from django.conf import settings

MSG_PRODUCAO_NAO_HABILITADA = 'Emissão NF-e produção não habilitada.'
CONFIRMACAO_AMBIENTE_PRODUCAO = 'PRODUCAO_SEFAZ'
MSG_CONFIRMACAO_OBRIGATORIA = (
    'Confirmação explícita obrigatória: '
    'confirmar_emissao_producao=true e confirmar_ambiente="PRODUCAO_SEFAZ".'
)


class NFeProducaoDesabilitadaError(PermissionError):
    """Produção SEFAZ bloqueada — flag ausente ou false."""


class NFeProducaoConfirmacaoError(ValueError):
    """Payload sem confirmação explícita de emissão produção."""


def nfe_producao_habilitada() -> bool:
    return bool(getattr(settings, 'NFE_PRODUCAO_HABILITADA', False))


def exigir_producao_habilitada() -> None:
    if not nfe_producao_habilitada():
        raise NFeProducaoDesabilitadaError(MSG_PRODUCAO_NAO_HABILITADA)


def validar_confirmacao_emissao_producao(payload: dict | None) -> None:
    data = payload or {}
    if not data.get('confirmar_emissao_producao'):
        raise NFeProducaoConfirmacaoError(MSG_CONFIRMACAO_OBRIGATORIA)
    ambiente = (data.get('confirmar_ambiente') or '').strip()
    if ambiente != CONFIRMACAO_AMBIENTE_PRODUCAO:
        raise NFeProducaoConfirmacaoError(MSG_CONFIRMACAO_OBRIGATORIA)
