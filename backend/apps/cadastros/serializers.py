from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Cliente, CondicaoPagamento, Empresa, Fornecedor, Transportadora


class CondicaoPagamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CondicaoPagamento
        fields = ('id', 'descricao', 'dias_parcelas', 'ativo')

    def validate_dias_parcelas(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('Informe uma lista de inteiros (dias por parcela).')
        for d in value:
            if not isinstance(d, int) or d < 0:
                raise serializers.ValidationError('Cada prazo deve ser um número inteiro ≥ 0.')
        return value


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
    condicao_pagamento_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=CondicaoPagamento.objects.all(),
        source='condicao_pagamento_padrao',
        allow_null=True,
        required=False,
    )
    transportadora_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora_padrao',
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Cliente
        exclude = ('condicao_pagamento_padrao', 'transportadora_padrao')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['condicao_pagamento_padrao_id'] = instance.condicao_pagamento_padrao_id
        data['transportadora_padrao_id'] = instance.transportadora_padrao_id
        return data


class FornecedorSerializer(serializers.ModelSerializer):
    condicao_pagamento_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=CondicaoPagamento.objects.all(),
        source='condicao_pagamento_padrao',
        allow_null=True,
        required=False,
    )
    transportadora_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora_padrao',
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Fornecedor
        exclude = ('condicao_pagamento_padrao', 'transportadora_padrao')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['condicao_pagamento_padrao_id'] = instance.condicao_pagamento_padrao_id
        data['transportadora_padrao_id'] = instance.transportadora_padrao_id
        return data


class TransportadoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transportadora
        fields = '__all__'
