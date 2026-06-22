"""Serializers — ações da Central DF-e."""

from rest_framework import serializers


class ArmazenarXmlCentralSerializer(serializers.Serializer):
    empresa_id = serializers.IntegerField()
    confirmacao_explicita = serializers.BooleanField()
