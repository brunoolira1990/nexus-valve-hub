"""Formatação reutilizável para PDFs (moeda, decimal, data, CNPJ, telefone)."""

from __future__ import annotations

from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph


def dec(v) -> Decimal:
    if v is None:
        return Decimal('0')
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def format_currency_br(v) -> str:
    """Ex.: R$ 5.000,00"""
    try:
        return f'R$ {dec(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return 'R$ 0,00'


def format_decimal_br(v) -> str:
    """Quantidade: inteiro sem decimais; senão até 2 casas com vírgula."""
    d = dec(v)
    try:
        if d == d.to_integral_value():
            return str(int(d))
        q = d.quantize(Decimal('0.01'))
        return f'{q:.2f}'.replace('.', ',')
    except Exception:
        return '0'


def format_date_br(d) -> str:
    if not d:
        return '—'
    if isinstance(d, str):
        s = d.strip()
        if not s:
            return '—'
        try:
            from datetime import date, datetime

            if 'T' in s:
                return datetime.fromisoformat(s.replace('Z', '+00:00')[:19]).strftime('%d/%m/%Y')
            return date.fromisoformat(s[:10]).strftime('%d/%m/%Y')
        except ValueError:
            return s[:10] if len(s) >= 10 else '—'
    try:
        return d.strftime('%d/%m/%Y')
    except Exception:
        return '—'


def format_cnpj(raw: str) -> str:
    s = ''.join(c for c in str(raw or '') if c.isdigit())
    if len(s) != 14:
        return str(raw or '').strip() or '—'
    return f'{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}'


def format_phone(*parts: str) -> str:
    """Concatena telefones não vazios (ex.: fixo + celular)."""
    s = ' · '.join((p or '').strip() for p in parts if (p or '').strip())
    return s if s else ''


def endereco_cadastro(
    logradouro: str,
    numero: str,
    complemento: str,
    bairro: str,
    cidade: str,
    uf: str,
    cep: str,
) -> str:
    parts = [
        ' '.join(filter(None, [logradouro or '', numero or ''])).strip(),
        (complemento or '').strip(),
        (bairro or '').strip(),
        ' '.join(filter(None, [cidade or '', uf or ''])).strip(),
        (cep or '').strip(),
    ]
    parts = [p for p in parts if p]
    return ', '.join(parts) if parts else '—'


def txt_or_emdash(v) -> str:
    s = (v or '').strip()
    return s if s else '—'


def nobr(s: str) -> str:
    return f'<nobr>{escape(str(s))}</nobr>'


def money_nobr(v) -> str:
    return nobr(format_currency_br(v))


def p_cell(text: str, style: ParagraphStyle, *, max_len: int = 4000) -> Paragraph:
    t = escape(str(text or '—')[:max_len]).replace('\n', '<br/>')
    return Paragraph(t, style)


# Aliases legados / nomes alternativos
money_br = format_currency_br
qty_br = format_decimal_br
fmt_date_br = format_date_br
fmt_cnpj = format_cnpj
