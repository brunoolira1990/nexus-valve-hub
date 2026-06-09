"""Helpers para extrair e comparar texto de PDFs DANFE (pypdf fragmenta palavras)."""

from __future__ import annotations

import io
import re
import unicodedata

from pypdf import PdfReader


def pdf_text(pdf: bytes) -> str:
    return ''.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)


def norm_pdf_text(t: str) -> str:
    t = unicodedata.normalize('NFKD', t)
    return ''.join(c for c in t if not unicodedata.combining(c)).upper()


def compact_pdf_text(t: str) -> str:
    """Normaliza e remove espaços/quebras para asserts estáveis em texto extraído de PDF."""
    t = norm_pdf_text(t)
    t = re.sub(r'\s+', '', t)
    return t.replace('-', '').replace(':', '').replace('.', '')
