from rest_framework import serializers

from .models import RegraFiscal


class RegraFiscalSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegraFiscal
        fields = '__all__'
