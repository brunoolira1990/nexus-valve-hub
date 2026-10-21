"""Últimos preços praticados do produto — NF-e, conferência de NF-e e, na falta delas, pedido de compra."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import OuterRef, QuerySet, Subquery
from django.db.models.functions import Coalesce

from apps.comercial.models import ItemPedidoCompra
from apps.fiscal.models import (
    ItemNFeEntrada,
    ItemNFeEntradaConferencia,
    ItemNFeSaida,
    NFeEntrada,
)

# Só documento que representa operação realizada conta como preço praticado:
# rascunho, pronta, rejeitada, erro de transmissão, inutilizada e cancelada ficam de fora.
STATUS_ENTRADA_PRECO_PRATICADO = (
    NFeEntrada.StatusOperacional.EM_CONFERENCIA,
    NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
    NFeEntrada.StatusOperacional.IMPORTADA_PENDENTE_CONFERENCIA,
)

# NFeSaida.status é CharField livre: a venda autorizada chega como AUTORIZADA_PRODUCAO (ciclo
# SEFAZ) ou AUTORIZADA_INTERNA (ciclo interno), e o cancelamento substitui o valor — nunca coexistem.
FILTRO_SAIDA_PRECO_PRATICADO = 'AUTORIZAD'

# PedidoCompra.status também é CharField livre e não tem enum no repo (o fluxo de baixa só escreve
# 'Recebido'/'Parcialmente recebido'). Só o pedido cancelado deixa de ser intenção de compra, então
# é o único excluído — por substring, para pegar CANCELADO e CANCELADA em qualquer caixa.
STATUS_PEDIDO_COMPRA_DESCARTADO = 'CANCEL'

# Hierarquia das fontes do último preço de compra, da mais confiável para a menos. Vale para a
# anotação da lista e para o card 'Última compra' do painel: recência desempata dentro de uma fonte,
# nunca troca uma fonte mais nova no lugar de uma mais antiga porém realizada.
ORDEM_FONTES_PRECO_COMPRA = ('nfe_entrada', 'nfe_entrada_conferencia', 'pedido_compra')


def _itens_compra(produto_ref) -> QuerySet:
    return (
        ItemNFeEntrada.objects
        .filter(produto_id=produto_ref, nf__status_operacional__in=STATUS_ENTRADA_PRECO_PRATICADO)
        .order_by('-nf__data', '-id')
        .values('valor')
    )


def _itens_venda(produto_ref) -> QuerySet:
    return (
        ItemNFeSaida.objects
        .filter(produto_id=produto_ref, nf__status__icontains=FILTRO_SAIDA_PRECO_PRATICADO)
        .order_by('-nf__data', '-id')
        .values('valor')
    )


def _itens_conferencia(produto_ref) -> QuerySet:
    return (
        ItemNFeEntradaConferencia.objects
        .filter(produto_id=produto_ref)
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .order_by('-conferencia__nf_entrada_historica__dh_emissao', '-id')
        .values('valor_unitario_nf')
    )


def _itens_pedido_compra(produto_ref) -> QuerySet:
    return (
        ItemPedidoCompra.objects
        .filter(produto_id=produto_ref)
        .exclude(pedido__status__icontains=STATUS_PEDIDO_COMPRA_DESCARTADO)
        .order_by('-pedido__data', '-id')
        .values('valor_unitario')
    )


def subquery_ultimo_preco_compra() -> Coalesce:
    """Caminho de prioridade: NF-e realizada > conferência de NF-e importada > pedido de compra."""
    return Coalesce(
        Subquery(_itens_compra(OuterRef('pk'))[:1]),
        Subquery(_itens_conferencia(OuterRef('pk'))[:1]),
        Subquery(_itens_pedido_compra(OuterRef('pk'))[:1]),
    )


def subquery_ultimo_preco_venda() -> Subquery:
    return Subquery(_itens_venda(OuterRef('pk'))[:1])


def annotate_ultimos_precos(queryset):
    return queryset.annotate(
        ultimo_preco_compra=subquery_ultimo_preco_compra(),
        ultimo_preco_venda=subquery_ultimo_preco_venda(),
    )


def ultimo_preco_compra_produto(produto_id: int) -> Decimal | None:
    for queryset, campo in (
        (_itens_compra(produto_id), 'valor'),
        (_itens_conferencia(produto_id), 'valor_unitario_nf'),
        (_itens_pedido_compra(produto_id), 'valor_unitario'),
    ):
        linha = queryset.first()
        if linha:
            return linha[campo]
    return None


def ultimo_preco_venda_produto(produto_id: int) -> Decimal | None:
    linha = _itens_venda(produto_id).first()
    return linha['valor'] if linha else None
