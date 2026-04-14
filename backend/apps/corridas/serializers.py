from rest_framework import serializers

from apps.cadastros.models import Fornecedor
from apps.produtos.models import Produto

from .models import Corrida


class CorridaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
    )
    fornecedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(),
        source='fornecedor',
    )
    produto_nome = serializers.SerializerMethodField()
    fornecedor_nome = serializers.SerializerMethodField()

    class Meta:
        model = Corrida
        fields = (
            'id',
            'numero',
            'produto_id',
            'produto_nome',
            'fornecedor_id',
            'fornecedor_nome',
            'data_recebimento',
            'nf_entrada',
            'composicao_quimica',
            'tracao',
            'impacto',
        )

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def get_fornecedor_nome(self, obj):
        return obj.fornecedor.razao_social

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        data['fornecedor_id'] = instance.fornecedor_id
        return data
