"""NF-e Saída 1 — gerar rascunho a partir de FaturamentoPedidoVenda PRONTO_PARA_NFE."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.comercial.faturamento_pedido_venda import STATUS_PEDIDO_CANCELADO
from apps.comercial.models import FaturamentoPedidoVenda, PedidoVenda
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.serializers import NFeSaidaSerializer, recalcular_valor_nf_saida
from apps.fiscal.snapshot_fiscal_helpers import normalize_snapshot_fiscal_for_nfe
from apps.produtos.snapshot import build_produto_snapshot

STATUS_NFE_RASCUNHO = 'RASCUNHO'
MSG_NFE_CRIADA = 'NF-e Saída rascunho criada. A transmissão para SEFAZ será tratada em etapa posterior.'
MSG_NFE_JA_EXISTE = 'Este faturamento já possui NF-e Saída rascunho gerada.'


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _numero_rascunho_faturamento(faturamento_id: int) -> str:
    return f'RASCUNHO-FAT-{faturamento_id}'


class GerarNFeSaidaFaturamentoDict(TypedDict):
    nfe_saida_id: int
    numero: str
    status: str
    pedido_id: int
    faturamento_id: int
    itens_criados: int
    mensagens: list[str]
    ja_existia: bool
    nfe_saida: dict[str, Any] | None


def _resposta_gerar(
    nf: NFeSaida,
    *,
    pedido_id: int,
    faturamento_id: int,
    itens_criados: int,
    mensagens: list[str],
    ja_existia: bool,
) -> GerarNFeSaidaFaturamentoDict:
    ser = NFeSaidaSerializer(nf)
    return {
        'nfe_saida_id': nf.pk,
        'numero': nf.numero,
        'status': nf.status,
        'pedido_id': pedido_id,
        'faturamento_id': faturamento_id,
        'itens_criados': itens_criados,
        'mensagens': mensagens,
        'ja_existia': ja_existia,
        'nfe_saida': ser.data,
    }


@transaction.atomic
def gerar_nfe_saida_from_faturamento(
    pedido: PedidoVenda,
    faturamento_id: int,
    *,
    observacao: str = '',
) -> GerarNFeSaidaFaturamentoDict:
    fat = (
        FaturamentoPedidoVenda.objects.select_related('pedido', 'pedido__cliente', 'nfe_saida')
        .prefetch_related('itens__produto', 'itens__item_pedido')
        .get(pk=faturamento_id, pedido_id=pedido.pk)
    )

    if fat.nfe_saida_id:
        nf = NFeSaida.objects.prefetch_related('itens__produto').get(pk=fat.nfe_saida_id)
        return _resposta_gerar(
            nf,
            pedido_id=pedido.pk,
            faturamento_id=fat.pk,
            itens_criados=nf.itens.count(),
            mensagens=[MSG_NFE_JA_EXISTE],
            ja_existia=True,
        )

    if fat.status == FaturamentoPedidoVenda.Status.CANCELADO:
        raise ValueError('Faturamento cancelado não pode gerar NF-e Saída.')
    if fat.status == FaturamentoPedidoVenda.Status.RASCUNHO:
        raise ValueError('Confirme o faturamento antes de gerar NF-e Saída.')
    if fat.status == FaturamentoPedidoVenda.Status.GERADO_NFE:
        raise ValueError('Faturamento já marcado como NF-e gerada, mas sem vínculo de NF-e.')
    if fat.status != FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE:
        raise ValueError('Somente faturamentos prontos para NF-e podem gerar NF-e Saída.')

    pedido = fat.pedido
    st_pedido = (pedido.status or '').strip().upper()
    if st_pedido in STATUS_PEDIDO_CANCELADO:
        raise ValueError('Pedido cancelado não pode gerar NF-e Saída.')

    linhas = list(fat.itens.select_related('produto', 'item_pedido').all())
    if not linhas:
        raise ValueError('Faturamento sem itens para gerar NF-e Saída.')

    for linha in linhas:
        if linha.quantidade <= 0:
            raise ValueError('Itens do faturamento precisam ter quantidade maior que zero.')

    obs_parts = []
    if fat.observacao:
        obs_parts.append(fat.observacao.strip())
    if observacao:
        obs_parts.append(observacao.strip())
    if pedido.observacoes_comerciais:
        obs_parts.append(pedido.observacoes_comerciais.strip())

    if not pedido.cliente_id:
        raise ValueError('Pedido de venda sem cliente cadastrado; não é possível gerar NF-e Saída.')

    nf = NFeSaida.objects.create(
        numero=_numero_rascunho_faturamento(fat.pk),
        cliente_id=pedido.cliente_id,
        data=date.today(),
        status=STATUS_NFE_RASCUNHO,
        valor_total=Decimal('0'),
        modo_atendimento_estoque=NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
        pedido_venda=pedido,
        faturamento_pedido_venda=fat,
        observacao_origem='\n'.join(obs_parts),
        condicao_pagamento_texto=pedido.condicao_pagamento_texto or '',
        dias_parcelas=list(pedido.dias_parcelas or []),
        quantidade_parcelas=pedido.quantidade_parcelas or 0,
        vencimentos_finais=list(pedido.vencimentos_previstos or []),
        titulos_receber=[],
    )

    criados = 0
    for linha in linhas:
        produto = linha.produto
        if linha.item_pedido_id and linha.item_pedido.produto_id != produto.pk:
            raise ValueError(
                f'Item de faturamento #{linha.pk} com produto inconsistente em relação ao pedido.',
            )
        snap_fiscal_origem = linha.snapshot_fiscal
        if (not snap_fiscal_origem) and linha.item_pedido_id and linha.item_pedido.snapshot_fiscal:
            snap_fiscal_origem = linha.item_pedido.snapshot_fiscal
        snapshot_comercial = {
            'item_faturamento_id': linha.pk,
            'item_pedido_id': linha.item_pedido_id,
            'valor_unitario': str(linha.valor_unitario),
            'desconto': str(linha.desconto),
            'valor_total': str(linha.valor_total),
            'unidade_negociada': (
                linha.item_pedido.unidade_negociada if linha.item_pedido_id else ''
            ),
        }
        ItemNFeSaida.objects.create(
            nf=nf,
            item_faturamento_pedido=linha,
            produto=produto,
            quantidade=linha.quantidade,
            valor=linha.valor_unitario,
            corrida=linha.item_pedido.corrida if linha.item_pedido_id else None,
            snapshot_produto=build_produto_snapshot(produto),
            snapshot_fiscal=normalize_snapshot_fiscal_for_nfe(snap_fiscal_origem),
            snapshot_comercial=snapshot_comercial,
        )
        criados += 1

    recalcular_valor_nf_saida(nf)

    agora = timezone.now()
    fat.status = FaturamentoPedidoVenda.Status.GERADO_NFE
    fat.nfe_saida = nf
    fat.nfe_saida_gerada_em = agora
    fat.save(update_fields=['status', 'nfe_saida', 'nfe_saida_gerada_em', 'atualizado_em'])

    return _resposta_gerar(
        nf,
        pedido_id=pedido.pk,
        faturamento_id=fat.pk,
        itens_criados=criados,
        mensagens=[MSG_NFE_CRIADA],
        ja_existia=False,
    )
