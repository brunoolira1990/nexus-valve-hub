"""Exibição de número de faturamento — oculta sufixo LEGADO na UI."""

from __future__ import annotations

import re

_RE_FAT_LEGADO = re.compile(r'^FAT-LEGADO-(\d{8})-(\d+)$', re.I)


def normalizar_numero_faturamento_exibicao(numero: str | None) -> str:
    """FAT-LEGADO-20260522-0002 → FAT-20260522-0002 (somente apresentação)."""
    raw = (numero or '').strip()
    if not raw:
        return ''
    m = _RE_FAT_LEGADO.match(raw)
    if m:
        return f'FAT-{m.group(1)}-{int(m.group(2)):04d}'
    return raw


def numero_faturamento_exibicao_faturamento(faturamento) -> str:
    if faturamento is None:
        return ''
    bruto = (getattr(faturamento, 'numero_faturamento', None) or '').strip()
    if bruto:
        return normalizar_numero_faturamento_exibicao(bruto)
    pk = getattr(faturamento, 'pk', None)
    if pk:
        dt = getattr(faturamento, 'criado_em', None)
        if dt:
            return f'FAT-{dt.strftime("%Y%m%d")}-{pk:04d}'
        return f'FAT-{pk:04d}'
    return ''
