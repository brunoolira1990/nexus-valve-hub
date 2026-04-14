from rest_framework import serializers

from .models import Certificado


class CertificadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificado
        fields = ('id', 'nf_saida', 'arquivo', 'gerado_em')
        read_only_fields = ('arquivo', 'gerado_em')
