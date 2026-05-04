from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def parse_polegada_to_decimal(raw: str) -> Decimal | None:
    txt = (raw or '').strip().replace('"', '').replace(',', '.')
    if not txt:
        return None
    txt = txt.replace('-', '.').replace(' ', '.')
    parts = [p for p in txt.split('.') if p]
    try:
        if len(parts) == 1:
            if '/' in parts[0]:
                n, d = parts[0].split('/', 1)
                return Decimal(n) / Decimal(d)
            return Decimal(parts[0])
        if len(parts) == 2 and '/' in parts[1]:
            i = Decimal(parts[0])
            n, d = parts[1].split('/', 1)
            return i + (Decimal(n) / Decimal(d))
        return Decimal(txt)
    except (InvalidOperation, ZeroDivisionError, ValueError):
        return None


def normalize_polegada_label(raw: str) -> str:
    dec = parse_polegada_to_decimal(raw)
    if dec is None:
        txt = (raw or '').strip()
        return txt if txt.endswith('"') else f'{txt}"' if txt else ''
    base = (raw or '').strip().replace('"', '')
    if '/' in base:
        base = base.replace('-', '.').replace(' ', '.')
        parts = [p for p in base.split('.') if p]
        if len(parts) == 2 and '/' in parts[1]:
            return f'{parts[0]}.{parts[1]}"'
        if len(parts) == 1:
            return f'{parts[0]}"'
    norm = f'{dec.normalize()}'
    return f'{norm}"'


def aliases_for_polegada(descricao: str, valor_decimal: Decimal, valor_mm: Decimal) -> list[str]:
    aliases = {
        (descricao or '').strip(),
        (descricao or '').replace('"', '').strip(),
        str(valor_decimal),
        str(valor_decimal).replace('.', ','),
        f'{valor_mm:.2f}',
        f'{valor_mm:.2f}'.replace('.', ','),
    }
    desc_clean = (descricao or '').strip().lower()
    if desc_clean in {'1/2"', '1/2'}:
        aliases.update({'meia', 'meio', '0.5', '0,5'})
    aliases = {a for a in aliases if a}
    return sorted(aliases)


def extract_mm_from_term(term: str) -> Decimal | None:
    txt = (term or '').strip().replace(',', '.')
    if not txt:
        return None
    if re.fullmatch(r'\d+(\.\d+)?', txt):
        try:
            return Decimal(txt)
        except InvalidOperation:
            return None
    return None
