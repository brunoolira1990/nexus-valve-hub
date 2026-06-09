"""Mensagens amigáveis ao excluir registros com vínculos PROTECT."""

from __future__ import annotations

from django.db.models import ProtectedError

from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import NFeSaida


def _identificador_pedido(pedido: PedidoVenda | None) -> str | None:
    if not pedido:
        return None
    numero = (pedido.numero or '').strip()
    return f'pedido {numero}' if numero else f'pedido #{pedido.pk}'


def _referencias_de_objeto(obj: object) -> list[str]:
    refs: list[str] = []
    if isinstance(obj, ItemPedidoVenda):
        ref = _identificador_pedido(obj.pedido)
        if ref:
            refs.append(ref)
    elif isinstance(obj, PedidoVenda):
        ref = _identificador_pedido(obj)
        if ref:
            refs.append(ref)
    elif isinstance(obj, FaturamentoPedidoVenda):
        num = (obj.numero_faturamento or '').strip()
        if num:
            refs.append(f'faturamento {num}')
        ref = _identificador_pedido(obj.pedido)
        if ref:
            refs.append(ref)
    elif isinstance(obj, NFeSaida):
        num = (obj.numero or '').strip()
        if num:
            refs.append(f'NF-e {num}')
    elif hasattr(obj, 'pedido_venda'):
        pv = getattr(obj, 'pedido_venda', None)
        ref = _identificador_pedido(pv)
        if ref:
            refs.append(ref)
    elif hasattr(obj, 'pedido'):
        ref = _identificador_pedido(getattr(obj, 'pedido', None))
        if ref:
            refs.append(ref)
    elif hasattr(obj, 'numero') and isinstance(getattr(obj, 'numero', None), str):
        num = (obj.numero or '').strip()
        if num:
            refs.append(num)
    return refs


def format_protected_delete_message(exc: ProtectedError, *, entidade: str) -> str:
    """Monta mensagem em português a partir de ProtectedError."""
    vistos: list[str] = []
    for obj in exc.protected_objects:
        for ref in _referencias_de_objeto(obj):
            if ref not in vistos:
                vistos.append(ref)
    if not vistos:
        return f'Este {entidade} não pode ser excluído porque existem registros vinculados.'
    if len(vistos) == 1:
        return f'Este {entidade} não pode ser excluído porque está vinculado ao {vistos[0]}.'
    lista = ', '.join(vistos[:5])
    sufixo = '…' if len(vistos) > 5 else ''
    return f'Este {entidade} não pode ser excluído porque está vinculado a: {lista}{sufixo}.'
