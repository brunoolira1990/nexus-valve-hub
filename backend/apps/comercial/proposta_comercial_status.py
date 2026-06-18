"""Status comercial de proposta/itens e histórico sem migration dedicada."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.utils import timezone

from apps.comercial.commercial_defaults import (
    STATUS_ITEM_CANCELADO,
    STATUS_ITEM_CONVERTIDO,
    STATUS_ITEM_MANTIDO,
    STATUS_ITEM_PENDENTE,
    STATUS_ITEM_PERDIDO,
    STATUS_PROPOSTA_CONVERTIDA,
    STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA,
    STATUS_PROPOSTA_REABERTA,
)

if TYPE_CHECKING:
    from apps.comercial.models import ItemProposta, Proposta

HISTORICO_MARKER = '[HISTORICO COMERCIAL]'

STATUS_PROPOSTA_BLOQUEIO_GERAR_PEDIDO = frozenset(
    {
        'rejeitada',
        'rejeitado',
        'cancelada',
        'cancelado',
        'perdida',
        'perdido',
    },
)

STATUS_ITEM_BLOQUEIO_CONVERSAO = frozenset(
    {
        STATUS_ITEM_CANCELADO,
        STATUS_ITEM_PERDIDO,
        STATUS_ITEM_CONVERTIDO,
    },
)


def _norm_status(val: str | None) -> str:
    return (val or '').strip().upper()


def _comercial_snapshot(item: ItemProposta) -> dict[str, Any]:
    raw = item.snapshot_produto if isinstance(item.snapshot_produto, dict) else {}
    com = raw.get('comercial')
    return dict(com) if isinstance(com, dict) else {}


def _merge_comercial_snapshot(item: ItemProposta, patch: dict[str, Any]) -> dict[str, Any]:
    raw = dict(item.snapshot_produto) if isinstance(item.snapshot_produto, dict) else {}
    com = _comercial_snapshot(item)
    com.update(patch)
    raw['comercial'] = com
    return raw


def item_ja_convertido_em_pedido(item: ItemProposta) -> bool:
    from apps.comercial.models import ItemPedidoVenda

    if ItemPedidoVenda.objects.filter(item_proposta_id=item.pk).exists():
        return True
    return _comercial_snapshot(item).get('status_comercial') == STATUS_ITEM_CONVERTIDO


def status_item_proposta(item: ItemProposta) -> str:
    if item_ja_convertido_em_pedido(item):
        return STATUS_ITEM_CONVERTIDO
    st = _comercial_snapshot(item).get('status_comercial')
    if st in (
        STATUS_ITEM_PENDENTE,
        STATUS_ITEM_MANTIDO,
        STATUS_ITEM_CANCELADO,
        STATUS_ITEM_PERDIDO,
    ):
        return st
    return STATUS_ITEM_PENDENTE


def item_pode_converter(item: ItemProposta) -> bool:
    return status_item_proposta(item) in (STATUS_ITEM_PENDENTE, STATUS_ITEM_MANTIDO)


def marcar_item_convertido(item: ItemProposta, *, pedido_id: int, pedido_numero: str) -> None:
    item.snapshot_produto = _merge_comercial_snapshot(
        item,
        {
            'status_comercial': STATUS_ITEM_CONVERTIDO,
            'convertido_em': timezone.now().isoformat(),
            'pedido_venda_id': pedido_id,
            'pedido_venda_numero': pedido_numero,
        },
    )
    item.save(update_fields=['snapshot_produto'])


def marcar_item_cancelado_ou_perdido(item: ItemProposta, *, status: str) -> None:
    if status not in (STATUS_ITEM_CANCELADO, STATUS_ITEM_PERDIDO):
        raise ValueError('Status inválido para cancelamento de item.')
    item.snapshot_produto = _merge_comercial_snapshot(
        item,
        {
            'status_comercial': status,
            'cancelado_em': timezone.now().isoformat(),
        },
    )
    item.save(update_fields=['snapshot_produto'])


def marcar_item_mantido_pendente(item: ItemProposta) -> None:
    item.snapshot_produto = _merge_comercial_snapshot(
        item,
        {'status_comercial': STATUS_ITEM_MANTIDO},
    )
    item.save(update_fields=['snapshot_produto'])


def pedido_vinculado_item(item: ItemProposta) -> tuple[int | None, str]:
    from apps.comercial.models import ItemPedidoVenda

    link = (
        ItemPedidoVenda.objects.filter(item_proposta_id=item.pk)
        .select_related('pedido')
        .order_by('id')
        .first()
    )
    if link and link.pedido_id:
        return link.pedido_id, link.pedido.numero
    com = _comercial_snapshot(item)
    pid = com.get('pedido_venda_id')
    pnum = com.get('pedido_venda_numero') or ''
    return (int(pid) if pid else None), str(pnum)


def proposta_requer_recuperacao(proposta: Proposta) -> bool:
    st = _norm_status(proposta.status)
    if st in (STATUS_PROPOSTA_REABERTA, STATUS_PROPOSTA_CONVERTIDA, STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA):
        return False
    if st in ('APROVADA', 'APROVADO', 'ACEITA', 'ACEITO', 'PENDENTE', 'ENVIADA', 'ABERTA', 'EM_NEGOCIACAO'):
        return False
    return st in STATUS_PROPOSTA_BLOQUEIO_GERAR_PEDIDO or st in ('REJEITADA', 'REJEITADO')


def proposta_totalmente_convertida(proposta: Proposta) -> bool:
    itens = list(proposta.itens.all())
    if not itens:
        return False
    ativos = [it for it in itens if status_item_proposta(it) not in (STATUS_ITEM_CANCELADO, STATUS_ITEM_PERDIDO)]
    if not ativos:
        return False
    return all(status_item_proposta(it) == STATUS_ITEM_CONVERTIDO for it in ativos)


def itens_pendentes_conversao(proposta: Proposta) -> list:
    return [it for it in proposta.itens.all() if item_pode_converter(it)]


def calcular_status_proposta_apos_conversao(proposta: Proposta) -> str:
    if proposta_totalmente_convertida(proposta):
        return STATUS_PROPOSTA_CONVERTIDA
    if proposta.pedidos_gerados.exists() or any(
        status_item_proposta(it) == STATUS_ITEM_CONVERTIDO for it in proposta.itens.all()
    ):
        return STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA
    st = (proposta.status or '').strip()
    if _norm_status(st) == STATUS_PROPOSTA_REABERTA:
        return STATUS_PROPOSTA_REABERTA
    return st or STATUS_PROPOSTA_REABERTA


def append_historico_comercial(proposta: Proposta, linha: str, *, usuario=None) -> None:
    user_txt = ''
    if usuario is not None and getattr(usuario, 'is_authenticated', False):
        user_txt = getattr(usuario, 'get_full_name', lambda: '')() or getattr(usuario, 'username', '') or ''
    ts = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
    prefix = f'{HISTORICO_MARKER} {ts}'
    if user_txt:
        prefix += f' ({user_txt})'
    entry = f'{prefix} — {linha.strip()}'
    base = (proposta.observacoes_proposta or '').rstrip()
    proposta.observacoes_proposta = f'{base}\n{entry}'.strip() if base else entry
