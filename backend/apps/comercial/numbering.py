"""Comercial 2.2.1 — numeração automática no padrão Pedido de Compra (PREFIXO-AAAAMMDD-NNNN)."""

from __future__ import annotations

import re
from datetime import date

from apps.comercial.sequencia_diaria_numero import (
    alocar_numero_diario,
    coerce_data_referencia,
    formatar_numero_diario,
)

PREFIX_PROPOSTA = 'PROP'
PREFIX_PEDIDO_VENDA = 'PV'
PREFIX_FATURAMENTO = 'FAT'

TIPO_PROPOSTA = 'PROPOSTA'
TIPO_PEDIDO_VENDA = 'PEDIDO_VENDA'
TIPO_FATURAMENTO = 'FATURAMENTO'

_RE_DIARIO = re.compile(r'^([A-Z]+)-(\d{8})-(\d+)$', re.I)
_RE_LEGADO_HIFEN = re.compile(r'^([A-Z]+)-(\d+)$', re.I)


def formatar_numero_proposta(data: date, sequencial: int) -> str:
    return formatar_numero_diario(PREFIX_PROPOSTA, data, sequencial)


def formatar_numero_pedido_venda(data: date, sequencial: int) -> str:
    return formatar_numero_diario(PREFIX_PEDIDO_VENDA, data, sequencial)


def extrair_sequencial_diario(numero: str, prefix: str) -> tuple[date, int] | None:
    """Extrai (data, sequencial) de PROP-20260521-0001 / PV-20260521-0002."""
    raw = (numero or '').strip()
    if not raw:
        return None
    p = prefix.upper()
    m = _RE_DIARIO.match(raw)
    if not m or m.group(1).upper() != p:
        return None
    try:
        data_ref = date(int(m.group(2)[:4]), int(m.group(2)[4:6]), int(m.group(2)[6:8]))
    except ValueError:
        return None
    return data_ref, int(m.group(3))


def extrair_sequencial_proposta(numero: str) -> int | None:
    """
    Compatibilidade com legado PROP{n} / PROP-000042 e novo PROP-AAAAMMDD-NNNN.
    Para o padrão diário retorna apenas o sufixo numérico do dia.
    """
    par = extrair_sequencial_diario(numero, PREFIX_PROPOSTA)
    if par is not None:
        return par[1]
    raw = (numero or '').strip()
    if not raw:
        return None
    m = _RE_LEGADO_HIFEN.match(raw)
    if m and m.group(1).upper() == PREFIX_PROPOSTA:
        return int(m.group(2))
    norm = raw.upper().replace(' ', '').replace('-', '')
    if norm.startswith(PREFIX_PROPOSTA):
        sufixo = norm[len(PREFIX_PROPOSTA) :]
        if sufixo.isdigit():
            return int(sufixo)
    return None


def extrair_sequencial_pedido_venda(numero: str) -> int | None:
    """Compatibilidade com legado PV{n} / PV-000088 e novo PV-AAAAMMDD-NNNN."""
    par = extrair_sequencial_diario(numero, PREFIX_PEDIDO_VENDA)
    if par is not None:
        return par[1]
    raw = (numero or '').strip()
    if not raw:
        return None
    m = _RE_LEGADO_HIFEN.match(raw)
    if m and m.group(1).upper() == PREFIX_PEDIDO_VENDA:
        return int(m.group(2))
    norm = raw.upper().replace(' ', '').replace('-', '')
    if norm.startswith(PREFIX_PEDIDO_VENDA):
        sufixo = norm[len(PREFIX_PEDIDO_VENDA) :]
        if sufixo.isdigit() and not sufixo.startswith(PREFIX_PROPOSTA):
            return int(sufixo)
    return None


def _alocar_comercial(tipo: str, prefix: str, data) -> str:
    from apps.comercial.models import SequenciaComercial

    date_key = coerce_data_referencia(data)
    return alocar_numero_diario(
        modelo_sequencia=SequenciaComercial,
        filtros={'tipo': tipo, 'data_referencia': date_key},
        prefix=prefix,
        data=date_key,
    )


def gerar_numero_proposta(data=None) -> str:
    return _alocar_comercial(TIPO_PROPOSTA, PREFIX_PROPOSTA, data or date.today())


def gerar_numero_pedido_venda(data=None) -> str:
    return _alocar_comercial(TIPO_PEDIDO_VENDA, PREFIX_PEDIDO_VENDA, data or date.today())


def gerar_numero_faturamento(data=None) -> str:
    return _alocar_comercial(TIPO_FATURAMENTO, PREFIX_FATURAMENTO, data or date.today())


def numero_proposta_vazio(numero: str | None) -> bool:
    return not (numero or '').strip()


def numero_pedido_venda_vazio(numero: str | None) -> bool:
    return not (numero or '').strip()
