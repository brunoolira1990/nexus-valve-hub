"""Serializers de leitura — consultas externas."""

from rest_framework import serializers

from apps.comercial.integracoes_credito.permissions import (
    usuario_pode_ver_buro,
    usuario_pode_ver_cadastral,
)
from apps.comercial.models import ConsultaExternaAnaliseFinanceira


class ConsultaExternaAnaliseFinanceiraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultaExternaAnaliseFinanceira
        fields = (
            'id',
            'analise_financeira',
            'tipo',
            'provider',
            'produto',
            'status',
            'solicitada_em',
            'iniciada_em',
            'concluida_em',
            'expira_em',
            'cnpj_mascarado',
            'resultado_normalizado',
            'erro_sanitizado',
            'protocolo_mascarado',
            'custo_consulta',
            'criada_em',
            'atualizada_em',
        )
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if instance.tipo == ConsultaExternaAnaliseFinanceira.Tipo.CADASTRAL:
            if not usuario_pode_ver_cadastral(user):
                data['resultado_normalizado'] = {}
                data.pop('erro_sanitizado', None)
        elif instance.tipo == ConsultaExternaAnaliseFinanceira.Tipo.BURO:
            if not usuario_pode_ver_buro(user):
                data['resultado_normalizado'] = {}
                data['status'] = instance.status
                data.pop('erro_sanitizado', None)
                data['provider'] = ''
                data['produto'] = ''
        # Nunca expor hash completo como superfície operacional desnecessária
        data.pop('hash_requisicao', None)
        return data
