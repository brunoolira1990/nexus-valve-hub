"""Numeração operacional: prefixo + dígitos contíguos (padrão Certificado Qualidade CQ{n}).

Também oferece busca parcial server-side tolerante a separadores (ERP 4.0.14.x).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.db.models import CharField, F, Q, Value
from django.db.models.functions import Replace, Upper

if TYPE_CHECKING:
    from django.db.models import QuerySet


def formatar_numero_documento(prefix: str, sequencial: int) -> str:
    """Ex.: prefixo CQ, sequencial 100 → CQ100."""
    p = prefix.upper()
    return f'{p}{int(sequencial)}'


def _corpo_sem_separadores(numero: str) -> str:
    t = (numero or '').strip().upper()
    for sep in (' ', '-', '/'):
        t = t.replace(sep, '')
    return t


def termo_busca_numero_documento(term: str | None) -> str:
    """Consulta de busca: trim nas bordas (sem fuzzy)."""
    return (term or '').strip()


def termo_busca_numero_documento_normalizado(term: str | None) -> str:
    """Termo sem espaços/hífens/barras, em maiúsculas — só para comparação."""
    return _corpo_sem_separadores(termo_busca_numero_documento(term))


def expr_numero_documento_normalizado(field: str):
    """Expressão ORM: Upper(campo) sem espaço, hífen ou barra."""
    expr = Upper(F(field))
    for sep in ('-', ' ', '/'):
        expr = Replace(expr, Value(sep), Value(''), output_field=CharField())
    return expr


def filtrar_queryset_por_numeros_documento(
    qs: QuerySet,
    term: str | None,
    *fields: str,
    q_extra: Q | None = None,
) -> QuerySet:
    """
    Filtra por correspondência parcial (contains) em campos de número documental.

    - Literal ``icontains`` no termo informado (case-insensitive no banco).
    - OU contains no valor/campo sem separadores (ex.: PV202607140006 ↔ PV-20260714-0006).

    Não usa fuzzy matching. ``q_extra`` é OR-ado (ex.: busca por nome do cliente).
    """
    bruto = termo_busca_numero_documento(term)
    if not bruto:
        return qs.filter(q_extra) if q_extra is not None else qs

    norm = termo_busca_numero_documento_normalizado(bruto)
    annotations: dict = {}
    q = Q()
    for idx, field in enumerate(fields):
        if not field:
            continue
        q |= Q(**{f'{field}__icontains': bruto})
        if norm:
            alias = f'_ndoc_busca_{idx}_{field.replace("__", "_")}'
            annotations[alias] = expr_numero_documento_normalizado(field)
            q |= Q(**{f'{alias}__icontains': norm})

    if q_extra is not None:
        q |= q_extra
    if not q and q_extra is None:
        return qs
    if annotations:
        qs = qs.annotate(**annotations)
    return qs.filter(q)


def normalizar_numero_documento(numero: str, prefix: str) -> str:
    """
    Alinha ao tratamento de CertificadoQualidade (_normalize_numero_cq):
    maiúsculas, sem espaço/hífen entre prefixo e sequência.
    """
    p = prefix.upper()
    cleaned = _corpo_sem_separadores(numero)
    if not cleaned:
        return ''
    while cleaned.startswith(p + p):
        cleaned = cleaned[len(p) :]
    if not cleaned.startswith(p):
        cleaned = f'{p}{cleaned}'
    sufixo = cleaned[len(p) :]
    if sufixo.isdigit():
        return f'{p}{int(sufixo)}'
    return cleaned


def extrair_sequencial_documento(numero: str, prefix: str) -> int | None:
    """
    Extrai o inteiro sequencial de números no padrão atual (PROP42, PV7)
    ou legado Comercial 2.2 (PROP-000042, PV-000007).
    Não interpreta números compostos de conversão (ex.: PV-PROP-…).
    """
    raw = (numero or '').strip()
    if not raw:
        return None
    p = prefix.upper()
    m_legado = re.match(rf'^{re.escape(p)}-(\d+)$', raw, re.I)
    if m_legado:
        return int(m_legado.group(1))
    norm = _corpo_sem_separadores(raw)
    if not norm.startswith(p):
        return None
    sufixo = norm[len(p) :]
    if not sufixo.isdigit():
        return None
    return int(sufixo)
