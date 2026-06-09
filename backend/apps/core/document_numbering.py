"""Numeração operacional: prefixo + dígitos contíguos (padrão Certificado Qualidade CQ{n})."""

from __future__ import annotations

import re


def formatar_numero_documento(prefix: str, sequencial: int) -> str:
    """Ex.: prefixo CQ, sequencial 100 → CQ100."""
    p = prefix.upper()
    return f'{p}{int(sequencial)}'


def _corpo_sem_separadores(numero: str) -> str:
    return (numero or '').strip().upper().replace(' ', '').replace('-', '')


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
