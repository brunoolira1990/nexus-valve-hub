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

# Separadores de tokens na consulta (hífen, barra, espaço).
_RE_SEP_TOKENS = re.compile(r'[\s\-/]+')


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


def tokenizar_busca_numero_documento(term: str | None) -> list[str]:
    """
    Divide a consulta em tokens por hífen, barra ou espaço.

    Cada token é normalizado (maiúsculas, sem separadores internos).
    Ordem preservada; tokens vazios descartados.
    """
    bruto = termo_busca_numero_documento(term)
    if not bruto:
        return []
    out: list[str] = []
    for parte in _RE_SEP_TOKENS.split(bruto):
        tok = _corpo_sem_separadores(parte)
        if tok:
            out.append(tok)
    return out


def expr_numero_documento_normalizado(field: str):
    """Expressão ORM: Upper(campo) sem espaço, hífen ou barra."""
    expr = Upper(F(field))
    for sep in ('-', ' ', '/'):
        expr = Replace(expr, Value(sep), Value(''), output_field=CharField())
    return expr


def _padrao_tokens_em_ordem(tokens: list[str]) -> str:
    """Regex: todos os tokens, nesta ordem, como substrings (qualquer coisa entre eles)."""
    return '.*'.join(re.escape(t) for t in tokens)


def filtrar_queryset_por_numeros_documento(
    qs: QuerySet,
    term: str | None,
    *fields: str,
    q_extra: Q | None = None,
) -> QuerySet:
    """
    Filtra por correspondência parcial em campos de número documental.

    - Literal ``icontains`` no termo bruto informado.
    - Um token: contains no valor sem separadores.
    - Vários tokens (separados por hífen/barra/espaço): todos devem aparecer
      no número normalizado **nesta ordem** (sem fuzzy; dígitos inexistentes
      não são ignorados). Ex.: ``0714-0010`` casa ``PV-20260714-0010``;
      ``074-0010`` não.

    ``q_extra`` é OR-ado (ex.: busca por nome do cliente) e usa o termo bruto.
    """
    bruto = termo_busca_numero_documento(term)
    if not bruto:
        return qs.filter(q_extra) if q_extra is not None else qs

    tokens = tokenizar_busca_numero_documento(bruto)
    annotations: dict = {}
    q = Q()
    for idx, field in enumerate(fields):
        if not field:
            continue
        q |= Q(**{f'{field}__icontains': bruto})
        if not tokens:
            continue
        alias = f'_ndoc_busca_{idx}_{field.replace("__", "_")}'
        annotations[alias] = expr_numero_documento_normalizado(field)
        if len(tokens) == 1:
            q |= Q(**{f'{alias}__icontains': tokens[0]})
        else:
            q |= Q(**{f'{alias}__regex': _padrao_tokens_em_ordem(tokens)})

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
