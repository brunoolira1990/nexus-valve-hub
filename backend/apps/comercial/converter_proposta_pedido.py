"""Propostas — conversão parcial/total de proposta em pedido de venda."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.comercial import pricing as price_rules
from apps.comercial.commercial_defaults import (
    STATUS_ITEM_CANCELADO,
    STATUS_ITEM_PERDIDO,
    STATUS_PROPOSTA_CONVERTIDA,
    STATUS_PROPOSTA_REABERTA,
)
from apps.comercial.models import ItemProposta, PedidoVenda, Proposta, PropostaComercialHistorico
from apps.comercial.proposta_comercial_historico import registrar_evento_comercial
from apps.comercial.proposta_comercial_status import (
    calcular_status_proposta_apos_conversao,
    item_pode_converter,
    itens_pendentes_conversao,
    marcar_item_cancelado_ou_perdido,
    marcar_item_convertido,
    marcar_item_mantido_pendente,
    proposta_requer_recuperacao,
    proposta_totalmente_convertida,
    status_item_proposta,
)
from apps.comercial.serializers import ItemPropostaSerializer, PedidoVendaSerializer, recalcular_pedido_venda
from apps.comercial.vendedor_helpers import nome_vendedor_exibicao

STATUS_PEDIDO_INICIAL = 'ABERTO'
STATUS_PROPOSTA_APROVADA = frozenset({'aprovada', 'aprovado', 'aceita', 'aceito'})
STATUS_PROPOSTA_BLOQUEIO = frozenset({'rejeitada', 'rejeitado', 'cancelada', 'cancelado', 'perdida', 'perdido'})

MSG_PROPOSTA_JA_CONVERTIDA = 'Esta proposta já foi convertida integralmente em pedido de venda.'
MSG_PROPOSTA_CANCELADA_RECUPERAR = (
    'Esta proposta está cancelada/perdida. Recupere a proposta antes de gerar Pedido de Venda.'
)
MSG_NENHUM_ITEM_SELECIONADO = 'Selecione ao menos um item da proposta para gerar o pedido de venda.'
ACAO_MANTER_PENDENTE = 'MANTER_PENDENTE'
ACAO_CANCELAR = 'CANCELAR'

_MONETARY_QUANT = Decimal('0.01')


def _round_monetary(value: Decimal) -> Decimal:
    return value.quantize(_MONETARY_QUANT, rounding=ROUND_HALF_UP)


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


class RecuperarPropostaDict(TypedDict):
    proposta_id: int
    proposta_status: str
    mensagem: str


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


def _snapshot_conversao_proposta(proposta: Proposta, *, parcial: bool, itens_ids: list[int]) -> dict[str, Any]:
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
        'conversao_parcial': parcial,
        'itens_proposta_ids': itens_ids,
    }


def _valor_item_proposta(item: ItemProposta) -> Decimal:
    qtd = item.quantidade_negociada or item.quantidade
    preco = item.preco_por_unidade_negociada or item.valor_unitario or item.preco_final
    bruto = (qtd * preco) - (item.desconto or Decimal('0'))
    return _round_monetary(bruto)


def validar_proposta_para_conversao(proposta: Proposta, *, parcial: bool = False) -> tuple[bool, list[str]]:
    mensagens: list[str] = []
    if proposta_requer_recuperacao(proposta):
        return False, [MSG_PROPOSTA_CANCELADA_RECUPERAR]
    if not parcial and proposta_totalmente_convertida(proposta):
        return False, [MSG_PROPOSTA_JA_CONVERTIDA]
    st = (proposta.status or '').strip().lower()
    if st in STATUS_PROPOSTA_BLOQUEIO:
        return False, [MSG_PROPOSTA_CANCELADA_RECUPERAR]
    if st not in STATUS_PROPOSTA_APROVADA and st not in (
        'pendente',
        'parcialmente_convertida',
        'reaberta',
        'enviada',
        'aberta',
        'em_negociacao',
    ):
        if st != STATUS_PROPOSTA_CONVERTIDA.lower():
            mensagens.append(
                'A proposta não está com status comercial «Aprovada». '
                'A conversão segue permitida conforme a regra atual do sistema.',
            )
    if not proposta.cliente_id:
        return False, ['Vincule um cliente cadastrado para converter a proposta em pedido.']
    if not itens_pendentes_conversao(proposta):
        return False, ['Não há itens pendentes para converter em pedido de venda.']
    pendentes = itens_pendentes_conversao(proposta)
    for item in pendentes:
        if item.produto_id:
            continue
        if not price_rules.ncm_fiscal_valido(item.ncm_avulso or ''):
            return False, [
                'Existem itens avulsos sem NCM válido (8 dígitos). '
                'Regularize antes de converter em pedido.',
            ]
    if proposta.itens.filter(produto__isnull=True).exists():
        avulsos_pendentes = [it for it in pendentes if not it.produto_id]
        if avulsos_pendentes:
            return False, [
                'Vincule todos os itens avulsos a produtos cadastrados antes de converter. '
                'O pedido e o faturamento exigem produto no cadastro.',
            ]
    if not proposta.itens.exists():
        return False, ['A proposta não possui itens para converter.']
    return True, mensagens


def _montar_item_payload(item: ItemProposta, proposta: Proposta) -> dict[str, Any]:
    qtd = item.quantidade_negociada or item.quantidade
    preco = item.preco_por_unidade_negociada or item.valor_unitario or item.preco_final
    return {
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
    }


def _montar_payload_pedido(
    proposta: Proposta,
    *,
    itens: list[ItemProposta],
    mensagens: list[str],
    observacao: str = '',
) -> dict[str, Any]:
    itens_payload = [_montar_item_payload(item, proposta) for item in itens]
    valor_total = _round_monetary(
        sum((_valor_item_proposta(item) for item in itens), Decimal('0')),
    )
    obs_internas = (proposta.homologacao_fiscal_observacao or '').strip()
    if observacao.strip():
        extra = observacao.strip()
        obs_internas = f'{obs_internas}\n{extra}'.strip() if obs_internas else extra
    parcial = len(itens) < proposta.itens.count()
    return {
        'empresa_emitente_id': proposta.empresa_emitente_id,
        'cliente_id': proposta.cliente_id,
        'data': proposta.data.isoformat(),
        'status': STATUS_PEDIDO_INICIAL,
        'condicao_pagamento_texto': proposta.condicao_pagamento_texto,
        'dias_parcelas': proposta.dias_parcelas,
        'quantidade_parcelas': proposta.quantidade_parcelas,
        'vencimentos_previstos': [d.isoformat() for d in proposta.vencimentos_previstos],
        'valor_total': valor_total,
        'proposta_id': proposta.id,
        'vendedor': nome_vendedor_exibicao(proposta),
        'vendedor_id': proposta.vendedor_ref_id,
        'prazo_entrega_texto': (proposta.prazo_entrega_texto or '').strip(),
        'prazo_entrega': None,
        'observacoes_comerciais': (proposta.mensagem_comercial or '').strip(),
        'observacoes_internas': obs_internas,
        'snapshot_conversao': _snapshot_conversao_proposta(
            proposta,
            parcial=parcial,
            itens_ids=[it.pk for it in itens],
        ),
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


def _resolver_itens_selecionados(proposta: Proposta, itens_payload: list[dict] | None) -> list[ItemProposta]:
    pendentes = {it.pk: it for it in itens_pendentes_conversao(proposta)}
    if not itens_payload:
        return list(pendentes.values())
    ids: list[int] = []
    for row in itens_payload:
        raw_id = row.get('proposta_item_id') or row.get('item_proposta_id') or row.get('id')
        if raw_id is None:
            continue
        ids.append(int(raw_id))
    if not ids:
        raise ValueError(MSG_NENHUM_ITEM_SELECIONADO)
    selecionados: list[ItemProposta] = []
    for iid in ids:
        item = pendentes.get(iid)
        if item is None:
            inst = proposta.itens.filter(pk=iid).first()
            if inst is None:
                raise ValueError(f'Item da proposta #{iid} não encontrado.')
            st = status_item_proposta(inst)
            if st == 'CONVERTIDO_EM_PEDIDO':
                raise ValueError(f'O item #{iid} já foi convertido em pedido de venda.')
            raise ValueError(f'O item #{iid} não está disponível para conversão (status: {st}).')
        selecionados.append(item)
    return selecionados


def _sincronizar_status_legado_com_pedido(proposta: Proposta) -> None:
    """Alinha proposta com pedido já vinculado (legado 2.6.4 / migration 0029)."""
    if not proposta.pedidos_gerados.exists():
        return
    if (proposta.status or '').strip().upper() != STATUS_PROPOSTA_CONVERTIDA:
        proposta.status = STATUS_PROPOSTA_CONVERTIDA
        proposta.save(update_fields=['status'])


def gerar_pedido_venda_de_proposta(
    proposta: Proposta,
    *,
    itens_payload: list[dict] | None = None,
    acao_itens_nao_selecionados: Literal['MANTER_PENDENTE', 'CANCELAR'] = ACAO_MANTER_PENDENTE,
    observacao: str = '',
    usuario=None,
) -> ConverterPropostaPedidoDict:
    proposta = Proposta.objects.select_related(
        'cliente',
        'empresa_emitente',
        'cenario_fiscal_saida',
        'vendedor_ref',
    ).prefetch_related('itens__produto', 'pedidos_gerados').get(pk=proposta.pk)

    if proposta_totalmente_convertida(proposta):
        raise ValueError(MSG_PROPOSTA_JA_CONVERTIDA)

    if not itens_payload and proposta.pedidos_gerados.exists():
        _sincronizar_status_legado_com_pedido(proposta)
        raise ValueError(MSG_PROPOSTA_JA_CONVERTIDA)

    parcial = bool(itens_payload)
    ok, mensagens = validar_proposta_para_conversao(proposta, parcial=parcial)
    if not ok:
        raise ValueError(mensagens[0] if mensagens else 'Proposta não pode ser convertida.')

    selecionados = _resolver_itens_selecionados(proposta, itens_payload)
    if not selecionados:
        raise ValueError(MSG_NENHUM_ITEM_SELECIONADO)

    selecionados_ids = {it.pk for it in selecionados}
    nao_selecionados = [it for it in itens_pendentes_conversao(proposta) if it.pk not in selecionados_ids]

    payload = _montar_payload_pedido(proposta, itens=selecionados, mensagens=mensagens, observacao=observacao)
    extra_msgs = payload.pop('_mensagens', [])

    with transaction.atomic():
        serializer = PedidoVendaSerializer(
            data=payload,
            context={
                'allow_proposta_vinculo': True,
                'allow_multi_pedido_proposta': bool(itens_payload),
            },
        )
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()
        links = {
            ipv.item_proposta_id: ipv
            for ipv in pedido.itens.filter(item_proposta_id__isnull=False).select_related('pedido')
        }

        for item in selecionados:
            marcar_item_convertido(
                item,
                pedido=pedido,
                item_pedido=links.get(item.pk),
                usuario=usuario,
            )
            registrar_evento_comercial(
                proposta,
                PropostaComercialHistorico.TipoEvento.ITEM_CONVERTIDO,
                descricao=f'Item #{item.pk} convertido no pedido {pedido.numero}.',
                usuario=usuario,
                dados_json={
                    'item_proposta_id': item.pk,
                    'pedido_venda_id': pedido.pk,
                    'pedido_venda_numero': pedido.numero,
                    'item_pedido_venda_id': links[item.pk].pk if item.pk in links else None,
                },
            )

        if acao_itens_nao_selecionados == ACAO_CANCELAR:
            for item in nao_selecionados:
                marcar_item_cancelado_ou_perdido(item, status=STATUS_ITEM_CANCELADO, usuario=usuario)
                registrar_evento_comercial(
                    proposta,
                    PropostaComercialHistorico.TipoEvento.ITEM_CANCELADO,
                    descricao=f'Item #{item.pk} cancelado (não selecionado na geração do pedido {pedido.numero}).',
                    usuario=usuario,
                    dados_json={'item_proposta_id': item.pk, 'pedido_venda_id': pedido.pk},
                )
        else:
            for item in nao_selecionados:
                marcar_item_mantido_pendente(item)
                registrar_evento_comercial(
                    proposta,
                    PropostaComercialHistorico.TipoEvento.ITEM_MANTIDO_PENDENTE,
                    descricao=f'Item #{item.pk} mantido pendente após geração do pedido {pedido.numero}.',
                    usuario=usuario,
                    dados_json={'item_proposta_id': item.pk, 'pedido_venda_id': pedido.pk},
                )

        proposta.status = calcular_status_proposta_apos_conversao(proposta)
        hist_desc = (
            f'Pedido de venda {pedido.numero} gerado com {len(selecionados)} item(ns). '
            f'Itens restantes: {acao_itens_nao_selecionados.lower()}.'
        )
        if observacao.strip():
            hist_desc += f' Obs.: {observacao.strip()}'
        registrar_evento_comercial(
            proposta,
            PropostaComercialHistorico.TipoEvento.PEDIDO_GERADO,
            descricao=hist_desc,
            usuario=usuario,
            dados_json={
                'pedido_venda_id': pedido.pk,
                'pedido_venda_numero': pedido.numero,
                'itens_convertidos_ids': [it.pk for it in selecionados],
                'acao_itens_nao_selecionados': acao_itens_nao_selecionados,
            },
        )
        proposta.save(update_fields=['status'])
        recalcular_pedido_venda(pedido)

    mensagens_finais = list(extra_msgs)
    mensagens_finais.append(
        f'Pedido de venda {pedido.numero} criado a partir da proposta. '
        'Faturamento e NF-e serão tratados em etapa posterior.',
    )
    proposta.refresh_from_db()
    return _resposta_converter(pedido, proposta, mensagens=mensagens_finais, ja_existia=False)


def converter_proposta_em_pedido_venda(proposta: Proposta) -> ConverterPropostaPedidoDict:
    """Conversão total dos itens pendentes (compatibilidade com endpoint legado)."""
    return gerar_pedido_venda_de_proposta(proposta, itens_payload=None, acao_itens_nao_selecionados=ACAO_MANTER_PENDENTE)


def recuperar_proposta_comercial(proposta: Proposta, *, motivo: str, usuario=None) -> RecuperarPropostaDict:
    proposta = Proposta.objects.prefetch_related('itens', 'pedidos_gerados').get(pk=proposta.pk)
    motivo_limpo = (motivo or '').strip()
    if not motivo_limpo:
        raise ValueError('Informe o motivo da recuperação da proposta.')

    if proposta_totalmente_convertida(proposta):
        raise ValueError('Proposta já convertida integralmente em pedido de venda não pode ser recuperada.')

    if not proposta_requer_recuperacao(proposta):
        raise ValueError('Somente propostas canceladas, perdidas ou rejeitadas podem ser recuperadas.')

    status_anterior = proposta.status
    with transaction.atomic():
        proposta.status = STATUS_PROPOSTA_REABERTA
        proposta.recuperada_em = timezone.now()
        proposta.recuperada_por = usuario if getattr(usuario, 'is_authenticated', False) else None
        proposta.motivo_recuperacao = motivo_limpo
        proposta.status_anterior_recuperacao = status_anterior or ''
        proposta.save(
            update_fields=[
                'status',
                'recuperada_em',
                'recuperada_por',
                'motivo_recuperacao',
                'status_anterior_recuperacao',
            ],
        )
        registrar_evento_comercial(
            proposta,
            PropostaComercialHistorico.TipoEvento.PROPOSTA_RECUPERADA,
            descricao=f'Proposta recuperada/reaberta (status anterior: {status_anterior}). Motivo: {motivo_limpo}',
            usuario=usuario,
            dados_json={'status_anterior': status_anterior, 'motivo': motivo_limpo},
        )

    return {
        'proposta_id': proposta.pk,
        'proposta_status': proposta.status,
        'mensagem': 'Proposta recuperada com sucesso. Atualize os dados necessários antes de gerar Pedido de Venda.',
    }
