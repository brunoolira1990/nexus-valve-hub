from decimal import Decimal

from rest_framework import serializers

from .models import Ncm, Polegada, Produto


class NcmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ncm
        fields = '__all__'


class PolegadaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Polegada
        fields = '__all__'


class ProdutoSerializer(serializers.ModelSerializer):
    preco_custo = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    preco_venda = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    estoque_minimo = serializers.DecimalField(max_digits=14, decimal_places=3, coerce_to_string=False)

    class Meta:
        model = Produto
        fields = '__all__'
        read_only_fields = ('codigo_completo',)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in ('preco_custo', 'preco_venda', 'estoque_minimo'):
            if k in data and data[k] is not None:
                data[k] = float(Decimal(str(data[k])))
        return data
