"""
Correlação fornecedor × código NF-e (cProd) → produto interno na conferência de entrada.

Reutiliza FornecedorProdutoEquivalencia (cadastro de equivalências) — persiste ao vincular
produto na conferência e sugere na abertura de notas subsequentes do mesmo fornecedor.
"""

from __future__ import annotations

from typing import Any, TypedDict

from apps.fiscal.models import ItemNFeEntradaConferencia, NFeEntradaConferencia
from apps.produtos.cnpj_fornecedor import cnpj_apenas_digitos, cnpj_raiz
from apps.produtos.descricao_normalizacao import normalizar_codigo_fornecedor, normalizar_descricao_produto
from apps.produtos.models_equivalencia import (
    EscopoCnpjFornecedor,
    FornecedorProdutoEquivalencia,
    OrigemEquivalencia,
)


class ProdutoSugeridoCorrelacaoDict(TypedDict):
    id: int
    codigo: str
    descricao: str
    codigo_fornecedor: str
    descricao_fornecedor: str


def _cnpj_emitente_nf(conferencia: NFeEntradaConferencia) -> tuple[str, str]:
    nf = conferencia.nf_entrada_historica
    emit = nf.emit_json if isinstance(nf.emit_json, dict) else {}
    cnpj = cnpj_apenas_digitos(str(emit.get('CNPJ') or emit.get('cnpj') or ''))
    if not cnpj and nf.fornecedor_emitente_id:
        cnpj = cnpj_apenas_digitos(nf.fornecedor_emitente.cnpj or '')
    return cnpj, cnpj_raiz(cnpj)


def _codigo_fornecedor_item(item_conf: ItemNFeEntradaConferencia) -> str:
    prod_json = item_conf.item_nfe_historico.prod_json or {}
    return normalizar_codigo_fornecedor(str(prod_json.get('cProd') or '').strip())


def _buscar_equivalencia_fornecedor(
    *,
    fornecedor_id: int | None,
    cnpj_emit: str,
    cnpj_raiz_emit: str,
    codigo_fornecedor: str,
) -> FornecedorProdutoEquivalencia | None:
    if not codigo_fornecedor:
        return None
    qs = FornecedorProdutoEquivalencia.objects.filter(
        ativo=True,
        codigo_fornecedor=codigo_fornecedor,
    ).select_related('produto_interno')
    if fornecedor_id:
        qs = qs.filter(fornecedor_id=fornecedor_id)
    elif cnpj_raiz_emit:
        qs = qs.filter(cnpj_raiz_fornecedor=cnpj_raiz_emit)
    else:
        return None
    return qs.order_by('-atualizado_em', '-id').first()


def persistir_correlacao_produto_fornecedor_conferencia(
    item_conf: ItemNFeEntradaConferencia,
    conferencia: NFeEntradaConferencia,
) -> FornecedorProdutoEquivalencia | None:
    """Salva/atualiza correlação quando operador vincula produto na conferência."""
    if not item_conf.produto_id:
        return None

    codigo = _codigo_fornecedor_item(item_conf)
    if not codigo:
        return None

    nf = conferencia.nf_entrada_historica
    fornecedor_id = nf.fornecedor_emitente_id
    if not fornecedor_id:
        return None

    prod_json = item_conf.item_nfe_historico.prod_json or {}
    cnpj_emit, cnpj_raiz_emit = _cnpj_emitente_nf(conferencia)
    descricao_norm = normalizar_descricao_produto(prod_json.get('xProd'))
    ncm = str(prod_json.get('NCM') or prod_json.get('ncm') or '').strip()[:8]

    defaults: dict[str, Any] = {
        'produto_interno_id': item_conf.produto_id,
        'cnpj_raiz_fornecedor': cnpj_raiz_emit,
        'cnpj_filial_fornecedor': cnpj_emit,
        'escopo_cnpj': EscopoCnpjFornecedor.RAIZ,
        'descricao_fornecedor_normalizada': descricao_norm,
        'ncm_fornecedor': ncm,
        'origem': OrigemEquivalencia.IMPORTACAO_HISTORICA,
        'ativo': True,
    }

    existente = (
        FornecedorProdutoEquivalencia.objects.filter(
            fornecedor_id=fornecedor_id,
            codigo_fornecedor=codigo,
        )
        .order_by('-atualizado_em', '-id')
        .first()
    )
    if existente:
        for campo, valor in defaults.items():
            setattr(existente, campo, valor)
        existente.save()
        return existente

    return FornecedorProdutoEquivalencia.objects.create(
        fornecedor_id=fornecedor_id,
        codigo_fornecedor=codigo,
        **defaults,
    )


def buscar_produto_sugerido_correlacao(
    item_conf: ItemNFeEntradaConferencia,
) -> ProdutoSugeridoCorrelacaoDict | None:
    """Sugere produto interno a partir de correlação salva (fornecedor + cProd)."""
    if item_conf.produto_id:
        return None

    codigo = _codigo_fornecedor_item(item_conf)
    if not codigo:
        return None

    conferencia = item_conf.conferencia
    nf = conferencia.nf_entrada_historica
    cnpj_emit, cnpj_raiz_emit = _cnpj_emitente_nf(conferencia)
    eq = _buscar_equivalencia_fornecedor(
        fornecedor_id=nf.fornecedor_emitente_id,
        cnpj_emit=cnpj_emit,
        cnpj_raiz_emit=cnpj_raiz_emit,
        codigo_fornecedor=codigo,
    )
    if not eq or not eq.produto_interno_id:
        return None

    prod_json = item_conf.item_nfe_historico.prod_json or {}
    produto = eq.produto_interno
    return {
        'id': produto.id,
        'codigo': produto.codigo_completo,
        'descricao': produto.descricao,
        'codigo_fornecedor': codigo,
        'descricao_fornecedor': str(prod_json.get('xProd') or '').strip(),
    }
