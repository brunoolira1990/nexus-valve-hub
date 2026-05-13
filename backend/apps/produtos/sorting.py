"""Ordenação natural para códigos de figura, produto, schedule e rosca (sem alterar valores salvos)."""

from __future__ import annotations

import re
from decimal import Decimal

_RE_LEADING_DIGITS = re.compile(r'^(\d+)(.*)$', re.DOTALL)


def natural_codigo_figura_key(codigo: str) -> tuple:
    """
    Ordenação natural de código figura/família.
    Prefixo numérico como inteiro (preserva ordem 9 < 10); sufixo alfanumérico em maiúsculas.
    Códigos que não começam com dígito ficam após os numéricos.
    """
    s = (codigo or '').strip()
    if not s:
        return (2, '', '')
    m = _RE_LEADING_DIGITS.match(s)
    if m:
        return (0, int(m.group(1)), m.group(2).upper())
    return (1, s.upper(), '')


def _segment_key(seg: str) -> tuple:
    seg = (seg or '').strip()
    if not seg:
        return (2, '', '')
    m = _RE_LEADING_DIGITS.match(seg)
    if m:
        return (0, int(m.group(1)), m.group(2).upper())
    return (1, seg.upper(), '')


def natural_codigo_completo_key(codigo: str) -> tuple:
    """
    Ordenação natural de código interno de produto (segmentos separados por '.').
    Ex.: 068840.09 < 068840.12; 0029BSP.04 ordena antes de 0075OD.13 pelo primeiro segmento.
    """
    s = (codigo or '').strip()
    if not s:
        return ()
    parts = s.split('.')
    return tuple(_segment_key(p) for p in parts)


# Ordem técnica aproximada para schedules comuns (índice menor = mais fino / antes).
_SCHEDULE_PRIORITY = [
    '5S',
    '10S',
    '10',
    '20',
    '30',
    '40',
    '40S',
    'STD',
    '60',
    '80',
    '80S',
    'XS',
    '100',
    '120',
    '140',
    '160',
    'XXS',
]


def _schedule_canonical(code: str) -> str:
    c = (code or '').strip().upper().replace(' ', '')
    if c.startswith('SCH'):
        c = c[3:]
    return c


def schedule_ordenacao_tuple(
    *,
    ordem: int | None,
    codigo_schedule: str,
    codigo: str,
) -> tuple:
    """Campo `ordem` primeiro; depois prioridade técnica; por fim texto estável."""
    raw = (codigo_schedule or codigo or '').strip()
    can = _schedule_canonical(raw)
    try:
        pri = _SCHEDULE_PRIORITY.index(can)
    except ValueError:
        m = re.match(r'^(\d+)$', can)
        if m:
            pri = 2000 + int(m.group(1))
        else:
            pri = 9999
    o = ordem if ordem is not None else 10**6
    return (o, pri, can.upper(), raw.upper())


_ROSCA_PRIORITY = ['BSP', 'NPT', 'BSPT', 'SW', 'TC', 'FL']


def rosca_ordenacao_tuple(codigo: str) -> tuple:
    c = (codigo or '').strip().upper()
    if not c:
        return (2, '', '')
    try:
        return (0, _ROSCA_PRIORITY.index(c), c)
    except ValueError:
        return (1, c, '')


def polegada_ordenacao_tuple(
    *,
    valor_decimal: Decimal | None,
    valor_mm: Decimal | None,
    codigo_oficial: str,
) -> tuple:
    """Ordenar polegada por medida real; nulls por último."""
    v = valor_decimal
    if v is None:
        v = Decimal('999999999')
    mm = valor_mm
    if mm is None:
        mm = Decimal('999999999')
    co = (codigo_oficial or '').strip().upper()
    return (v, mm, co)
