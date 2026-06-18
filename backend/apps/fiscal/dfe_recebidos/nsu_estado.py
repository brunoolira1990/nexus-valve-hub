"""Estado de NSU para captura DF-e — cache temporário (sem migration de banco)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from django.core.cache import cache

_CACHE_PREFIX = 'dfe_captura_nsu'
_CACHE_TTL = 60 * 60 * 24 * 90  # 90 dias

AVISO_NSU_CACHE = (
    'Estado NSU temporário em cache; para uso contínuo em produção será necessária persistência em banco.'
)


@dataclass
class EstadoNsuCaptura:
    ultimo_nsu: int = 0
    max_nsu: int = 0
    ultima_consulta_em: str | None = None
    status_ultima_consulta: str = ''
    mensagem_ultima_consulta: str = ''


def _cache_key(empresa_id: int, tipo_documento: str, ambiente: str = 'producao') -> str:
    return f'{_CACHE_PREFIX}:{empresa_id}:{tipo_documento.upper()}:{ambiente}'


def carregar_estado_nsu(empresa_id: int, tipo_documento: str) -> EstadoNsuCaptura:
    raw = cache.get(_cache_key(empresa_id, tipo_documento))
    if not isinstance(raw, dict):
        return EstadoNsuCaptura()
    return EstadoNsuCaptura(
        ultimo_nsu=int(raw.get('ultimo_nsu') or 0),
        max_nsu=int(raw.get('max_nsu') or 0),
        ultima_consulta_em=raw.get('ultima_consulta_em'),
        status_ultima_consulta=str(raw.get('status_ultima_consulta') or ''),
        mensagem_ultima_consulta=str(raw.get('mensagem_ultima_consulta') or ''),
    )


def salvar_estado_nsu(
    empresa_id: int,
    tipo_documento: str,
    *,
    ultimo_nsu: int,
    max_nsu: int | None = None,
    status: str = '',
    mensagem: str = '',
) -> EstadoNsuCaptura:
    anterior = carregar_estado_nsu(empresa_id, tipo_documento)
    novo_ultimo = max(int(ultimo_nsu), anterior.ultimo_nsu)
    novo_max = int(max_nsu if max_nsu is not None else anterior.max_nsu)
    agora = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        'ultimo_nsu': novo_ultimo,
        'max_nsu': novo_max,
        'ultima_consulta_em': agora,
        'status_ultima_consulta': status,
        'mensagem_ultima_consulta': mensagem[:500],
    }
    cache.set(_cache_key(empresa_id, tipo_documento), payload, _CACHE_TTL)
    return EstadoNsuCaptura(**payload)
