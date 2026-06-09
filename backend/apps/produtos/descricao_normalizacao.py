"""Normalização de descrições para matching de equivalência — ERP 4.0.13.7."""

from __future__ import annotations

import re
import unicodedata


_RE_NAO_ALFANUM = re.compile(r'[^A-Z0-9\s/]+')
_RE_ESPACOS = re.compile(r'\s+')

_SUBSTITUICOES = (
    (r'\b4\s*POL(?:EGADAS?)?\b', '4P'),
    (r'\b4\s*"\b', '4P'),
    (r'\b4P\b', '4P'),
    (r'\b2\s*POL(?:EGADAS?)?\b', '2P'),
    (r'\b2\s*"\b', '2P'),
    (r'\b2P\b', '2P'),
    (r'\b1\s*1/2\b', '1-1/2P'),
    (r'\b1\.1/2\b', '1-1/2P'),
    (r'\b1-1/2\b', '1-1/2P'),
    (r'\bACO\s+INOX\s+304\b', 'INOX304'),
    (r'\bINOX\s+304\b', 'INOX304'),
    (r'\b304\b', 'INOX304'),
    (r'\bACO\s+CARBONO\b', 'ACCARBONO'),
    (r'\bAC\s+CARBONO\b', 'ACCARBONO'),
    (r'\bFERRO\s+FUNDIDO\b', 'FERROFUNDIDO'),
    (r'\bFF\b', 'FERROFUNDIDO'),
    (r'\bANSI\s+150\s*#?\b', 'ANSI150'),
    (r'\bCL\s*150\b', 'ANSI150'),
    (r'\b150\s*#\b', 'ANSI150'),
    (r'\bFACE\s+RESSALTO\b', 'RF'),
    (r'\bRF\b', 'RF'),
    (r'\bABRACADEIRA\b', 'ABRACADEIRA'),
    (r'\bNIPLE\b', 'NIPLE'),
    (r'\bESPIGAO\b', 'ESPIGAO'),
    (r'\bANEL\s+DE\s+VEDACAO\b', 'ANELVEDACAO'),
    (r'\bVEDACAO\b', 'VEDACAO'),
    (r'\bFLANGE\b', 'FLANGE'),
    (r'\bREDUCAO\b', 'REDUCAO'),
    (r'\bUNIAO\s+TC\b', 'UNIAOTC'),
    (r'\bTC\b', 'TC'),
    (r'\bCURTA\b', 'CURTA'),
    (r'\bSILICONE\b', 'SILICONE'),
    (r'\bCOMPLETA\b', 'COMPLETA'),
)


def remover_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_descricao_produto(descricao: str | None) -> str:
    """Normaliza descrição para busca/matching de equivalência."""
    raw = remover_acentos((descricao or '').upper().strip())
    raw = _RE_NAO_ALFANUM.sub(' ', raw)
    for pattern, repl in _SUBSTITUICOES:
        raw = re.sub(pattern, repl, raw, flags=re.IGNORECASE)
    return _RE_ESPACOS.sub(' ', raw).strip()


def normalizar_codigo_fornecedor(codigo: str | None) -> str:
    return (codigo or '').strip().upper()


def tokens_normalizados(descricao: str | None) -> set[str]:
    norm = normalizar_descricao_produto(descricao)
    return {t for t in norm.split() if len(t) >= 2}


def similaridade_descricao(a: str | None, b: str | None) -> float:
    ta = tokens_normalizados(a)
    tb = tokens_normalizados(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0
