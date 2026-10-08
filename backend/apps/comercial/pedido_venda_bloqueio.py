"""Comercial 3.4 — bloqueio de itens do pedido após faturamento."""

from __future__ import annotations

from decimal import Decimal

from rest_framework.exceptions import ValidationError

from apps.comercial.faturamento_pedido_venda import STATUS_PEDIDO_FATURADO
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda

MSG_PEDIDO_FATURADO_ITENS = 'Pedido faturado não permite alteração de itens.'
MSG_ITEM_FATURADO_EXCLUIR = 'Item já faturado não pode ser excluído.'
MSG_ITEM_COM_FATURAMENTO_VINCULADO_EXCLUIR = (
    'Item com faturamento vinculado não pode ser excluído. Estorne ou cancele o faturamento primeiro.'
)
MSG_QTD_MENOR_FATURADA = 'Quantidade do item não pode ser menor que a quantidade já faturada.'
MSG_ITEM_FATURADO_CAMPOS = 'Item faturado não permite alteração de produto, preço ou desconto.'
MSG_PEDIDO_FATURADO_ADICIONAR = 'Pedido faturado não permite adicionar itens.'


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _status_pedido(pedido: PedidoVenda) -> str:
    return (pedido.status or '').strip().upper()


def pedido_itens_bloqueados(pedido: PedidoVenda) -> bool:
    return _status_pedido(pedido) in STATUS_PEDIDO_FATURADO


def _item_faturado(item: ItemPedidoVenda) -> bool:
    return _dec(item.quantidade_faturada) > 0


def _item_tem_vinculo_faturamento_bloqueante(item: ItemPedidoVenda) -> bool:
    """Vínculo em faturamento cancelado não bloqueia edição — só histórico inativo."""
    return item.itens_faturamento.exclude(
        faturamento__status=FaturamentoPedidoVenda.Status.CANCELADO,
    ).exists()


def _liberar_vinculos_faturamento_cancelados(item: ItemPedidoVenda) -> None:
    """Remove linhas de faturamento cancelado para permitir exclusão do item (PROTECT)."""
    item.itens_faturamento.filter(
        faturamento__status=FaturamentoPedidoVenda.Status.CANCELADO,
    ).delete()


def _campos_item_alterados(existing: ItemPedidoVenda, row: dict) -> list[str]:
    alterados: list[str] = []
    produto_id = row.get('produto')
    if produto_id is not None and hasattr(produto_id, 'pk'):
        produto_id = produto_id.pk
    if produto_id is None:
        produto_id = row.get('produto_id')
    if produto_id is not None and int(produto_id) != existing.produto_id:
        alterados.append('produto')

    for campo_model, keys in (
        ('valor_unitario', ('valor_unitario',)),
        ('preco_por_unidade_negociada', ('preco_por_unidade_negociada',)),
        ('desconto', ('desconto',)),
    ):
        for key in keys:
            if key not in row:
                continue
            novo = _dec(row[key])
            if novo != _dec(getattr(existing, campo_model)):
                alterados.append(campo_model)
            break

    qtd_keys = ('quantidade_negociada', 'quantidade')
    for key in qtd_keys:
        if key not in row:
            continue
        novo = _dec(row[key])
        antigo = _dec(existing.quantidade_negociada or existing.quantidade)
        if novo != antigo:
            alterados.append('quantidade')
        break
    return alterados


def validar_atualizacao_itens_pedido_venda(pedido: PedidoVenda, itens_data: list[dict] | None) -> None:
    """Valida payload de itens antes de persistir; levanta ValidationError com mensagens claras."""
    if itens_data is None:
        return

    st = _status_pedido(pedido)
    if st in STATUS_PEDIDO_FATURADO:
        raise ValidationError({'itens': MSG_PEDIDO_FATURADO_ITENS})

    existentes = {it.id: it for it in pedido.itens.select_related('produto').all()}
    incoming_ids: set[int] = set()

    for row in itens_data:
        raw_id = row.get('id')
        if raw_id in (None, ''):
            continue
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        incoming_ids.add(item_id)
        existing = existentes.get(item_id)
        if existing is None:
            continue

        alterados = _campos_item_alterados(existing, row)
        if not alterados:
            continue

        if existing.status_item == ItemPedidoVenda.StatusItem.FATURADO:
            raise ValidationError({'itens': MSG_ITEM_FATURADO_CAMPOS})

        if _item_faturado(existing):
            bloqueados = {'produto', 'valor_unitario', 'preco_por_unidade_negociada', 'desconto'}
            if bloqueados.intersection(alterados):
                raise ValidationError({'itens': MSG_ITEM_FATURADO_CAMPOS})

        if 'quantidade' in alterados:
            qtd_nova = _dec(row.get('quantidade_negociada') or row.get('quantidade'))
            if qtd_nova < _dec(existing.quantidade_faturada):
                raise ValidationError({'itens': MSG_QTD_MENOR_FATURADA})

    for item_id, existing in existentes.items():
        if item_id in incoming_ids:
            continue
        if _item_tem_vinculo_faturamento_bloqueante(existing):
            raise ValidationError({'itens': MSG_ITEM_COM_FATURAMENTO_VINCULADO_EXCLUIR})
        if _item_faturado(existing):
            raise ValidationError({'itens': MSG_ITEM_FATURADO_EXCLUIR})

    if st in STATUS_PEDIDO_FATURADO:
        novos = sum(1 for row in itens_data if not row.get('id'))
        if novos:
            raise ValidationError({'itens': MSG_PEDIDO_FATURADO_ADICIONAR})


def sincronizar_itens_pedido_venda(pedido: PedidoVenda, itens_data: list[dict]) -> None:
    """Atualiza itens preservando quantidade_faturada e status_item."""
    validar_atualizacao_itens_pedido_venda(pedido, itens_data)
    existentes = {it.id: it for it in pedido.itens.all()}
    vistos: set[int] = set()

    for row in itens_data:
        item_id = row.get('id')
        dados = {k: v for k, v in row.items() if k != 'id'}
        if item_id not in (None, ''):
            try:
                pk = int(item_id)
            except (TypeError, ValueError):
                pk = None
        else:
            pk = None

        if pk and pk in existentes:
            obj = existentes[pk]
            for attr, value in dados.items():
                setattr(obj, attr, value)
            obj.save()
            vistos.add(pk)
        else:
            ItemPedidoVenda.objects.create(pedido=pedido, **dados)

    for pk, obj in existentes.items():
        if pk not in vistos:
            if _item_tem_vinculo_faturamento_bloqueante(obj):
                raise ValidationError({'itens': MSG_ITEM_COM_FATURAMENTO_VINCULADO_EXCLUIR})
            _liberar_vinculos_faturamento_cancelados(obj)
            obj.delete()
