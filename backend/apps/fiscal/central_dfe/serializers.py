"""Serializers — ações da Central DF-e."""

from rest_framework import serializers


class ArmazenarXmlCentralSerializer(serializers.Serializer):
    empresa_id = serializers.IntegerField()
    confirmacao_explicita = serializers.BooleanField()
    chave_acesso = serializers.CharField(required=False, allow_blank=True, max_length=44)
