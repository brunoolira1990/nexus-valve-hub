"""Views equivalência/composição — ERP 4.0.13.7."""

from __future__ import annotations

from rest_framework import viewsets

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin
from nexus_erp.pagination import NexusPageNumberPagination

from apps.produtos.models_equivalencia import (
    FornecedorComposicaoEquivalencia,
    FornecedorProdutoEquivalencia,
    ProdutoComposicao,
)
from apps.produtos.serializers_equivalencia import (
    FornecedorComposicaoEquivalenciaSerializer,
    FornecedorProdutoEquivalenciaSerializer,
    ProdutoComposicaoSerializer,
)


class ProdutoComposicaoViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = ProdutoComposicao.objects.select_related('produto_final').prefetch_related(
        'itens__componente_produto',
        'processos',
    )
    serializer_class = ProdutoComposicaoSerializer
    pagination_class = NexusPageNumberPagination
    search_fields = ('descricao', 'produto_final__codigo_completo', 'produto_final__descricao')

    def get_queryset(self):
        qs = super().get_queryset()
        pid = self.request.query_params.get('produto_final_id')
        if pid:
            qs = qs.filter(produto_final_id=pid)
        return qs


class FornecedorProdutoEquivalenciaViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = FornecedorProdutoEquivalencia.objects.select_related('produto_interno', 'fornecedor')
    serializer_class = FornecedorProdutoEquivalenciaSerializer
    pagination_class = NexusPageNumberPagination
    search_fields = ('codigo_fornecedor', 'descricao_fornecedor_normalizada', 'produto_interno__codigo_completo')

    def get_queryset(self):
        qs = super().get_queryset()
        fid = self.request.query_params.get('fornecedor_id')
        if fid:
            qs = qs.filter(fornecedor_id=fid)
        pid = self.request.query_params.get('produto_interno_id')
        if pid:
            qs = qs.filter(produto_interno_id=pid)
        return qs


class FornecedorComposicaoEquivalenciaViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = FornecedorComposicaoEquivalencia.objects.select_related(
        'produto_interno_final',
        'fornecedor',
    ).prefetch_related('itens')
    serializer_class = FornecedorComposicaoEquivalenciaSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        fid = self.request.query_params.get('fornecedor_id')
        if fid:
            qs = qs.filter(fornecedor_id=fid)
        return qs
