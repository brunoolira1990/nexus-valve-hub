"""Exclusão de pedido de venda com reversão de itens da proposta vinculada."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.comercial.models import FaturamentoPedidoVenda, ItemProposta, PedidoVenda, Proposta, PropostaComercialHistorico
from apps.comercial.pedido_venda_bloqueio import pedido_itens_bloqueados
from apps.comercial.proposta_comercial_historico import registrar_evento_comercial
from apps.comercial.proposta_comercial_status import (
    calcular_status_proposta_apos_exclusao_pedido,
    reverter_item_proposta_apos_exclusao_pedido,
)

if TYPE_CHECKING:
    pass

MSG_PEDIDO_FATURADO = (
    'Pedido faturado não pode ser excluído. Estorne ou cancele o faturamento antes de excluir.'
)
MSG_PEDIDO_FATURAMENTO = (
    'Pedido com faturamento vinculado não pode ser excluído. Cancele o faturamento primeiro.'
)
MSG_PEDIDO_NFE = 'Pedido com NF-e vinculada não pode ser excluído.'
MSG_PEDIDO_EXPEDICAO = 'Pedido com expedição vinculada não pode ser excluído.'
MSG_PEDIDO_ALOCACAO = (
    'Pedido com alocação de atendimento operacional não pode ser excluído.'
)


def validar_exclusao_pedido_venda(pedido: PedidoVenda) -> None:
    """Bloqueia exclusão quando o pedido já possui efeitos posteriores."""
    if pedido_itens_bloqueados(pedido):
        raise ValidationError({'detail': MSG_PEDIDO_FATURADO})

    if pedido.itens.filter(quantidade_faturada__gt=0).exists():
        raise ValidationError({'detail': MSG_PEDIDO_FATURADO})

    if pedido.faturamentos.exclude(status=FaturamentoPedidoVenda.Status.CANCELADO).exists():
        raise ValidationError({'detail': MSG_PEDIDO_FATURAMENTO})

    from apps.fiscal.models import AlocacaoAtendimento, NFeSaida

    if NFeSaida.objects.filter(pedido_venda_id=pedido.pk).exists():
        raise ValidationError({'detail': MSG_PEDIDO_NFE})

    if pedido.faturamentos.filter(nfe_saida_id__isnull=False).exists():
        raise ValidationError({'detail': MSG_PEDIDO_NFE})

    if pedido.expedicoes.exists():
        raise ValidationError({'detail': MSG_PEDIDO_EXPEDICAO})

    item_ids = list(pedido.itens.values_list('pk', flat=True))
    if item_ids and AlocacaoAtendimento.objects.filter(pedido_venda_item_id__in=item_ids).exists():
        raise ValidationError({'detail': MSG_PEDIDO_ALOCACAO})


def _itens_proposta_a_reverter(pedido: PedidoVenda) -> list[ItemProposta]:
    ids: set[int] = set()
    ids.update(
        ItemProposta.objects.filter(pedido_venda_gerado_id=pedido.pk).values_list('pk', flat=True),
    )
    ids.update(
        ItemProposta.objects.filter(item_pedido_venda_gerado__pedido_id=pedido.pk).values_list('pk', flat=True),
    )
    ids.update(
        pedido.itens.filter(item_proposta_id__isnull=False).values_list('item_proposta_id', flat=True),
    )
    if not ids:
        return []
    return list(ItemProposta.objects.filter(pk__in=ids).select_for_update())


@transaction.atomic
def excluir_pedido_venda(pedido: PedidoVenda, *, usuario=None) -> None:
    """Exclui pedido sem efeitos posteriores e reverte itens da proposta vinculados."""
    validar_exclusao_pedido_venda(pedido)

    proposta_id = pedido.proposta_id
    pedido_id = pedido.pk
    pedido_numero = pedido.numero

    itens_proposta = _itens_proposta_a_reverter(pedido)
    itens_revertidos_meta: list[dict[str, Any]] = [
        {'item_proposta_id': it.pk} for it in itens_proposta
    ]

    pedido.delete()

    for item in itens_proposta:
        item.refresh_from_db()
        reverter_item_proposta_apos_exclusao_pedido(item, usuario=usuario)

    if not proposta_id:
        return

    proposta = Proposta.objects.select_for_update().get(pk=proposta_id)
    proposta.status = calcular_status_proposta_apos_exclusao_pedido(proposta)
    proposta.save(update_fields=['status'])

    if itens_revertidos_meta:
        registrar_evento_comercial(
            proposta,
            PropostaComercialHistorico.TipoEvento.PEDIDO_EXCLUIDO_STATUS_REVERTIDO,
            descricao=(
                f'Pedido de venda {pedido_numero} excluído; '
                'itens vinculados retornaram para pendente.'
            ),
            usuario=usuario,
            dados_json={
                'pedido_id': pedido_id,
                'numero_pedido': pedido_numero,
                'itens_revertidos': itens_revertidos_meta,
            },
        )
