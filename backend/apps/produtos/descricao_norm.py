"""Descrição comercial operacional: maiúsculas sem acento (símbolos técnicos preservados)."""

from __future__ import annotations

import re
import unicodedata


def normalizar_descricao_produto(texto: str) -> str:
    if texto is None:
        return ''
    s = str(texto).strip()
    if not s:
        return ''
    nkfd = unicodedata.normalize('NFKD', s)
    sem_acento = ''.join(ch for ch in nkfd if unicodedata.category(ch) != 'Mn')
    colapsado = re.sub(r'\s+', ' ', sem_acento).strip()
    return colapsado.upper()
