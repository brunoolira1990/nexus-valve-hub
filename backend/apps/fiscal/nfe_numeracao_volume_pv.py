"""Numeração compacta de volumes a partir do número do Pedido de Venda.

Convenção operacional (ERP 4.0.14.x):
  PV-AAAAMMDD-NNNN → AAMMDD-NNNN
  Ex.: PV-20260714-0042 → 260714-0042
"""

from __future__ import annotations

import re
from datetime import date

# Formato completo obrigatório — sem split permissivo.
_RE_NUMERO_PV = re.compile(r'^PV-(\d{4})(\d{2})(\d{2})-(\d{4})$')


def compactar_numero_pedido_venda(numero: str | None) -> str | None:
    """Deriva a referência compacta do PV para `NFeSaida.numeracao_volumes`.

    Retorna ``None`` se ausente, legado, incompleto ou com data inválida.
    Não cria contador nem tenta corrigir formatos parciais.
    """
    if numero is None:
        return None
    bruto = str(numero).strip()
    if not bruto:
        return None
    m = _RE_NUMERO_PV.fullmatch(bruto)
    if not m:
        return None
    ano_s, mes_s, dia_s, seq = m.group(1), m.group(2), m.group(3), m.group(4)
    try:
        date(int(ano_s), int(mes_s), int(dia_s))
    except ValueError:
        return None
    return f'{ano_s[2:]}{mes_s}{dia_s}-{seq}'


def sugerir_numeracao_volumes_pedido(
    numero_pedido: str | None,
    numeracao_atual: str | None = None,
) -> str | None:
    """Sugere compacto somente se a numeração atual estiver vazia."""
    if (numeracao_atual or '').strip():
        return None
    return compactar_numero_pedido_venda(numero_pedido)
