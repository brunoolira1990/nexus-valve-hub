"""Comercial 2.2 — defaults de data, status e condição comercial."""

from __future__ import annotations

from datetime import date, timedelta

VALIDADE_DIAS_PADRAO = 15
STATUS_PROPOSTA_INICIAL = 'PENDENTE'
STATUS_PROPOSTA_CONVERTIDA = 'CONVERTIDA'
STATUS_PEDIDO_VENDA_INICIAL = 'ABERTO'

_LABELS_STATUS_PROPOSTA = {
    STATUS_PROPOSTA_INICIAL: 'Pendente',
    'Aprovada': 'Aprovada',
    'Aprovado': 'Aprovada',
    'Rejeitada': 'Rejeitada',
    STATUS_PROPOSTA_CONVERTIDA: 'Convertida',
    'Pendente': 'Pendente',
}


def label_status_proposta(status: str | None) -> str:
    s = (status or '').strip()
    if not s:
        return '—'
    return _LABELS_STATUS_PROPOSTA.get(s, _LABELS_STATUS_PROPOSTA.get(s.upper(), s))
CONDICAO_PAGAMENTO_PADRAO = '30'


def hoje() -> date:
    return date.today()


def validade_padrao(data_base: date | None = None) -> date:
    base = data_base or hoje()
    return base + timedelta(days=VALIDADE_DIAS_PADRAO)


def _texto_vazio(val) -> bool:
    return val is None or (isinstance(val, str) and not val.strip())


def aplicar_defaults_proposta(attrs: dict, *, instance=None) -> dict:
    if instance is not None:
        return attrs
    if attrs.get('data') is None:
        attrs['data'] = hoje()
    if attrs.get('validade') is None:
        attrs['validade'] = validade_padrao(attrs['data'])
    if _texto_vazio(attrs.get('status')):
        attrs['status'] = STATUS_PROPOSTA_INICIAL
    if _texto_vazio(attrs.get('condicao_pagamento_texto')):
        attrs['condicao_pagamento_texto'] = CONDICAO_PAGAMENTO_PADRAO
    if 'usar_cenario_fiscal_saida' not in attrs:
        attrs['usar_cenario_fiscal_saida'] = True
    return attrs


def aplicar_defaults_pedido_venda(attrs: dict, *, instance=None) -> dict:
    if instance is not None:
        return attrs
    if attrs.get('data') is None:
        attrs['data'] = hoje()
    if _texto_vazio(attrs.get('status')):
        attrs['status'] = STATUS_PEDIDO_VENDA_INICIAL
    if _texto_vazio(attrs.get('condicao_pagamento_texto')):
        attrs['condicao_pagamento_texto'] = CONDICAO_PAGAMENTO_PADRAO
    return attrs
