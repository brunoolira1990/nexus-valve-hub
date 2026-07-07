"""Primitivas de baixa/consumo de estoque físico rastreável por peça (EstoqueBarra).

Fase preparatória para a venda por peça/barra: estas funções são o núcleo testável
de consumo e reversão sobre EstoqueBarra, independente do fluxo de NF saída (que será
plugado numa fase futura, junto com o seletor de peça).

Regras:
- Baixa integral (quantidade == saldo): status vira CONSUMIDA, saldo zera.
- Baixa parcial (quantidade < saldo): status vira PARCIAL, saldo é reduzido.
- Não permite baixar mais que o saldo disponível.
- Só consome peças DISPONIVEL ou PARCIAL.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.fiscal.models import EstoqueBarra

TOLERANCIA = Decimal('0.001')


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    return Decimal(str(v))


def _sincronizar_espelho_m(barra: EstoqueBarra) -> None:
    if barra.unidade_base == 'M':
        barra.saldo_m = barra.saldo


def _status_apos_saldo(barra: EstoqueBarra) -> str:
    saldo = _dec(barra.saldo)
    if saldo <= TOLERANCIA:
        return EstoqueBarra.Status.CONSUMIDA
    if saldo < _dec(barra.quantidade_original) - TOLERANCIA:
        return EstoqueBarra.Status.PARCIAL
    return EstoqueBarra.Status.DISPONIVEL


@transaction.atomic
def baixar_peca_estoque(
    estoque_barra_id: int,
    quantidade: Decimal | str | float,
) -> EstoqueBarra:
    """
    Baixa `quantidade` (na unidade base da peça) do saldo de uma EstoqueBarra.

    Levanta ValueError se a peça não pode ser consumida ou se a quantidade é inválida
    ou maior que o saldo disponível.
    """
    qtd = _dec(quantidade)
    if qtd <= 0:
        raise ValueError('Quantidade de baixa deve ser maior que zero.')

    barra = EstoqueBarra.objects.select_for_update().get(id=estoque_barra_id)

    if barra.status not in (EstoqueBarra.Status.DISPONIVEL, EstoqueBarra.Status.PARCIAL):
        raise ValueError(
            f'Peça {barra.codigo_interno_barra} não está disponível para baixa (status {barra.status}).',
        )

    saldo = _dec(barra.saldo)
    if qtd > saldo + TOLERANCIA:
        raise ValueError(
            f'Baixa de {qtd:.3f} {barra.unidade_base} excede o saldo disponível '
            f'({saldo:.3f} {barra.unidade_base}) da peça {barra.codigo_interno_barra}.',
        )

    novo_saldo = saldo - qtd
    if novo_saldo < TOLERANCIA:
        novo_saldo = Decimal('0')
    barra.saldo = novo_saldo
    _sincronizar_espelho_m(barra)
    barra.status = _status_apos_saldo(barra)
    barra.save(update_fields=['saldo', 'saldo_m', 'status', 'atualizado_em'])
    return barra


@transaction.atomic
def reverter_baixa_peca_estoque(
    estoque_barra_id: int,
    quantidade: Decimal | str | float,
) -> EstoqueBarra:
    """
    Estorna `quantidade` de volta ao saldo de uma EstoqueBarra (ex.: cancelamento de venda).

    Não permite ultrapassar a quantidade original da peça.
    """
    qtd = _dec(quantidade)
    if qtd <= 0:
        raise ValueError('Quantidade de estorno deve ser maior que zero.')

    barra = EstoqueBarra.objects.select_for_update().get(id=estoque_barra_id)

    if barra.status == EstoqueBarra.Status.CANCELADA:
        raise ValueError(
            f'Peça {barra.codigo_interno_barra} está cancelada; não é possível estornar.',
        )

    novo_saldo = _dec(barra.saldo) + qtd
    original = _dec(barra.quantidade_original)
    if novo_saldo > original + TOLERANCIA:
        raise ValueError(
            f'Estorno de {qtd:.3f} {barra.unidade_base} ultrapassa a quantidade original '
            f'({original:.3f} {barra.unidade_base}) da peça {barra.codigo_interno_barra}.',
        )
    if novo_saldo > original:
        novo_saldo = original

    barra.saldo = novo_saldo
    _sincronizar_espelho_m(barra)
    barra.status = _status_apos_saldo(barra)
    barra.save(update_fields=['saldo', 'saldo_m', 'status', 'atualizado_em'])
    return barra
