"""ERP 4.0.13.6.12 — medição de performance da conferência NF-e ([NFE_PERF])."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

from django.conf import settings
from django.db import connection

logger = logging.getLogger('apps.fiscal.nfe_perf')

_PREFIX = '[NFE_PERF]'


def nfe_perf_habilitado() -> bool:
    """Logs verbosos somente em desenvolvimento/homologação."""
    return bool(getattr(settings, 'NFE_PERF_LOGGING', False))


class NFePerfTracker:
    """Acumula tempos parciais e contagem de queries SQL."""

    def __init__(self, acao: str, *, nfe_id: int | None = None) -> None:
        self.acao = acao
        self.nfe_id = nfe_id
        self.inicio = time.perf_counter()
        self.parciais: dict[str, float] = {}
        self.queries_inicio = len(connection.queries) if nfe_perf_habilitado() else 0

    def marcar(self, etapa: str) -> None:
        if not nfe_perf_habilitado():
            return
        self.parciais[etapa] = round((time.perf_counter() - self.inicio) * 1000, 1)

    def queries(self) -> int:
        if not nfe_perf_habilitado():
            return 0
        return max(0, len(connection.queries) - self.queries_inicio)

    def total_ms(self) -> float:
        return round((time.perf_counter() - self.inicio) * 1000, 1)

    def emitir(self, **extras: Any) -> None:
        if not nfe_perf_habilitado():
            return
        partes = [f'{k}={v}' for k, v in self.parciais.items()]
        for k, v in extras.items():
            if v is not None:
                partes.append(f'{k}={v}')
        id_part = f' id={self.nfe_id}' if self.nfe_id else ''
        msg = f'{_PREFIX} {self.acao}{id_part} total_ms={self.total_ms()} queries={self.queries()}'
        if partes:
            msg = f'{msg} ' + ' '.join(partes)
        logger.info(msg)


@contextmanager
def medir_nfe_perf(acao: str, *, nfe_id: int | None = None, **extras: Any) -> Iterator[NFePerfTracker]:
    tracker = NFePerfTracker(acao, nfe_id=nfe_id)
    try:
        yield tracker
    finally:
        tracker.emitir(**extras)
