from decimal import Decimal

from rest_framework import serializers

from apps.cadastros.models import Cliente, Fornecedor
from apps.corridas.models import Corrida
from apps.produtos.models import Produto

from .models import (
    ItemPedidoCompra,
    ItemPedidoVenda,
    ItemProposta,
    PedidoCompra,
    PedidoVenda,
    Proposta,
)


def _dec(v):
    return Decimal(str(v)) if v is not None else Decimal('0')


def recalcular_proposta(proposta: Proposta) -> None:
    total = Decimal('0')
    for it in proposta.itens.all():
        total += _dec(it.quantidade) * _dec(it.valor_unitario) - _dec(it.desconto)
    proposta.valor_total = total
    proposta.save(update_fields=['valor_total'])


def recalcular_pedido_venda(pedido: PedidoVenda) -> None:
    total = sum(
        (_dec(it.quantidade) * _dec(it.valor_unitario) for it in pedido.itens.all()),
        Decimal('0'),
    )
    pedido.valor_total = total
    pedido.save(update_fields=['valor_total'])


def recalcular_pedido_compra(pedido: PedidoCompra) -> None:
    total = sum(
        (_dec(it.quantidade) * _dec(it.valor_unitario) for it in pedido.itens.all()),
        Decimal('0'),
    )
    pedido.valor_total = total
    pedido.save(update_fields=['valor_total'])


class ItemPropostaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemProposta
        fields = ('id', 'produto_id', 'produto_nome', 'quantidade', 'valor_unitario', 'desconto')

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        return data


class PropostaSerializer(serializers.ModelSerializer):
    cliente_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(),
        source='cliente',
    )
    cliente_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemPropostaSerializer(many=True)

    class Meta:
        model = Proposta
        fields = (
            'id',
            'numero',
            'cliente_id',
            'cliente_nome',
            'data',
            'validade',
            'vendedor',
            'status',
            'valor_total',
            'itens',
        )

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['cliente_id'] = instance.cliente_id
        data['data'] = instance.data.isoformat()
        data['validade'] = instance.validade.isoformat()
        data['valor_total'] = float(instance.valor_total)
        return data

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        proposta = Proposta.objects.create(**validated_data)
        for item in itens_data:
            ItemProposta.objects.create(proposta=proposta, **item)
        recalcular_proposta(proposta)
        return proposta

    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemProposta.objects.create(proposta=instance, **item)
        recalcular_proposta(instance)
        return instance


class ItemPedidoVendaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
    )
    corrida_id = serializers.PrimaryKeyRelatedField(
        queryset=Corrida.objects.all(),
        source='corrida',
        allow_null=True,
        required=False,
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)
    corrida_numero = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemPedidoVenda
        fields = (
            'id',
            'produto_id',
            'produto_nome',
            'quantidade',
            'valor_unitario',
            'corrida_id',
            'corrida_numero',
        )

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def get_corrida_numero(self, obj):
        return obj.corrida.numero if obj.corrida_id else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        data['corrida_id'] = instance.corrida_id
        return data


class PedidoVendaSerializer(serializers.ModelSerializer):
    cliente_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(),
        source='cliente',
    )
    proposta_id = serializers.PrimaryKeyRelatedField(
        queryset=Proposta.objects.all(),
        source='proposta',
        allow_null=True,
        required=False,
    )
    cliente_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemPedidoVendaSerializer(many=True)

    class Meta:
        model = PedidoVenda
        fields = (
            'id',
            'numero',
            'cliente_id',
            'cliente_nome',
            'data',
            'status',
            'valor_total',
            'proposta_id',
            'itens',
        )

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['cliente_id'] = instance.cliente_id
        data['data'] = instance.data.isoformat()
        data['valor_total'] = float(instance.valor_total)
        data['proposta_id'] = instance.proposta_id
        return data

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        pedido = PedidoVenda.objects.create(**validated_data)
        for item in itens_data:
            ItemPedidoVenda.objects.create(pedido=pedido, **item)
        recalcular_pedido_venda(pedido)
        return pedido

    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemPedidoVenda.objects.create(pedido=instance, **item)
        recalcular_pedido_venda(instance)
        return instance


class ItemPedidoCompraSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemPedidoCompra
        fields = ('id', 'produto_id', 'produto_nome', 'quantidade', 'valor_unitario')

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        return data


class PedidoCompraSerializer(serializers.ModelSerializer):
    fornecedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(),
        source='fornecedor',
    )
    fornecedor_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemPedidoCompraSerializer(many=True)

    class Meta:
        model = PedidoCompra
        fields = (
            'id',
            'numero',
            'fornecedor_id',
            'fornecedor_nome',
            'data',
            'status',
            'valor_total',
            'itens',
        )

    def get_fornecedor_nome(self, obj):
        return obj.fornecedor.razao_social

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['fornecedor_id'] = instance.fornecedor_id
        data['data'] = instance.data.isoformat()
        data['valor_total'] = float(instance.valor_total)
        return data

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        pedido = PedidoCompra.objects.create(**validated_data)
        for item in itens_data:
            ItemPedidoCompra.objects.create(pedido=pedido, **item)
        recalcular_pedido_compra(pedido)
        return pedido

    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemPedidoCompra.objects.create(pedido=instance, **item)
        recalcular_pedido_compra(instance)
        return instance
