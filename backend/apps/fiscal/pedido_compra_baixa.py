"""Baixa de Pedido de Compra vinculado à conferência NF-e Entrada (finalização)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.conferencia_pedido import _quantidade_proxima
from apps.fiscal.models import ItemNFeEntradaConferencia, NFeEntradaConferencia

MSG_JA_BAIXADO = 'Pedido de compra já foi baixado para esta NF-e Entrada.'
MSG_SEM_PEDIDO = 'Nenhum pedido de compra vinculado à conferência.'
MSG_SEM_VINCULO = 'Nenhum item da NF-e vinculado a itens do pedido de compra.'
MSG_QTD_EXCEDE_SALDO = (
    'Quantidade a baixar excede o saldo pendente do item {item_id} do pedido de compra.'
)

STATUS_PEDIDO_RECEBIDO = 'Recebido'
STATUS_PEDIDO_PARCIAL = 'Parcialmente recebido'


class ResultadoBaixaPedidoCompraDict(TypedDict):
    aplicado: bool
    ja_baixado: bool
    conferencia_id: int
    pedido_compra_id: int | None
    pedido_compra_numero: str
    pedido_compra_status: str
    itens_baixados: list[dict[str, Any]]
    mensagem: str


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def quantidade_baixar_linha_conferencia(linha: ItemNFeEntradaConferencia) -> Decimal:
    q = _dec(linha.quantidade_nf)
    if q > 0:
        return q
    return _dec(linha.quantidade_estoque_calculada)


def _quantidade_pedido_item(item_pc: ItemPedidoCompra) -> Decimal:
    q = _dec(item_pc.quantidade_negociada)
    if q > 0:
        return q
    return _dec(item_pc.quantidade)


def _atualizar_status_pedido_compra(pedido: PedidoCompra) -> str:
    itens = list(pedido.itens.all())
    if not itens:
        return pedido.status or ''

    algum_recebido = False
    todos_completos = True
    for item_pc in itens:
        q_pedido = _quantidade_pedido_item(item_pc)
        q_rec = _dec(item_pc.quantidade_recebida)
        if q_rec > 0:
            algum_recebido = True
        if q_pedido <= 0:
            continue
        if not _quantidade_proxima(q_rec, q_pedido):
            todos_completos = False

    if not algum_recebido:
        return pedido.status or ''

    novo_status = STATUS_PEDIDO_RECEBIDO if todos_completos else STATUS_PEDIDO_PARCIAL
    if (pedido.status or '') != novo_status:
        pedido.status = novo_status
        pedido.save(update_fields=['status'])
    return pedido.status or ''


@transaction.atomic
def aplicar_baixa_pedido_compra_conferencia(
    conferencia: NFeEntradaConferencia,
    *,
    usuario=None,
) -> ResultadoBaixaPedidoCompraDict:
    conferencia = (
        NFeEntradaConferencia.objects.select_for_update(of=('self',))
        .select_related('pedido_compra')
        .get(pk=conferencia.pk)
    )

    pedido = conferencia.pedido_compra
    resultado: ResultadoBaixaPedidoCompraDict = {
        'aplicado': False,
        'ja_baixado': False,
        'conferencia_id': conferencia.id,
        'pedido_compra_id': conferencia.pedido_compra_id,
        'pedido_compra_numero': pedido.numero if pedido else '',
        'pedido_compra_status': pedido.status if pedido else '',
        'itens_baixados': [],
        'mensagem': '',
    }

    if conferencia.pedido_baixa_aplicado_em:
        resultado['ja_baixado'] = True
        resultado['mensagem'] = MSG_JA_BAIXADO
        if pedido:
            resultado['pedido_compra_status'] = pedido.status or ''
        return resultado

    if not conferencia.pedido_compra_id or not pedido:
        resultado['mensagem'] = MSG_SEM_PEDIDO
        return resultado

    linhas = list(
        conferencia.itens.select_related('item_pedido_compra')
        .filter(item_pedido_compra_id__isnull=False)
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO),
    )
    if not linhas:
        raise ValueError(MSG_SEM_VINCULO)

    for linha in linhas:
        item_pc = linha.item_pedido_compra
        if not item_pc or item_pc.pedido_id != pedido.id:
            raise ValueError(MSG_SEM_VINCULO)
        q_baixar = quantidade_baixar_linha_conferencia(linha)
        if q_baixar <= 0:
            continue
        q_pedido = _quantidade_pedido_item(item_pc)
        q_ja = _dec(item_pc.quantidade_recebida)
        saldo = q_pedido - q_ja
        if q_baixar > saldo and not _quantidade_proxima(q_baixar, saldo):
            raise ValueError(MSG_QTD_EXCEDE_SALDO.format(item_id=item_pc.id))

    agora = timezone.now()
    itens_baixados: list[dict[str, Any]] = []

    for linha in linhas:
        item_pc = ItemPedidoCompra.objects.select_for_update(of=('self',)).get(pk=linha.item_pedido_compra_id)
        q_baixar = quantidade_baixar_linha_conferencia(linha)
        if q_baixar <= 0:
            continue

        item_pc.quantidade_recebida = _dec(item_pc.quantidade_recebida) + q_baixar
        item_pc.save(update_fields=['quantidade_recebida'])

        linha_locked = ItemNFeEntradaConferencia.objects.select_for_update(of=('self',)).get(pk=linha.pk)
        if linha_locked.pedido_baixa_aplicada_em:
            raise ValueError(MSG_JA_BAIXADO)
        linha_locked.quantidade_pedido_baixada = q_baixar
        linha_locked.pedido_baixa_aplicada_em = agora
        linha_locked.save(
            update_fields=['quantidade_pedido_baixada', 'pedido_baixa_aplicada_em', 'atualizado_em'],
        )

        itens_baixados.append(
            {
                'item_conferencia_id': linha_locked.id,
                'item_pedido_compra_id': item_pc.id,
                'quantidade_baixada': str(q_baixar),
                'quantidade_recebida_total': str(item_pc.quantidade_recebida),
            },
        )

    if not itens_baixados:
        raise ValueError(MSG_SEM_VINCULO)

    pedido = PedidoCompra.objects.select_for_update(of=('self',)).get(pk=pedido.pk)
    status_atualizado = _atualizar_status_pedido_compra(pedido)

    conferencia.pedido_baixa_aplicado_em = agora
    if usuario and getattr(usuario, 'is_authenticated', False):
        conferencia.pedido_baixa_aplicado_por = usuario
    conferencia.save(
        update_fields=['pedido_baixa_aplicado_em', 'pedido_baixa_aplicado_por', 'atualizado_em'],
    )

    resultado['aplicado'] = True
    resultado['itens_baixados'] = itens_baixados
    resultado['pedido_compra_status'] = status_atualizado
    resultado['mensagem'] = 'Pedido de compra baixado com sucesso.'
    return resultado
