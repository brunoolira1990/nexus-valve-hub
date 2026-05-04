from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.comercial.payment_terms import parse_payment_condition
from apps.text_normalize import normalize_operational_fields

from .models import Cliente, Empresa, Fornecedor, Transportadora


class EmpresaSerializer(serializers.ModelSerializer):
    empresa_pai_id = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(),
        source='empresa_pai',
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Empresa
        exclude = ('empresa_pai',)
        extra_kwargs = {
            'senha_certificado': {'write_only': True, 'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        normalize_operational_fields(
            attrs,
            {
                'razao_social',
                'nome_fantasia',
                'ie',
                'im',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'telefone',
            },
        )
        pai = attrs.get('empresa_pai')
        pk = self.instance.pk if self.instance else None
        if pk and pai and pai.pk == pk:
            raise serializers.ValidationError(
                {'empresa_pai_id': 'A empresa não pode ser filial de si mesma.'}
            )
        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if getattr(e, 'message_dict', None) else e.messages
            ) from e

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if getattr(e, 'message_dict', None) else e.messages
            ) from e

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['empresa_pai_id'] = instance.empresa_pai_id
        request = self.context.get('request')
        if request:
            if instance.certificado_arquivo:
                data['certificado_arquivo'] = request.build_absolute_uri(
                    instance.certificado_arquivo.url
                )
            if instance.logotipo:
                data['logotipo'] = request.build_absolute_uri(instance.logotipo.url)
        return data


class ClienteSerializer(serializers.ModelSerializer):
    transportadora_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora_padrao',
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Cliente
        exclude = ('transportadora_padrao',)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'razao_social',
                'nome_fantasia',
                'ie',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'contato_responsavel',
                'observacoes',
                'inscricao_municipal',
                'suframa',
                'vendedor_padrao',
                'banco',
                'agencia',
                'conta',
                'tipo_conta',
                'cnae',
                'regime_tributario',
                'integracao_texto',
                'condicao_pagamento_texto',
            },
        )
        texto = attrs.get(
            'condicao_pagamento_texto',
            self.instance.condicao_pagamento_texto if self.instance else '',
        )
        dias = parse_payment_condition(texto)
        attrs['dias_parcelas'] = dias
        attrs['quantidade_parcelas'] = len(dias)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['transportadora_padrao_id'] = instance.transportadora_padrao_id
        return data


class FornecedorSerializer(serializers.ModelSerializer):
    transportadora_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora_padrao',
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Fornecedor
        exclude = ('transportadora_padrao',)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'razao_social',
                'nome_fantasia',
                'ie',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'contato_responsavel',
                'observacoes',
                'inscricao_municipal',
                'suframa',
                'banco',
                'agencia',
                'conta',
                'tipo_conta',
                'cnae',
                'regime_tributario',
                'integracao_texto',
                'condicao_pagamento_texto',
            },
        )
        texto = attrs.get(
            'condicao_pagamento_texto',
            self.instance.condicao_pagamento_texto if self.instance else '',
        )
        dias = parse_payment_condition(texto)
        attrs['dias_parcelas'] = dias
        attrs['quantidade_parcelas'] = len(dias)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['transportadora_padrao_id'] = instance.transportadora_padrao_id
        return data


class TransportadoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transportadora
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'razao_social',
                'nome_fantasia',
                'ie',
                'inscricao_municipal',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'contato',
                'placa_padrao',
                'uf_placa',
                'observacoes',
                'ddd',
                'suframa',
                'banco',
                'agencia',
                'conta',
                'tipo_conta',
                'cnae',
                'regime_tributario',
                'integracao_texto',
            },
        )
        return attrs
