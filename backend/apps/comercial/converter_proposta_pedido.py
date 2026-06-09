"""Propostas 2.1 — conversão de proposta em pedido de venda."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.comercial import pricing as price_rules
from apps.comercial.commercial_defaults import STATUS_PROPOSTA_CONVERTIDA
from apps.comercial.models import ItemPedidoVenda, ItemProposta, PedidoVenda, Proposta
from apps.comercial.vendedor_helpers import nome_vendedor_exibicao
from apps.comercial.serializers import ItemPropostaSerializer, PedidoVendaSerializer, recalcular_pedido_venda


STATUS_PEDIDO_INICIAL = 'ABERTO'
STATUS_PROPOSTA_APROVADA = frozenset({'aprovada', 'aprovado', 'aceita', 'aceito'})
STATUS_PROPOSTA_BLOQUEIO = frozenset({'rejeitada', 'rejeitado', 'cancelada', 'cancelado'})


MSG_PROPOSTA_JA_CONVERTIDA = 'Esta proposta já foi convertida em pedido de venda.'


class ConverterPropostaPedidoDict(TypedDict):
    pedido_id: int
    numero: str
    status: str
    proposta_id: int
    proposta_status: str
    itens_criados: int
    mensagens: list[str]
    ja_existia: bool
    pedido: dict[str, Any] | None


def _incoming_proposta(proposta: Proposta) -> dict[str, Any]:
    return {
        'usar_cenario_fiscal_saida': proposta.usar_cenario_fiscal_saida,
        'cenario_fiscal_saida_id': proposta.cenario_fiscal_saida_id,
        'empresa_emitente_id': proposta.empresa_emitente_id,
        'cliente_id': proposta.cliente_id,
        'uf_destino_avulso': proposta.uf_destino_avulso,
        'operacao_fiscal': proposta.operacao_fiscal,
    }


def _snapshot_fiscal_item(item: ItemProposta, proposta: Proposta) -> dict[str, Any]:
    ser = ItemPropostaSerializer(item, context={'proposta_incoming': _incoming_proposta(proposta)})
    data = ser.data
    produto = item.produto
    ncm = ''
    if produto is not None:
        ncm = (produto.get_ncm_efetivo_codigo() or produto.ncm or '').strip()
    else:
        ncm = (item.ncm_avulso or '').strip()
    return {
        'item_proposta_id': item.pk,
        'produto_id': item.produto_id,
        'produto_codigo': (produto.codigo_completo if produto else '') or '',
        'descricao': (produto.descricao if produto else item.descricao_avulsa) or '',
        'ncm': ncm,
        'unidade_negociada': item.unidade_negociada,
        'origem_regra_fiscal_saida': data.get('origem_regra_fiscal_saida'),
        'regra_fiscal_saida_id': data.get('regra_fiscal_saida_id'),
        'regra_fiscal_legada_id': data.get('regra_fiscal_legada_id'),
        'mensagem_regra_fiscal_saida': data.get('mensagem_regra_fiscal_saida'),
        'icms_saida_percentual': str(item.icms_saida_percentual),
        'pis_saida_percentual': str(item.pis_saida_percentual),
        'cofins_saida_percentual': str(item.cofins_saida_percentual),
        'ipi_saida_percentual': str(item.ipi_saida_percentual),
        'deduzir_icms_base_pis': data.get('deduzir_icms_base_pis'),
        'deduzir_icms_base_cofins': data.get('deduzir_icms_base_cofins'),
        'pis_cofins_base_deduz_icms': data.get('pis_cofins_base_deduz_icms'),
    }


def _snapshot_conversao_proposta(proposta: Proposta) -> dict[str, Any]:
    return {
        'proposta_id': proposta.pk,
        'proposta_numero': proposta.numero,
        'proposta_status': proposta.status,
        'homologacao_fiscal_status': proposta.homologacao_fiscal_status,
        'usar_cenario_fiscal_saida': bool(proposta.usar_cenario_fiscal_saida),
        'cenario_fiscal_saida_id': proposta.cenario_fiscal_saida_id,
        'origem_fiscal_resumo': (
            'Cenário fiscal de saída'
            if proposta.usar_cenario_fiscal_saida
            else 'Regra fiscal legada'
        ),
        'convertido_em': timezone.now().isoformat(),
        'valor_total_proposta': str(proposta.valor_total),
    }


def validar_proposta_para_conversao(proposta: Proposta) -> tuple[bool, list[str]]:
    mensagens: list[str] = []
    if proposta.pedidos_gerados.exists():
        return False, [MSG_PROPOSTA_JA_CONVERTIDA]
    st = (proposta.status or '').strip().lower()
    if st in STATUS_PROPOSTA_BLOQUEIO:
        return False, ['Proposta com status que não permite conversão em pedido de venda.']
    if st not in STATUS_PROPOSTA_APROVADA:
        mensagens.append(
            'A proposta não está com status comercial «Aprovada». '
            'A conversão segue permitida conforme a regra atual do sistema.',
        )
    if not proposta.cliente_id:
        return False, ['Vincule um cliente cadastrado para converter a proposta em pedido.']
    if proposta.itens.filter(produto__isnull=True).exists():
        return False, [
            'Vincule todos os itens avulsos a produtos cadastrados antes de converter. '
            'O pedido e o faturamento exigem produto no cadastro.',
        ]
    for item in proposta.itens.all():
        if item.produto_id:
            continue
        if not price_rules.ncm_fiscal_valido(item.ncm_avulso or ''):
            return False, [
                'Existem itens avulsos sem NCM válido (8 dígitos). '
                'Regularize antes de converter em pedido.',
            ]
    if not proposta.itens.exists():
        return False, ['A proposta não possui itens para converter.']
    return True, mensagens


def _montar_payload_pedido(proposta: Proposta, *, mensagens: list[str]) -> dict[str, Any]:
    itens_payload = []
    for item in proposta.itens.select_related('produto').all():
        qtd = item.quantidade_negociada or item.quantidade
        preco = item.preco_por_unidade_negociada or item.valor_unitario or item.preco_final
        itens_payload.append(
            {
                'produto_id': item.produto_id,
                'item_proposta_id': item.pk,
                'quantidade': item.quantidade,
                'valor_unitario': item.valor_unitario,
                'desconto': item.desconto,
                'unidade_negociada': item.unidade_negociada,
                'quantidade_negociada': qtd,
                'unidade_estoque_calculada': item.unidade_estoque_calculada,
                'quantidade_estoque_calculada': item.quantidade_estoque_calculada,
                'peso_total_kg': item.peso_total_kg,
                'metros_total': item.metros_total,
                'barras_total': item.barras_total,
                'preco_por_unidade_negociada': preco,
                'preco_por_kg': item.preco_por_kg,
                'preco_por_metro': item.preco_por_metro,
                'fator_conversao': item.fator_conversao,
                'corrida_id': None,
                'snapshot_produto': item.snapshot_produto or {},
                'snapshot_fiscal': _snapshot_fiscal_item(item, proposta),
            },
        )
    return {
        'empresa_emitente_id': proposta.empresa_emitente_id,
        'cliente_id': proposta.cliente_id,
        'data': proposta.data.isoformat(),
        'status': STATUS_PEDIDO_INICIAL,
        'condicao_pagamento_texto': proposta.condicao_pagamento_texto,
        'dias_parcelas': proposta.dias_parcelas,
        'quantidade_parcelas': proposta.quantidade_parcelas,
        'vencimentos_previstos': [d.isoformat() for d in proposta.vencimentos_previstos],
        'valor_total': proposta.valor_total,
        'proposta_id': proposta.id,
        'vendedor': nome_vendedor_exibicao(proposta),
        'vendedor_id': proposta.vendedor_ref_id,
        'prazo_entrega_texto': (proposta.prazo_entrega_texto or '').strip(),
        'prazo_entrega': None,
        'observacoes_comerciais': '',
        'observacoes_internas': proposta.homologacao_fiscal_observacao or '',
        'snapshot_conversao': _snapshot_conversao_proposta(proposta),
        'itens': itens_payload,
        '_mensagens': mensagens,
    }


def _resposta_converter(
    pedido: PedidoVenda,
    proposta: Proposta,
    *,
    mensagens: list[str],
    ja_existia: bool,
) -> ConverterPropostaPedidoDict:
    ser = PedidoVendaSerializer(pedido)
    return {
        'pedido_id': pedido.pk,
        'numero': pedido.numero,
        'status': pedido.status,
        'proposta_id': pedido.proposta_id or proposta.pk,
        'proposta_status': proposta.status,
        'itens_criados': pedido.itens.count(),
        'mensagens': mensagens,
        'ja_existia': ja_existia,
        'pedido': ser.data,
    }


def converter_proposta_em_pedido_venda(proposta: Proposta) -> ConverterPropostaPedidoDict:
    proposta = Proposta.objects.select_related(
        'cliente',
        'empresa_emitente',
        'cenario_fiscal_saida',
        'vendedor_ref',
    ).prefetch_related('itens__produto').get(pk=proposta.pk)

    existente = PedidoVenda.objects.filter(proposta_id=proposta.pk).order_by('id').first()
    if existente:
        Proposta.objects.filter(pk=proposta.pk).exclude(status=STATUS_PROPOSTA_CONVERTIDA).update(
            status=STATUS_PROPOSTA_CONVERTIDA,
        )
        proposta.refresh_from_db(fields=['status'])
        raise ValueError(MSG_PROPOSTA_JA_CONVERTIDA)

    ok, mensagens = validar_proposta_para_conversao(proposta)
    if not ok:
        raise ValueError(mensagens[0] if mensagens else 'Proposta não pode ser convertida.')

    payload = _montar_payload_pedido(proposta, mensagens=mensagens)
    extra_msgs = payload.pop('_mensagens', [])
    with transaction.atomic():
        serializer = PedidoVendaSerializer(data=payload, context={'allow_proposta_vinculo': True})
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()
        proposta.status = STATUS_PROPOSTA_CONVERTIDA
        proposta.save(update_fields=['status'])
    mensagens_finais = list(extra_msgs)
    mensagens_finais.append(
        'Pedido de venda criado a partir da proposta. Faturamento e NF-e serão tratados em etapa posterior.',
    )
    return _resposta_converter(
        pedido,
        proposta,
        mensagens=mensagens_finais,
        ja_existia=False,
    )
