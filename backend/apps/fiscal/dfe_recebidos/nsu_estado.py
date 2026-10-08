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


def _nsu_int(val: str | int | None) -> int:
    if val is None:
        return 0
    if isinstance(val, int):
        return max(val, 0)
    digits = ''.join(c for c in str(val) if c.isdigit())
    return int(digits) if digits else 0


def _recuperar_nsu_fallback_banco(empresa_id: int, tipo_documento: str) -> int:
    """
    Recupera último NSU conhecido no banco quando o cache expirou/reiniciou.
    Conservador: usa o maior NSU já persistido em resumos destinados (NF-e).
    """
    if tipo_documento.upper() != 'NFE':
        return 0
    from django.db.models import Max

    from apps.fiscal.models import NFeDestinadaManifestacao

    max_nsu_str = (
        NFeDestinadaManifestacao.objects.filter(
            empresa_id=empresa_id,
            ambiente=NFeDestinadaManifestacao.Ambiente.PRODUCAO,
        )
        .exclude(nsu='')
        .aggregate(m=Max('nsu'))
        .get('m')
    )
    return _nsu_int(max_nsu_str)


def carregar_estado_nsu(empresa_id: int, tipo_documento: str) -> EstadoNsuCaptura:
    raw = cache.get(_cache_key(empresa_id, tipo_documento))
    if isinstance(raw, dict):
        ultimo = int(raw.get('ultimo_nsu') or 0)
        fallback = _recuperar_nsu_fallback_banco(empresa_id, tipo_documento)
        ultimo = max(ultimo, fallback)
        return EstadoNsuCaptura(
            ultimo_nsu=ultimo,
            max_nsu=int(raw.get('max_nsu') or 0),
            ultima_consulta_em=raw.get('ultima_consulta_em'),
            status_ultima_consulta=str(raw.get('status_ultima_consulta') or ''),
            mensagem_ultima_consulta=str(raw.get('mensagem_ultima_consulta') or ''),
        )
    fallback = _recuperar_nsu_fallback_banco(empresa_id, tipo_documento)
    if fallback > 0:
        return EstadoNsuCaptura(ultimo_nsu=fallback)
    return EstadoNsuCaptura()


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
