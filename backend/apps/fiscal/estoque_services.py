from decimal import Decimal

from apps.corridas.models import Corrida
from apps.fiscal.models import EstoqueCorrida, ItemNFeEntrada, ItemNFeSaida, NFeEntrada, NFeSaida


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _validar_produto_corrida(produto_id: int, corrida: Corrida) -> None:
    if corrida.produto_id != produto_id:
        raise ValueError('O produto do item deve ser o mesmo da corrida selecionada.')


def aplicar_entrada_item(item: ItemNFeEntrada) -> None:
    if not item.corrida_id:
        return
    _validar_produto_corrida(item.produto_id, item.corrida)
    ec, _ = EstoqueCorrida.objects.select_for_update().get_or_create(
        produto_id=item.produto_id,
        corrida_id=item.corrida_id,
        defaults={'saldo': Decimal('0')},
    )
    ec.saldo = _dec(ec.saldo) + _dec(item.quantidade)
    ec.save(update_fields=['saldo'])


def reverter_entrada_item(item: ItemNFeEntrada) -> None:
    if not item.corrida_id:
        return
    ec = EstoqueCorrida.objects.select_for_update().filter(
        produto_id=item.produto_id,
        corrida_id=item.corrida_id,
    ).first()
    if not ec:
        return
    ec.saldo = _dec(ec.saldo) - _dec(item.quantidade)
    ec.save(update_fields=['saldo'])


def aplicar_saida_item(item: ItemNFeSaida) -> None:
    if not item.corrida_id:
        raise ValueError('NF de saída exige corrida em cada item para baixa de estoque.')
    _validar_produto_corrida(item.produto_id, item.corrida)
    ec, _ = EstoqueCorrida.objects.select_for_update().get_or_create(
        produto_id=item.produto_id,
        corrida_id=item.corrida_id,
        defaults={'saldo': Decimal('0')},
    )
    q = _dec(item.quantidade)
    if _dec(ec.saldo) < q:
        raise ValueError(
            f'Saldo insuficiente para corrida {item.corrida.numero} / produto {item.produto_id}.'
        )
    ec.saldo = _dec(ec.saldo) - q
    ec.save(update_fields=['saldo'])


def reverter_saida_item(item: ItemNFeSaida) -> None:
    if not item.corrida_id:
        return
    ec = EstoqueCorrida.objects.select_for_update().filter(
        produto_id=item.produto_id,
        corrida_id=item.corrida_id,
    ).first()
    if not ec:
        return
    ec.saldo = _dec(ec.saldo) + _dec(item.quantidade)
    ec.save(update_fields=['saldo'])


def reverter_todos_itens_entrada(nf: NFeEntrada) -> None:
    for it in nf.itens.select_related('corrida', 'produto').all():
        reverter_entrada_item(it)


def aplicar_todos_itens_entrada(nf: NFeEntrada) -> None:
    for it in nf.itens.select_related('corrida', 'produto').all():
        aplicar_entrada_item(it)


def reverter_todos_itens_saida(nf: NFeSaida) -> None:
    for it in nf.itens.select_related('corrida', 'produto').all():
        reverter_saida_item(it)


def aplicar_todos_itens_saida(nf: NFeSaida) -> None:
    for it in nf.itens.select_related('corrida', 'produto').all():
        aplicar_saida_item(it)
