"""Numeração automática de Pedido de Compra: PC-AAAAMMDD-NNNN (sequência por dia, baseada na data do pedido)."""

from __future__ import annotations

from datetime import date, datetime

from django.db import IntegrityError, transaction


def _coerce_data(data) -> date:
    if isinstance(data, date) and not isinstance(data, datetime):
        return data
    if isinstance(data, datetime):
        return data.date()
    if isinstance(data, str):
        return datetime.strptime(data[:10], '%Y-%m-%d').date()
    raise TypeError(f'data inválida para numeração: {type(data)!r}')


def formatar_numero_pedido_compra(data: date, sequencial: int) -> str:
    return f"PC-{data.strftime('%Y%m%d')}-{sequencial:04d}"


@transaction.atomic
def alocar_numero_pedido_compra(data) -> str:
    """
    Reserva o próximo número do dia (data do pedido) com lock pessimista.
    Não reutiliza sequência de pedidos excluídos (contador só incrementa).
    """
    from apps.comercial.models import SequenciaPedidoCompra

    date_key = _coerce_data(data)
    seq = SequenciaPedidoCompra.objects.select_for_update().filter(data_referencia=date_key).first()
    if seq is None:
        try:
            SequenciaPedidoCompra.objects.create(data_referencia=date_key, proximo_numero=1)
        except IntegrityError:
            pass
        seq = SequenciaPedidoCompra.objects.select_for_update().get(data_referencia=date_key)
    n = seq.proximo_numero
    seq.proximo_numero = n + 1
    seq.save(update_fields=['proximo_numero'])
    return formatar_numero_pedido_compra(date_key, n)
