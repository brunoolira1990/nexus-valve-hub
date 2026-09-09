from rest_framework import serializers

from apps.cadastros.models import Fornecedor

from .models import (
    CotacaoFornecedor,
    CotacaoFornecedorItem,
    CotacaoFornecedorParticipante,
    CotacaoFornecedorRespostaItem,
    ItemProposta,
)


class CotacaoFornecedorRespostaItemSerializer(serializers.ModelSerializer):
    fornecedor_id = serializers.IntegerField(source='participante.fornecedor_id', read_only=True)
    fornecedor_nome = serializers.CharField(source='participante.fornecedor.razao_social', read_only=True)
    selecionada_por_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CotacaoFornecedorRespostaItem
        fields = (
            'id', 'participante', 'cotacao_item', 'fornecedor_id', 'fornecedor_nome',
            'preco_unitario', 'quantidade_atendida', 'prazo_entrega', 'condicao_pagamento',
            'frete', 'frete_tipo', 'marca_fabricante', 'validade', 'observacao', 'status_item',
            'selecionada_como_referencia', 'selecionada_por', 'selecionada_por_nome', 'selecionada_em',
        )
        read_only_fields = ('selecionada_por', 'selecionada_em', 'selecionada_como_referencia')

    def get_selecionada_por_nome(self, obj):
        return getattr(obj.selecionada_por, 'get_username', lambda: '')() if obj.selecionada_por else ''


class CotacaoFornecedorItemSerializer(serializers.ModelSerializer):
    item_proposta_id = serializers.PrimaryKeyRelatedField(
        source='item_proposta', queryset=ItemProposta.objects.all(),
    )
    produto_id = serializers.IntegerField(read_only=True)
    produto_nome = serializers.SerializerMethodField(read_only=True)
    respostas = CotacaoFornecedorRespostaItemSerializer(many=True, read_only=True)

    class Meta:
        model = CotacaoFornecedorItem
        fields = ('id', 'item_proposta_id', 'produto_id', 'produto_nome', 'produto_snapshot', 'quantidade', 'observacao_tecnica', 'status', 'respostas')
        read_only_fields = ('produto_id', 'produto_nome', 'produto_snapshot', 'status', 'respostas')

    def get_produto_nome(self, obj):
        return getattr(obj.produto, 'descricao', '') if obj.produto_id else (obj.produto_snapshot or {}).get('descricao', '')

    def validate_item_proposta_id(self, value):
        proposta_id = self.context.get('proposta_id')
        if proposta_id and value.proposta_id != int(proposta_id):
            raise serializers.ValidationError('O item não pertence à Proposta da cotação.')
        return value


class CotacaoFornecedorParticipanteSerializer(serializers.ModelSerializer):
    fornecedor_id = serializers.PrimaryKeyRelatedField(source='fornecedor', queryset=Fornecedor.objects.filter(ativo=True))
    fornecedor_nome = serializers.CharField(source='fornecedor.razao_social', read_only=True)
    respostas = CotacaoFornecedorRespostaItemSerializer(many=True, read_only=True)

    class Meta:
        model = CotacaoFornecedorParticipante
        fields = ('id', 'fornecedor_id', 'fornecedor_nome', 'status', 'enviado_em', 'respondido_em', 'observacao', 'respostas')
        read_only_fields = ('status', 'enviado_em', 'respondido_em', 'respostas')


class CotacaoFornecedorSerializer(serializers.ModelSerializer):
    proposta_id = serializers.PrimaryKeyRelatedField(source='proposta', read_only=True)
    responsavel_nome = serializers.SerializerMethodField(read_only=True)
    itens = CotacaoFornecedorItemSerializer(many=True, read_only=True)
    participantes = CotacaoFornecedorParticipanteSerializer(many=True, read_only=True)

    class Meta:
        model = CotacaoFornecedor
        fields = ('id', 'numero', 'proposta_id', 'data', 'responsavel', 'responsavel_nome', 'prazo_resposta', 'observacao', 'status', 'criado_em', 'atualizado_em', 'itens', 'participantes')
        read_only_fields = ('numero', 'responsavel', 'responsavel_nome', 'status', 'criado_em', 'atualizado_em', 'itens', 'participantes')

    def get_responsavel_nome(self, obj):
        return obj.responsavel.get_username() if obj.responsavel_id else ''


class CotacaoFornecedorCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CotacaoFornecedor
        fields = ('proposta', 'data', 'prazo_resposta', 'observacao')

    def validate_proposta(self, value):
        if not value.itens.exists():
            raise serializers.ValidationError('A Proposta precisa ter ao menos um item.')
        return value


class CotacaoFornecedorRespostaInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = CotacaoFornecedorRespostaItem
        fields = ('participante', 'cotacao_item', 'preco_unitario', 'quantidade_atendida', 'prazo_entrega', 'condicao_pagamento', 'frete', 'frete_tipo', 'marca_fabricante', 'validade', 'observacao', 'status_item')

    def validate(self, attrs):
        participante = attrs['participante']
        item = attrs['cotacao_item']
        if participante.cotacao_id != item.cotacao_id:
            raise serializers.ValidationError('Participante e item pertencem a cotações diferentes.')
        if attrs.get('status_item', CotacaoFornecedorRespostaItem.StatusItem.RESPONDIDO) == CotacaoFornecedorRespostaItem.StatusItem.RESPONDIDO and attrs.get('preco_unitario') is None:
            raise serializers.ValidationError({'preco_unitario': 'Preço unitário é obrigatório para resposta respondida.'})
        return attrs
