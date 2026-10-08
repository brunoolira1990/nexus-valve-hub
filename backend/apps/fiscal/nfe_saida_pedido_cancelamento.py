"""Efeitos comerciais no pedido após cancelamento SEFAZ — sem alterar status/XML/evento fiscal da NF-e."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.comercial.faturamento_pedido_venda import (
    _round_qty,
    recalcular_status_item,
    recalcular_status_pedido,
)
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_bloqueio import nf_cancelada_operacional
from apps.fiscal.nfe_saida_ciclo_vida import _liberar_faturamento_para_nova_nfe
from apps.fiscal.nfe_saida_efeitos import (
    _dec,
    _itens_nf_para_estorno,
    _lock_faturamento,
    _lock_nfe_saida,
    _lock_pedido,
    _registrar_evento,
)


def nf_cancelada_sefaz(nf: NFeSaida) -> bool:
    """NF-e com cancelamento fiscal SEFAZ registrado (status operacional cancelado)."""
    st = (nf.status or '').strip().upper()
    if st in ('CANCELADA_PRODUCAO', 'CANCELADA_HOMOLOGACAO'):
        return True
    if not nf_cancelada_operacional(nf):
        return False
    return bool((nf.protocolo_autorizacao or '').strip() or (nf.xml_autorizado or '').strip())


def _estornar_quantidades_pedido_da_nfe(nf: NFeSaida) -> tuple[list[dict[str, Any]], set[int]]:
    itens_nf = _itens_nf_para_estorno(nf)
    if not itens_nf:
        raise ValueError('NF-e sem itens para estorno de faturamento no pedido.')

    estorno_resumo: list[dict[str, Any]] = []
    pedido_ids: set[int] = set()

    for linha_nf in itens_nf:
        qtd = _round_qty(_dec(linha_nf.quantidade))
        if qtd <= 0:
            continue
        item_fat = linha_nf.item_faturamento_pedido
        if not item_fat or not item_fat.item_pedido_id:
            raise ValueError(
                f'Item da NF-e #{linha_nf.pk} sem vínculo com item de faturamento/pedido; estorno abortado.',
            )
        item_pedido = ItemPedidoVenda.objects.select_for_update().get(pk=item_fat.item_pedido_id)
        if item_pedido.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            raise ValueError(f'Item do pedido {item_pedido.pk} está cancelado.')

        qtd_antes = _dec(item_pedido.quantidade_faturada)
        nova_qtd = max(Decimal('0'), _round_qty(qtd_antes - qtd))
        item_pedido.quantidade_faturada = nova_qtd
        item_pedido.save(update_fields=['quantidade_faturada'])
        recalcular_status_item(item_pedido)
        pedido_ids.add(item_pedido.pedido_id)
        estorno_resumo.append(
            {
                'item_pedido_id': item_pedido.pk,
                'quantidade_estornada': str(qtd),
                'quantidade_faturada_antes': str(qtd_antes),
                'quantidade_faturada_depois': str(nova_qtd),
            },
        )

    if not estorno_resumo:
        raise ValueError('Nenhuma quantidade foi estornada nos itens do pedido.')

    return estorno_resumo, pedido_ids


def faturamento_teve_estorno_por_cancelamento_nfe(faturamento: FaturamentoPedidoVenda) -> bool:
    """Faturamento cujo saldo comercial já foi liberado após cancelamento SEFAZ de NF-e vinculada."""
    return NFeSaida.objects.filter(
        faturamento_pedido_venda_id=faturamento.pk,
        efeitos_cancelamento_aplicados_em__isnull=False,
    ).exists()


def nf_cancelada_vinculada_faturamento(faturamento: FaturamentoPedidoVenda) -> NFeSaida | None:
    """NF-e cancelada SEFAZ ainda vinculada ao faturamento (histórico)."""
    for nf in NFeSaida.objects.filter(faturamento_pedido_venda_id=faturamento.pk).order_by('-pk'):
        if nf_cancelada_sefaz(nf):
            return nf
    return None


@transaction.atomic
def aplicar_efeitos_comerciais_pos_cancelamento_sefaz(
    nfe_saida: NFeSaida | int,
    *,
    usuario=None,
    motivo: str = '',
) -> dict[str, Any]:
    """
    Após cancelamento SEFAZ: estorna quantidades faturadas, libera faturamento para nova NF-e.
    Não altera status fiscal, XML autorizado nem evento de cancelamento da NF-e.
    """
    nf_id = nfe_saida.pk if isinstance(nfe_saida, NFeSaida) else int(nfe_saida)
    nf = _lock_nfe_saida(nf_id)

    if nf.efeitos_cancelamento_aplicados_em:
        return {
            'aplicado': False,
            'nfe_saida_id': nf.pk,
            'pedido_id': nf.pedido_venda_id,
            'faturamento_id': nf.faturamento_pedido_venda_id,
            'mensagens': ['Efeitos comerciais de cancelamento já aplicados.'],
        }

    if not nf_cancelada_sefaz(nf):
        raise ValueError('NF-e não está cancelada na SEFAZ para liberar saldo comercial do pedido.')

    if not nf.faturamento_pedido_venda_id:
        agora = timezone.now()
        nf.efeitos_cancelamento_aplicados_em = agora
        if usuario and getattr(usuario, 'is_authenticated', False):
            nf.efeitos_cancelamento_por = usuario
        nf.save(update_fields=['efeitos_cancelamento_aplicados_em', 'efeitos_cancelamento_por'])
        return {
            'aplicado': True,
            'nfe_saida_id': nf.pk,
            'pedido_id': nf.pedido_venda_id,
            'faturamento_id': None,
            'mensagens': ['NF-e cancelada sem faturamento vinculado — efeitos comerciais registrados.'],
        }

    fat = _lock_faturamento(nf.faturamento_pedido_venda_id)
    status_antes = nf.status or ''
    estorno_resumo, pedido_ids = _estornar_quantidades_pedido_da_nfe(nf)

    agora = timezone.now()
    nf.efeitos_cancelamento_aplicados_em = agora
    if usuario and getattr(usuario, 'is_authenticated', False):
        nf.efeitos_cancelamento_por = usuario
    nf.save(update_fields=['efeitos_cancelamento_aplicados_em', 'efeitos_cancelamento_por'])

    if fat.nfe_saida_id == nf.pk:
        _liberar_faturamento_para_nova_nfe(fat)

    for pid in sorted(pedido_ids):
        pedido = _lock_pedido(pid)
        recalcular_status_pedido(pedido)

    msg = motivo.strip() or 'Saldo comercial liberado após cancelamento SEFAZ.'
    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.ESTORNO_FATURAMENTO,
        status_anterior=status_antes,
        status_novo=status_antes,
        resumo={'itens_estornados': estorno_resumo, 'origem': 'cancelamento_sefaz'},
        observacao=msg,
        usuario=usuario,
    )
    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.CANCELAMENTO_EFEITOS_APLICADOS,
        status_anterior=status_antes,
        status_novo=status_antes,
        resumo={'origem': 'cancelamento_sefaz', 'faturamento_liberado': fat.pk},
        observacao=msg,
        usuario=usuario,
    )

    return {
        'aplicado': True,
        'nfe_saida_id': nf.pk,
        'status': nf.status,
        'pedido_id': nf.pedido_venda_id,
        'faturamento_id': fat.pk,
        'mensagens': [
            'Cancelamento SEFAZ: saldo comercial do pedido liberado para nova NF-e.',
            'Faturamento disponível para gerar nova NF-e (a nota cancelada permanece no histórico).',
        ],
    }


def sincronizar_efeitos_comerciais_pedido(pedido: PedidoVenda) -> None:
    """Reparo idempotente: aplica efeitos comerciais em NF-e canceladas SEFAZ ainda pendentes."""
    nfs = (
        NFeSaida.objects.filter(pedido_venda_id=pedido.pk, efeitos_cancelamento_aplicados_em__isnull=True)
        .order_by('pk')
    )
    for nf in nfs:
        if not nf_cancelada_sefaz(nf):
            continue
        try:
            aplicar_efeitos_comerciais_pos_cancelamento_sefaz(nf)
        except ValueError:
            continue
