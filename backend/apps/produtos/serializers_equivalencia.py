"""Serializers equivalência/composição — ERP 4.0.13.7 / 4.0.13.7.1."""

from __future__ import annotations

from rest_framework import serializers

from apps.cadastros.models import Fornecedor
from apps.produtos.models import Produto
from apps.produtos.models_equivalencia import (
    FornecedorComposicaoEquivalencia,
    FornecedorComposicaoEquivalenciaItem,
    FornecedorProdutoEquivalencia,
    ProcessoMontagem,
    ProdutoComposicao,
    ProdutoComposicaoItem,
)


class ProcessoMontagemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessoMontagem
        fields = (
            'id',
            'tipo',
            'exige_servico',
            'exige_fornecedor_servico',
            'gera_produto_acabado',
            'baixa_componentes',
            'observacoes',
        )


class ProdutoComposicaoItemSerializer(serializers.ModelSerializer):
    componente_produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='componente_produto',
    )
    componente_codigo = serializers.CharField(source='componente_produto.codigo_completo', read_only=True)
    componente_descricao = serializers.CharField(source='componente_produto.descricao', read_only=True)

    class Meta:
        model = ProdutoComposicaoItem
        fields = (
            'id',
            'componente_produto_id',
            'componente_codigo',
            'componente_descricao',
            'quantidade_por_unidade_final',
            'unidade',
            'obrigatorio',
            'permite_substituto',
            'perda_percentual',
            'ordem',
            'observacoes',
        )


class ProdutoComposicaoSerializer(serializers.ModelSerializer):
    produto_final_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto_final',
    )
    produto_final_codigo = serializers.CharField(source='produto_final.codigo_completo', read_only=True)
    itens = ProdutoComposicaoItemSerializer(many=True, required=False)
    processos = ProcessoMontagemSerializer(many=True, required=False)

    class Meta:
        model = ProdutoComposicao
        fields = (
            'id',
            'produto_final_id',
            'produto_final_codigo',
            'nome',
            'tipo_composicao',
            'descricao',
            'ativo',
            'padrao',
            'permite_alternativa',
            'permite_comprar_pronto',
            'permite_montar',
            'exige_ordem_montagem',
            'exige_confirmacao',
            'exige_servico',
            'tipo_servico',
            'observacoes',
            'itens',
            'processos',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = ('criado_em', 'atualizado_em')

    def create(self, validated_data):
        itens_data = validated_data.pop('itens', [])
        processos_data = validated_data.pop('processos', [])
        comp = ProdutoComposicao.objects.create(**validated_data)
        for raw in itens_data:
            ProdutoComposicaoItem.objects.create(composicao=comp, **raw)
        for raw in processos_data:
            ProcessoMontagem.objects.create(composicao=comp, **raw)
        return comp

    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        processos_data = validated_data.pop('processos', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for raw in itens_data:
                ProdutoComposicaoItem.objects.create(composicao=instance, **raw)
        if processos_data is not None:
            instance.processos.all().delete()
            for raw in processos_data:
                ProcessoMontagem.objects.create(composicao=instance, **raw)
        return instance


class FornecedorProdutoEquivalenciaSerializer(serializers.ModelSerializer):
    produto_interno_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto_interno',
    )
    fornecedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(),
        source='fornecedor',
    )
    produto_interno_codigo = serializers.CharField(source='produto_interno.codigo_completo', read_only=True)

    class Meta:
        model = FornecedorProdutoEquivalencia
        fields = (
            'id',
            'fornecedor_id',
            'cnpj_raiz_fornecedor',
            'cnpj_filial_fornecedor',
            'escopo_cnpj',
            'produto_interno_id',
            'produto_interno_codigo',
            'codigo_fornecedor',
            'descricao_fornecedor_normalizada',
            'ncm_fornecedor',
            'unidade_fornecedor',
            'fator_conversao',
            'tolerancia_quantidade',
            'tolerancia_valor',
            'ativo',
            'confianca_padrao',
            'origem',
            'observacoes',
        )


class FornecedorComposicaoEquivalenciaItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FornecedorComposicaoEquivalenciaItem
        fields = (
            'id',
            'codigo_fornecedor',
            'descricao_fornecedor_normalizada',
            'ncm_fornecedor',
            'produto_componente_interno',
            'quantidade_componente_por_produto_final',
            'unidade',
            'obrigatorio',
            'ordem',
            'peso_match_codigo',
            'peso_match_descricao',
            'peso_match_ncm',
            'observacoes',
        )


class FornecedorComposicaoEquivalenciaSerializer(serializers.ModelSerializer):
    produto_interno_final_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto_interno_final',
    )
    fornecedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(),
        source='fornecedor',
    )
    itens = FornecedorComposicaoEquivalenciaItemSerializer(many=True, required=False)

    class Meta:
        model = FornecedorComposicaoEquivalencia
        fields = (
            'id',
            'fornecedor_id',
            'cnpj_raiz_fornecedor',
            'cnpj_filial_fornecedor',
            'escopo_cnpj',
            'produto_interno_final_id',
            'descricao',
            'tolerancia_valor_percentual',
            'tolerancia_valor_absoluto',
            'tolerancia_quantidade',
            'ativo',
            'origem',
            'observacoes',
            'itens',
        )

    def create(self, validated_data):
        itens_data = validated_data.pop('itens', [])
        obj = FornecedorComposicaoEquivalencia.objects.create(**validated_data)
        for raw in itens_data:
            FornecedorComposicaoEquivalenciaItem.objects.create(equivalencia_composta=obj, **raw)
        return obj
