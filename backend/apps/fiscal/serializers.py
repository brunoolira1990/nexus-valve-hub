from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.cadastros.models import Cliente, Empresa, Fornecedor, Transportadora
from apps.comercial.models import PedidoCompra, PedidoVenda
from apps.corridas.models import Corrida
from apps.produtos.models import Produto
from apps.qualidade.certificado_pdf import gerar_certificado_pdf
from apps.qualidade.models import Certificado

from .estoque_services import (
    aplicar_todos_itens_entrada,
    aplicar_todos_itens_saida,
    reverter_todos_itens_entrada,
    reverter_todos_itens_saida,
)
from .models import CTeEntrada, ItemNFeEntrada, ItemNFeSaida, NFeEntrada, NFeSaida


def _dec(v):
    return Decimal(str(v)) if v is not None else Decimal('0')


def recalcular_valor_nf_entrada(nf: NFeEntrada) -> None:
    total = sum((_dec(it.valor) * _dec(it.quantidade) for it in nf.itens.all()), Decimal('0'))
    nf.valor_total = total
    nf.save(update_fields=['valor_total'])


def recalcular_valor_nf_saida(nf: NFeSaida) -> None:
    total = sum((_dec(it.valor) * _dec(it.quantidade) for it in nf.itens.all()), Decimal('0'))
    nf.valor_total = total
    nf.save(update_fields=['valor_total'])


class ItemNFeEntradaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.all(), source='produto')
    corrida_id = serializers.PrimaryKeyRelatedField(
        queryset=Corrida.objects.all(),
        source='corrida',
        allow_null=True,
        required=False,
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)
    corrida_numero = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemNFeEntrada
        fields = ('id', 'produto_id', 'produto_nome', 'quantidade', 'valor', 'corrida_id', 'corrida_numero')

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def get_corrida_numero(self, obj):
        return obj.corrida.numero if obj.corrida_id else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        data['corrida_id'] = instance.corrida_id
        return data


class NFeEntradaSerializer(serializers.ModelSerializer):
    fornecedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(),
        source='fornecedor',
    )
    pedido_compra_id = serializers.PrimaryKeyRelatedField(
        queryset=PedidoCompra.objects.all(),
        source='pedido_compra',
        allow_null=True,
        required=False,
    )
    cte_id = serializers.PrimaryKeyRelatedField(
        queryset=CTeEntrada.objects.all(),
        source='cte',
        allow_null=True,
        required=False,
    )
    fornecedor_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemNFeEntradaSerializer(many=True)

    class Meta:
        model = NFeEntrada
        fields = (
            'id',
            'numero',
            'fornecedor_id',
            'fornecedor_nome',
            'data',
            'valor_total',
            'pedido_compra_id',
            'cte_id',
            'itens',
        )

    def get_fornecedor_nome(self, obj):
        return obj.fornecedor.razao_social

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['fornecedor_id'] = instance.fornecedor_id
        data['data'] = instance.data.isoformat()
        data['valor_total'] = float(instance.valor_total)
        data['pedido_compra_id'] = instance.pedido_compra_id
        data['cte_id'] = instance.cte_id
        return data

    @transaction.atomic
    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        nf = NFeEntrada.objects.create(**validated_data)
        for item in itens_data:
            ItemNFeEntrada.objects.create(nf=nf, **item)
        recalcular_valor_nf_entrada(nf)
        try:
            aplicar_todos_itens_entrada(nf)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return nf

    @transaction.atomic
    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        reverter_todos_itens_entrada(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemNFeEntrada.objects.create(nf=instance, **item)
        recalcular_valor_nf_entrada(instance)
        try:
            aplicar_todos_itens_entrada(instance)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return instance


class ItemNFeSaidaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.all(), source='produto')
    corrida_id = serializers.PrimaryKeyRelatedField(
        queryset=Corrida.objects.all(),
        source='corrida',
        allow_null=True,
        required=False,
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)
    corrida_numero = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemNFeSaida
        fields = ('id', 'produto_id', 'produto_nome', 'quantidade', 'valor', 'corrida_id', 'corrida_numero')

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def get_corrida_numero(self, obj):
        return obj.corrida.numero if obj.corrida_id else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        data['corrida_id'] = instance.corrida_id
        return data


def _gerar_ou_atualizar_certificado(nf: NFeSaida) -> None:
    Certificado.objects.filter(nf_saida=nf).delete()
    pdf = gerar_certificado_pdf(nf)
    Certificado.objects.create(nf_saida=nf, arquivo=pdf)


class NFeSaidaSerializer(serializers.ModelSerializer):
    cliente_id = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all(), source='cliente')
    pedido_venda_id = serializers.PrimaryKeyRelatedField(
        queryset=PedidoVenda.objects.all(),
        source='pedido_venda',
        allow_null=True,
        required=False,
    )
    cliente_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemNFeSaidaSerializer(many=True)

    class Meta:
        model = NFeSaida
        fields = (
            'id',
            'numero',
            'cliente_id',
            'cliente_nome',
            'data',
            'valor_total',
            'status',
            'pedido_venda_id',
            'itens',
        )

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['cliente_id'] = instance.cliente_id
        data['data'] = instance.data.isoformat()
        data['valor_total'] = float(instance.valor_total)
        data['pedido_venda_id'] = instance.pedido_venda_id
        return data

    @transaction.atomic
    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        nf = NFeSaida.objects.create(**validated_data)
        for item in itens_data:
            ItemNFeSaida.objects.create(nf=nf, **item)
        recalcular_valor_nf_saida(nf)
        try:
            aplicar_todos_itens_saida(nf)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        _gerar_ou_atualizar_certificado(nf)
        return nf

    @transaction.atomic
    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        reverter_todos_itens_saida(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemNFeSaida.objects.create(nf=instance, **item)
        recalcular_valor_nf_saida(instance)
        try:
            aplicar_todos_itens_saida(instance)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        _gerar_ou_atualizar_certificado(instance)
        return instance


class CTeEntradaSerializer(serializers.ModelSerializer):
    transportadora_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora',
    )
    tomador_id = serializers.PrimaryKeyRelatedField(queryset=Empresa.objects.all(), source='tomador')
    transportadora_nome = serializers.SerializerMethodField(read_only=True)
    tomador_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CTeEntrada
        fields = (
            'id',
            'numero',
            'transportadora_id',
            'transportadora_nome',
            'tomador_id',
            'tomador_nome',
            'valor_frete',
            'data',
            'nfe_ids',
        )

    def get_transportadora_nome(self, obj):
        return obj.transportadora.razao_social

    def get_tomador_nome(self, obj):
        return obj.tomador.razao_social

    def validate_nfe_ids(self, value):
        if not value:
            return value
        found = set(NFeEntrada.objects.filter(pk__in=value).values_list('pk', flat=True))
        missing = set(value) - found
        if missing:
            raise serializers.ValidationError(f'NF-e de entrada inexistentes: {sorted(missing)}')
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['transportadora_id'] = instance.transportadora_id
        data['tomador_id'] = instance.tomador_id
        data['data'] = instance.data.isoformat()
        data['valor_frete'] = float(instance.valor_frete)
        return data
