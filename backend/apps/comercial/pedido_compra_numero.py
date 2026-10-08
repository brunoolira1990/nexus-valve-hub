"""Numeração automática de Pedido de Compra: PC-AAAAMMDD-NNNN (sequência por dia)."""

from __future__ import annotations

from datetime import date

from apps.comercial.sequencia_diaria_numero import (
    alocar_numero_diario,
    coerce_data_referencia,
    formatar_numero_diario,
)


def formatar_numero_pedido_compra(data: date, sequencial: int) -> str:
    return formatar_numero_diario('PC', data, sequencial)


def alocar_numero_pedido_compra(data) -> str:
    """
    Reserva o próximo número do dia (data do pedido) com lock pessimista.
    Não reutiliza sequência de pedidos excluídos (contador só incrementa).
    """
    from apps.comercial.models import SequenciaPedidoCompra

    date_key = coerce_data_referencia(data)
    return alocar_numero_diario(
        modelo_sequencia=SequenciaPedidoCompra,
        filtros={'data_referencia': date_key},
        prefix='PC',
        data=date_key,
    )
