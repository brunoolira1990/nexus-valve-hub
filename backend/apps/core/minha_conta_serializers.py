"""Serializers Minha conta — ERP 4.0.14.9.4."""

from rest_framework import serializers

from apps.cadastros.colaborador_senha import email_operacional_valido


class MinhaContaUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=False)
    telefone = serializers.CharField(required=False, allow_blank=True, max_length=32)

    def validate_email(self, value):
        if not email_operacional_valido(value):
            raise serializers.ValidationError('Informe um e-mail válido.')
        return value.strip()

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Informe ao menos um campo para atualizar.')
        return attrs
