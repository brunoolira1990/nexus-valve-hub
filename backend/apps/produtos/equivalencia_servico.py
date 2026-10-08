"""Serviço operacional de equivalência — confirmação manual, sem efeitos financeiros/estoque."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    NFeEntradaAgrupamentoConferencia,
    NFeEntradaAgrupamentoItem,
    NFeEntradaConferencia,
)
from apps.produtos.cnpj_fornecedor import cnpj_apenas_digitos, cnpj_raiz
from apps.produtos.descricao_normalizacao import normalizar_codigo_fornecedor, normalizar_descricao_produto
from apps.produtos.equivalencia_sugestao import _dec, _emit_cnpj, _item_nf_dados, _valor_item_pedido
from apps.produtos.models_equivalencia import (
    EscopoCnpjFornecedor,
    FornecedorComposicaoEquivalencia,
    FornecedorComposicaoEquivalenciaItem,
    FornecedorProdutoEquivalencia,
    OrigemEquivalencia,
)


class EquivalenciaOperacionalError(ValueError):
    pass


def _snapshot_rastreabilidade(conferencia: NFeEntradaConferencia, itens_conf: list[ItemNFeEntradaConferencia]) -> dict:
    nf = conferencia.nf_entrada_historica
    return {
        'nfe_entrada_historica_id': nf.id,
        'chave_acesso': nf.chave_acesso,
        'fornecedor_id': nf.fornecedor_emitente_id,
        'itens_originais': [_item_nf_dados(it) for it in itens_conf],
    }


@transaction.atomic
def confirmar_agrupamento_equivalencia(
    conferencia: NFeEntradaConferencia,
    *,
    produto_interno_id: int,
    item_pedido_compra_id: int | None,
    itens_nfe_conferencia_ids: list[int],
    tipo_agrupamento: str,
    quantidade_equivalente: Decimal | str,
    confianca: int = 0,
    motivo_confirmacao: str = '',
    salvar_regra_fornecedor: bool = False,
    usuario=None,
) -> NFeEntradaAgrupamentoConferencia:
    """Confirma agrupamento manualmente — não movimenta estoque nem financeiro."""
    if not itens_nfe_conferencia_ids:
        raise EquivalenciaOperacionalError('Selecione ao menos um item da NF-e.')

    itens_conf = list(
        conferencia.itens.filter(id__in=itens_nfe_conferencia_ids).select_related('item_nfe_historico'),
    )
    if len(itens_conf) != len(set(itens_nfe_conferencia_ids)):
        raise EquivalenciaOperacionalError('Itens da NF-e inválidos para esta conferência.')

    for iid in itens_nfe_conferencia_ids:
        if NFeEntradaAgrupamentoItem.objects.filter(item_nfe_conferencia_id=iid).exists():
            raise EquivalenciaOperacionalError(
                f'Item da NF-e #{iid} já está vinculado a outro agrupamento confirmado.',
            )

    valor_nf = sum(_dec(it.valor_total_nf) for it in itens_conf)
    valor_ped = Decimal('0')
    item_pc = None
    if item_pedido_compra_id and conferencia.pedido_compra_id:
        from apps.comercial.models import ItemPedidoCompra

        item_pc = ItemPedidoCompra.objects.filter(
            pk=item_pedido_compra_id,
            pedido_id=conferencia.pedido_compra_id,
        ).first()
        if item_pc:
            valor_ped = _valor_item_pedido(item_pc)

    diff_val = (valor_nf - valor_ped).quantize(Decimal('0.01'))
    agr = NFeEntradaAgrupamentoConferencia.objects.create(
        conferencia=conferencia,
        pedido_compra=conferencia.pedido_compra,
        item_pedido_compra=item_pc,
        produto_interno_resultante_id=produto_interno_id,
        tipo_agrupamento=tipo_agrupamento,
        status=NFeEntradaAgrupamentoConferencia.Status.CONFIRMADO,
        confianca=confianca,
        quantidade_equivalente=_dec(quantidade_equivalente),
        valor_total_agrupado=valor_nf,
        valor_pedido_referencia=valor_ped,
        diferenca_valor=diff_val,
        motivo_confirmacao=motivo_confirmacao,
        usuario_confirmacao=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
        data_confirmacao=timezone.now(),
        salvar_regra_fornecedor=salvar_regra_fornecedor,
        snapshot_rastreabilidade=_snapshot_rastreabilidade(conferencia, itens_conf),
    )
    for it in itens_conf:
        NFeEntradaAgrupamentoItem.objects.create(
            agrupamento=agr,
            item_nfe_conferencia=it,
            quantidade_usada=it.quantidade_nf,
            valor_usado=it.valor_total_nf,
        )

    if salvar_regra_fornecedor:
        _persistir_regra_fornecedor(conferencia, agr, itens_conf, item_pc)

    return agr


def _persistir_regra_fornecedor(
    conferencia: NFeEntradaConferencia,
    agr: NFeEntradaAgrupamentoConferencia,
    itens_conf: list[ItemNFeEntradaConferencia],
    item_pc,
) -> None:
    nf = conferencia.nf_entrada_historica
    fornecedor_id = nf.fornecedor_emitente_id
    if not fornecedor_id:
        return

    cnpj_emit, cnpj_raiz_emit = _emit_cnpj(conferencia)

    if agr.tipo_agrupamento == NFeEntradaAgrupamentoConferencia.TipoAgrupamento.EQUIVALENCIA_SIMPLES:
        if len(itens_conf) == 1:
            dados = _item_nf_dados(itens_conf[0])
            FornecedorProdutoEquivalencia.objects.update_or_create(
                fornecedor_id=fornecedor_id,
                codigo_fornecedor=normalizar_codigo_fornecedor(dados['codigo_fornecedor']),
                produto_interno_id=agr.produto_interno_resultante_id,
                defaults={
                    'cnpj_raiz_fornecedor': cnpj_raiz_emit,
                    'cnpj_filial_fornecedor': cnpj_emit,
                    'escopo_cnpj': EscopoCnpjFornecedor.RAIZ,
                    'descricao_fornecedor_normalizada': dados['descricao_normalizada'],
                    'ncm_fornecedor': (dados.get('ncm') or '')[:8],
                    'origem': OrigemEquivalencia.SUGESTAO_CONFIRMADA,
                    'ativo': True,
                },
            )
        return

    if agr.tipo_agrupamento == NFeEntradaAgrupamentoConferencia.TipoAgrupamento.EQUIVALENCIA_COMPOSTA:
        regra, _ = FornecedorComposicaoEquivalencia.objects.update_or_create(
            fornecedor_id=fornecedor_id,
            produto_interno_final_id=agr.produto_interno_resultante_id,
            defaults={
                'cnpj_raiz_fornecedor': cnpj_raiz_emit,
                'cnpj_filial_fornecedor': cnpj_emit,
                'escopo_cnpj': EscopoCnpjFornecedor.RAIZ,
                'descricao': f'Regra confirmada NF-e {nf.chave_acesso or nf.id}',
                'origem': OrigemEquivalencia.SUGESTAO_CONFIRMADA,
                'ativo': True,
            },
        )
        regra.itens.all().delete()
        qtd_final = _dec(agr.quantidade_equivalente) or Decimal('1')
        for idx, it in enumerate(itens_conf):
            dados = _item_nf_dados(it)
            q_comp = _dec(it.quantidade_nf) / qtd_final if qtd_final else _dec(it.quantidade_nf)
            FornecedorComposicaoEquivalenciaItem.objects.create(
                equivalencia_composta=regra,
                codigo_fornecedor=normalizar_codigo_fornecedor(dados['codigo_fornecedor']),
                descricao_fornecedor_normalizada=dados['descricao_normalizada'],
                ncm_fornecedor=(dados.get('ncm') or '')[:8],
                quantidade_componente_por_produto_final=q_comp,
                unidade=it.unidade_nf,
                ordem=idx,
            )
        agr.regra_equivalencia_composta = regra
        agr.save(update_fields=['regra_equivalencia_composta'])


@transaction.atomic
def rejeitar_sugestao_equivalencia(
    conferencia: NFeEntradaConferencia,
    *,
    produto_interno_id: int,
    itens_nfe_conferencia_ids: list[int],
    motivo: str = '',
    usuario=None,
) -> NFeEntradaAgrupamentoConferencia:
    agr = NFeEntradaAgrupamentoConferencia.objects.create(
        conferencia=conferencia,
        pedido_compra=conferencia.pedido_compra,
        produto_interno_resultante_id=produto_interno_id,
        tipo_agrupamento=NFeEntradaAgrupamentoConferencia.TipoAgrupamento.DIVERGENTE,
        status=NFeEntradaAgrupamentoConferencia.Status.REJEITADO,
        motivo_confirmacao=motivo or 'Sugestão rejeitada pelo usuário.',
        usuario_confirmacao=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
        data_confirmacao=timezone.now(),
    )
    for iid in itens_nfe_conferencia_ids:
        _ = iid  # registrado apenas no snapshot futuro se necessário
    return agr
