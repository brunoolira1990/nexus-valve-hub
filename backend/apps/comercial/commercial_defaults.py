"""Comercial 2.2 — defaults de data, status e condição comercial."""

from __future__ import annotations

from datetime import date, timedelta

VALIDADE_DIAS_PADRAO = 15
STATUS_PROPOSTA_INICIAL = 'PENDENTE'
STATUS_PROPOSTA_CONVERTIDA = 'CONVERTIDA'
STATUS_PEDIDO_VENDA_INICIAL = 'ABERTO'
MENSAGEM_COMERCIAL_PADRAO = 'A regra é não perder pedidos. Estamos abertos à negociação.'

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


def calcular_validade_por_dias(data_base: date, dias: int) -> date:
    return data_base + timedelta(days=max(1, int(dias)))


def inferir_validade_dias(data_base: date | None, validade: date | None) -> int | None:
    if not data_base or not validade:
        return None
    delta = (validade - data_base).days
    return max(0, delta)


def ultima_mensagem_comercial_vendedor(*, vendedor_ref=None, usuario=None) -> str:
    from apps.comercial.models import Proposta

    qs = Proposta.objects.exclude(mensagem_comercial='').order_by('-id', '-data')
    if vendedor_ref is not None:
        msg = qs.filter(vendedor_ref=vendedor_ref).values_list('mensagem_comercial', flat=True).first()
        if msg:
            return msg
    if usuario is not None and getattr(usuario, 'is_authenticated', False):
        msg = (
            qs.filter(vendedor_ref__usuario_id=usuario.pk)
            .values_list('mensagem_comercial', flat=True)
            .first()
        )
        if msg:
            return msg
    return MENSAGEM_COMERCIAL_PADRAO


def sincronizar_validade_proposta(attrs: dict, *, instance=None) -> None:
    data_base = attrs.get('data')
    if data_base is None and instance is not None:
        data_base = instance.data

    if 'validade_dias' in attrs and attrs.get('validade_dias') is not None and data_base is not None:
        dias = int(attrs['validade_dias'])
        if dias > 0:
            attrs['validade'] = calcular_validade_por_dias(data_base, dias)
        return

    validade = attrs.get('validade')
    if validade is None and instance is not None:
        validade = instance.validade
    if data_base and validade and attrs.get('validade_dias') is None:
        inferido = inferir_validade_dias(data_base, validade)
        if inferido is not None:
            attrs['validade_dias'] = inferido


def _texto_vazio(val) -> bool:
    return val is None or (isinstance(val, str) and not val.strip())


def aplicar_defaults_proposta(attrs: dict, *, instance=None, request=None) -> dict:
    if instance is not None:
        return attrs
    if attrs.get('data') is None:
        attrs['data'] = hoje()
    if attrs.get('validade_dias') is None:
        attrs['validade_dias'] = VALIDADE_DIAS_PADRAO
    sincronizar_validade_proposta(attrs, instance=instance)
    if attrs.get('validade') is None:
        attrs['validade'] = validade_padrao(attrs['data'])
    if _texto_vazio(attrs.get('status')):
        attrs['status'] = STATUS_PROPOSTA_INICIAL
    if _texto_vazio(attrs.get('condicao_pagamento_texto')):
        attrs['condicao_pagamento_texto'] = CONDICAO_PAGAMENTO_PADRAO
    if _texto_vazio(attrs.get('mensagem_comercial')):
        attrs['mensagem_comercial'] = ultima_mensagem_comercial_vendedor(
            vendedor_ref=attrs.get('vendedor_ref'),
            usuario=getattr(request, 'user', None) if request is not None else None,
        )
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
