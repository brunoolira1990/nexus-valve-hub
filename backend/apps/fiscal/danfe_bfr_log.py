"""ERP 4.0.13.6.13A — logs do renderizador oficial DANFE (BFR)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings

logger = logging.getLogger('apps.fiscal.danfe_bfr')

_PREFIX_ERROR = '[DANFE_BFR_ERROR]'
_PREFIX_FALLBACK = '[DANFE_FALLBACK_BLOQUEADO]'


def danfe_log_renderer_habilitado() -> bool:
    return bool(getattr(settings, 'DANFE_LOG_RENDERER', True))


def novo_trace_id() -> str:
    return uuid.uuid4().hex[:12]


def log_danfe_bfr_erro(
    *,
    nfe_id: int | None,
    numero: str | None,
    status: str | None,
    ambiente: str | None,
    erro_tipo: str,
    erro_mensagem: str,
    trace_id: str | None = None,
    **extras: Any,
) -> str:
    tid = trace_id or novo_trace_id()
    if not danfe_log_renderer_habilitado():
        return tid
    partes = [
        f'{_PREFIX_ERROR}',
        f'nfe_id={nfe_id}',
        f'numero={numero or ""}',
        f'status={status or ""}',
        f'ambiente={ambiente or ""}',
        f'erro_tipo={erro_tipo}',
        f'erro_mensagem={erro_mensagem}',
        f'trace_id={tid}',
    ]
    for k, v in extras.items():
        if v is not None:
            partes.append(f'{k}={v}')
    logger.error(' '.join(partes))
    return tid


def log_danfe_fallback_bloqueado(
    *,
    nfe_id: int | None,
    motivo: str,
    fallback: str = 'HTML/WeasyPrint',
    trace_id: str | None = None,
) -> None:
    if not danfe_log_renderer_habilitado():
        return
    tid = trace_id or novo_trace_id()
    logger.warning(
        '%s renderer_oficial=BFR fallback=%s nfe_id=%s motivo=%s trace_id=%s',
        _PREFIX_FALLBACK,
        fallback,
        nfe_id,
        motivo,
        tid,
    )
