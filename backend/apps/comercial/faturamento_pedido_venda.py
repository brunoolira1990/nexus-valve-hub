"""Pedido Venda 3 — faturamento parcial (solicitação, sem NF-e/estoque/financeiro)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.db.models import Sum

from apps.comercial.models import (
    FaturamentoPedidoVenda,
    ItemFaturamentoPedidoVenda,
    ItemPedidoVenda,
    PedidoVenda,
)
from apps.fiscal.models import NFeSaida

STATUS_PEDIDO_FATURADO = frozenset({'faturado', 'FATURADO'})
STATUS_PEDIDO_CANCELADO = frozenset({'cancelado', 'cancelada', 'CANCELADO'})
STATUS_PEDIDO_BLOQUEIO_FAT = STATUS_PEDIDO_FATURADO | STATUS_PEDIDO_CANCELADO

MSG_FATURAMENTO_CRIADO = (
    'Solicitação de faturamento criada. A emissão da NF-e será tratada em etapa posterior.'
)


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _round_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'))


def _round_qty(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.001'))


def quantidade_pedida_item(item: ItemPedidoVenda) -> Decimal:
    return _round_qty(_dec(item.quantidade_negociada or item.quantidade))


def quantidade_pendente_item(item: ItemPedidoVenda) -> Decimal:
    return max(Decimal('0'), quantidade_pedida_item(item) - _dec(item.quantidade_faturada))


def preco_unitario_item(item: ItemPedidoVenda) -> Decimal:
    return _dec(item.preco_por_unidade_negociada or item.valor_unitario)


def _status_pedido_normalizado(pedido: PedidoVenda) -> str:
    return (pedido.status or '').strip()


def pedido_permite_faturamento(pedido: PedidoVenda) -> tuple[bool, str]:
    st = _status_pedido_normalizado(pedido).upper()
    if st in STATUS_PEDIDO_CANCELADO:
        return False, 'Pedido cancelado não pode gerar faturamento.'
    if st in STATUS_PEDIDO_FATURADO:
        return False, 'Pedido já está totalmente faturado.'
    itens_ativos = pedido.itens.exclude(status_item=ItemPedidoVenda.StatusItem.CANCELADO)
    if not itens_ativos.exists():
        return False, 'Pedido sem itens ativos para faturar.'
    if all(quantidade_pendente_item(it) <= 0 for it in itens_ativos):
        return False, 'Pedido já está totalmente faturado (todos os itens).'
    return True, ''


def quantidade_reservada_rascunho(
    pedido: PedidoVenda,
    item_pedido_id: int,
    *,
    exclude_faturamento_id: int | None = None,
) -> Decimal:
    qs = ItemFaturamentoPedidoVenda.objects.filter(
        faturamento__pedido_id=pedido.pk,
        faturamento__status=FaturamentoPedidoVenda.Status.RASCUNHO,
        item_pedido_id=item_pedido_id,
    )
    if exclude_faturamento_id:
        qs = qs.exclude(faturamento_id=exclude_faturamento_id)
    total = qs.aggregate(s=Sum('quantidade'))['s']
    return _round_qty(_dec(total))


def quantidade_disponivel_faturar(item: ItemPedidoVenda) -> Decimal:
    pendente = quantidade_pendente_item(item)
    reservado = quantidade_reservada_rascunho(item.pedido, item.pk)
    return max(Decimal('0'), pendente - reservado)


def _desconto_proporcional(item: ItemPedidoVenda, quantidade: Decimal) -> Decimal:
    pedida = quantidade_pedida_item(item)
    if pedida <= 0:
        return Decimal('0')
    return _round_money(_dec(item.desconto) * (quantidade / pedida))


def _valor_item_faturamento(item: ItemPedidoVenda, quantidade: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    preco = preco_unitario_item(item)
    desconto = _desconto_proporcional(item, quantidade)
    valor = _round_money(quantidade * preco - desconto)
    return preco, desconto, valor


def _snapshot_cliente(pedido: PedidoVenda) -> dict[str, Any]:
    cli = pedido.cliente
    return {
        'cliente_id': cli.pk,
        'razao_social': cli.razao_social,
        'nome_fantasia': getattr(cli, 'nome_fantasia', '') or '',
        'cnpj': getattr(cli, 'cnpj', '') or '',
        'uf': getattr(cli, 'uf', '') or '',
    }


def recalcular_status_item(item: ItemPedidoVenda) -> None:
    if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
        return
    pendente = quantidade_pendente_item(item)
    faturada = _dec(item.quantidade_faturada)
    if faturada <= 0:
        item.status_item = ItemPedidoVenda.StatusItem.PENDENTE
    elif pendente <= 0:
        item.status_item = ItemPedidoVenda.StatusItem.FATURADO
    else:
        item.status_item = ItemPedidoVenda.StatusItem.PARCIAL
    item.save(update_fields=['status_item'])


def recalcular_status_pedido(pedido: PedidoVenda) -> None:
    st_atual = _status_pedido_normalizado(pedido).upper()
    if st_atual in STATUS_PEDIDO_CANCELADO:
        return

    itens = list(pedido.itens.exclude(status_item=ItemPedidoVenda.StatusItem.CANCELADO))
    if not itens:
        return

    todos_faturados = all(it.status_item == ItemPedidoVenda.StatusItem.FATURADO for it in itens)
    algum_faturado = any(
        it.status_item in (ItemPedidoVenda.StatusItem.FATURADO, ItemPedidoVenda.StatusItem.PARCIAL)
        for it in itens
    )
    tem_rascunho = pedido.faturamentos.filter(status=FaturamentoPedidoVenda.Status.RASCUNHO).exists()

    if todos_faturados:
        novo = 'FATURADO'
    elif algum_faturado:
        novo = 'PARCIALMENTE_FATURADO'
    elif tem_rascunho:
        novo = 'EM_FATURAMENTO'
    elif st_atual in ('PARCIALMENTE_FATURADO', 'FATURADO', 'EM_FATURAMENTO'):
        novo = 'ABERTO'
    else:
        novo = pedido.status or 'ABERTO'

    pedido.status = novo
    pedido.save(update_fields=['status'])


def _serializar_item_resumo(item: ItemPedidoVenda) -> dict[str, Any]:
    pedida = quantidade_pedida_item(item)
    faturada = _dec(item.quantidade_faturada)
    pendente = quantidade_pendente_item(item)
    disponivel = quantidade_disponivel_faturar(item)
    preco = preco_unitario_item(item)
    produto = item.produto
    return {
        'item_pedido_id': item.pk,
        'produto_codigo': (produto.codigo_completo if produto else '') or '',
        'descricao': (produto.descricao if produto else '') or '',
        'quantidade_pedida': str(pedida),
        'quantidade_faturada': str(_round_qty(faturada)),
        'quantidade_pendente': str(pendente),
        'quantidade_disponivel': str(disponivel),
        'status_item': item.status_item,
        'valor_unitario': str(_round_money(preco)),
        'valor_pendente': str(_round_money(pendente * preco)),
    }


def montar_resumo_faturamento(pedido: PedidoVenda) -> dict[str, Any]:
    pedido = (
        PedidoVenda.objects.select_related('cliente')
        .prefetch_related('itens__produto', 'faturamentos')
        .get(pk=pedido.pk)
    )
    itens = list(pedido.itens.select_related('produto').order_by('id'))
    valor_faturado = Decimal('0')
    valor_pendente = Decimal('0')
    itens_pendentes = itens_parciais = itens_faturados = 0

    itens_resumo = []
    for item in itens:
        if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            continue
        row = _serializar_item_resumo(item)
        itens_resumo.append(row)
        preco = preco_unitario_item(item)
        valor_faturado += _dec(item.quantidade_faturada) * preco
        valor_pendente += quantidade_pendente_item(item) * preco
        if item.status_item == ItemPedidoVenda.StatusItem.FATURADO:
            itens_faturados += 1
        elif item.status_item == ItemPedidoVenda.StatusItem.PARCIAL:
            itens_parciais += 1
        else:
            itens_pendentes += 1

    rascunhos = [
        {
            'faturamento_id': f.pk,
            'status': f.status,
            'observacao': f.observacao,
            'criado_em': f.criado_em.isoformat(),
            'itens_count': f.itens.count(),
        }
        for f in pedido.faturamentos.filter(status=FaturamentoPedidoVenda.Status.RASCUNHO).order_by('-id')
    ]

    faturamentos_nfe = []
    for f in (
        pedido.faturamentos.filter(
            status__in=(
                FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE,
                FaturamentoPedidoVenda.Status.GERADO_NFE,
            ),
        )
        .select_related('nfe_saida')
        .order_by('-id')
    ):
        faturamentos_nfe.append(
            {
                'faturamento_id': f.pk,
                'status': f.status,
                'observacao': f.observacao,
                'criado_em': f.criado_em.isoformat(),
                'itens_count': f.itens.count(),
                'nfe_saida_id': f.nfe_saida_id,
                'nfe_saida_numero': f.nfe_saida.numero if f.nfe_saida_id else '',
                'nfe_saida_status': f.nfe_saida.status if f.nfe_saida_id else '',
            },
        )

    pode, motivo = pedido_permite_faturamento(pedido)

    historico_nfe = [
        {
            'nfe_saida_id': nf.pk,
            'numero': nf.numero,
            'status': nf.status,
            'data': nf.data.isoformat() if nf.data else '',
            'faturamento_id': nf.faturamento_pedido_venda_id,
            'valor_total': str(_round_money(_dec(nf.valor_total))),
            'cancelada_em': nf.cancelada_em.isoformat() if nf.cancelada_em else None,
            'motivo_cancelamento': (nf.motivo_cancelamento or '').strip(),
            'efeitos_autorizacao_aplicados_em': (
                nf.efeitos_autorizacao_aplicados_em.isoformat() if nf.efeitos_autorizacao_aplicados_em else None
            ),
            'efeitos_cancelamento_aplicados_em': (
                nf.efeitos_cancelamento_aplicados_em.isoformat()
                if nf.efeitos_cancelamento_aplicados_em
                else None
            ),
        }
        for nf in NFeSaida.objects.filter(pedido_venda_id=pedido.pk).order_by('-id')
    ]

    return {
        'pedido_id': pedido.pk,
        'status': pedido.status,
        'pode_faturar': pode,
        'motivo_bloqueio': motivo,
        'total_itens': len(itens_resumo),
        'itens_pendentes': itens_pendentes,
        'itens_parciais': itens_parciais,
        'itens_faturados': itens_faturados,
        'valor_total_pedido': str(_round_money(_dec(pedido.valor_total))),
        'valor_faturado': str(_round_money(valor_faturado)),
        'valor_pendente': str(_round_money(valor_pendente)),
        'faturamentos_rascunho': rascunhos,
        'faturamentos_nfe': faturamentos_nfe,
        'historico_nfe_saida': historico_nfe,
        'itens': itens_resumo,
    }


class CriarFaturamentoPayload(TypedDict, total=False):
    observacao: str
    itens: list[dict[str, Any]]


@transaction.atomic
def criar_faturamento_pedido(
    pedido: PedidoVenda,
    payload: CriarFaturamentoPayload,
    *,
    usuario=None,
) -> dict[str, Any]:
    pedido = PedidoVenda.objects.select_related('cliente').prefetch_related('itens__produto').get(pk=pedido.pk)

    ok, msg = pedido_permite_faturamento(pedido)
    if not ok:
        raise ValueError(msg)

    itens_payload = payload.get('itens') or []
    if not itens_payload:
        raise ValueError('Informe ao menos um item com quantidade a faturar.')

    fat = FaturamentoPedidoVenda.objects.create(
        pedido=pedido,
        status=FaturamentoPedidoVenda.Status.RASCUNHO,
        cliente_snapshot=_snapshot_cliente(pedido),
        observacao=(payload.get('observacao') or '').strip(),
        criado_por=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
    )

    itens_map = {it.pk: it for it in pedido.itens.select_related('produto')}
    criados = 0

    for linha in itens_payload:
        item_id = linha.get('item_pedido_id')
        if item_id is None:
            raise ValueError('item_pedido_id é obrigatório em cada linha.')
        item = itens_map.get(int(item_id))
        if item is None:
            raise ValueError(f'Item do pedido {item_id} não encontrado neste pedido.')
        if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            raise ValueError(f'Item {item_id} está cancelado e não pode ser faturado.')

        qtd = _round_qty(_dec(linha.get('quantidade')))
        if qtd <= 0:
            raise ValueError('Quantidade a faturar deve ser maior que zero.')

        disponivel = quantidade_disponivel_faturar(item)
        if qtd > disponivel:
            raise ValueError(
                f'Quantidade {qtd} excede o saldo disponível ({disponivel}) do item {item_id}.',
            )

        preco, desconto, valor_total = _valor_item_faturamento(item, qtd)
        ItemFaturamentoPedidoVenda.objects.create(
            faturamento=fat,
            item_pedido=item,
            produto=item.produto,
            quantidade=qtd,
            valor_unitario=preco,
            desconto=desconto,
            valor_total=valor_total,
            snapshot_fiscal=item.snapshot_fiscal or {},
            observacao=(linha.get('observacao') or '').strip(),
        )
        criados += 1

    if criados == 0:
        fat.delete()
        raise ValueError('Nenhum item válido para faturamento.')

    recalcular_status_pedido(pedido)

    return {
        'faturamento_id': fat.pk,
        'pedido_id': pedido.pk,
        'status': fat.status,
        'itens_criados': criados,
        'mensagens': [MSG_FATURAMENTO_CRIADO],
    }


@transaction.atomic
def confirmar_faturamento_pedido(
    pedido: PedidoVenda,
    faturamento_id: int,
) -> dict[str, Any]:
    pedido = PedidoVenda.objects.prefetch_related('itens').get(pk=pedido.pk)
    try:
        fat = FaturamentoPedidoVenda.objects.select_related('pedido').prefetch_related(
            'itens__item_pedido',
        ).get(pk=faturamento_id, pedido_id=pedido.pk)
    except FaturamentoPedidoVenda.DoesNotExist as exc:
        raise ValueError('Faturamento não encontrado para este pedido.') from exc

    if fat.status != FaturamentoPedidoVenda.Status.RASCUNHO:
        raise ValueError('Somente faturamentos em rascunho podem ser confirmados.')

    ok, msg = pedido_permite_faturamento(pedido)
    if not ok and _status_pedido_normalizado(pedido).upper() not in STATUS_PEDIDO_FATURADO:
        raise ValueError(msg)

    for linha in fat.itens.select_related('item_pedido'):
        item = linha.item_pedido
        if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            raise ValueError(f'Item {item.pk} cancelado não pode ser confirmado.')

        disponivel = quantidade_pendente_item(item) - quantidade_reservada_rascunho(
            pedido,
            item.pk,
            exclude_faturamento_id=fat.pk,
        )
        if linha.quantidade > disponivel:
            raise ValueError(
                f'Saldo insuficiente no item {item.pk} para confirmar quantidade {linha.quantidade}.',
            )

        item.quantidade_faturada = _round_qty(_dec(item.quantidade_faturada) + linha.quantidade)
        item.save(update_fields=['quantidade_faturada'])
        recalcular_status_item(item)

    fat.status = FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE
    fat.save(update_fields=['status', 'atualizado_em'])

    recalcular_status_pedido(pedido)

    return {
        'faturamento_id': fat.pk,
        'pedido_id': pedido.pk,
        'status': fat.status,
        'pedido_status': pedido.status,
        'mensagens': [
            'Faturamento confirmado. Quantidades do pedido atualizadas. NF-e e estoque em etapa posterior.',
        ],
    }


@transaction.atomic
def cancelar_faturamento_pedido(
    pedido: PedidoVenda,
    faturamento_id: int,
) -> dict[str, Any]:
    try:
        fat = FaturamentoPedidoVenda.objects.get(pk=faturamento_id, pedido_id=pedido.pk)
    except FaturamentoPedidoVenda.DoesNotExist as exc:
        raise ValueError('Faturamento não encontrado para este pedido.') from exc

    if fat.status != FaturamentoPedidoVenda.Status.RASCUNHO:
        raise ValueError(
            'Faturamento confirmado não pode ser cancelado nesta fase. Estorno ficará para fase futura.',
        )

    fat.status = FaturamentoPedidoVenda.Status.CANCELADO
    fat.save(update_fields=['status', 'atualizado_em'])
    recalcular_status_pedido(pedido)

    return {
        'faturamento_id': fat.pk,
        'pedido_id': pedido.pk,
        'status': fat.status,
        'mensagens': ['Solicitação de faturamento cancelada. Quantidades faturadas do pedido não foram alteradas.'],
    }
