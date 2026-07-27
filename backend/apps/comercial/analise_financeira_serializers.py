from rest_framework import serializers

from apps.comercial.models import AnaliseFinanceiraProposta, AnaliseFinanceiraPropostaEvento


class AnaliseFinanceiraEventoSerializer(serializers.ModelSerializer):
    ator_nome = serializers.SerializerMethodField()

    class Meta:
        model = AnaliseFinanceiraPropostaEvento
        fields = ('id', 'tipo', 'ator', 'ator_nome', 'criado_em', 'dados')
        read_only_fields = fields

    def get_ator_nome(self, obj):
        if not obj.ator_id:
            return None
        return (obj.ator.get_full_name() or '').strip() or obj.ator.get_username()


class AnaliseFinanceiraPropostaSerializer(serializers.ModelSerializer):
    solicitada_por_nome = serializers.SerializerMethodField()
    decidida_por_nome = serializers.SerializerMethodField()
    proposta_numero = serializers.CharField(source='proposta.numero', read_only=True)
    cliente_nome = serializers.CharField(source='cliente.razao_social', read_only=True)
    eventos = AnaliseFinanceiraEventoSerializer(many=True, read_only=True)

    class Meta:
        model = AnaliseFinanceiraProposta
        fields = (
            'id',
            'proposta',
            'proposta_numero',
            'cliente',
            'cliente_nome',
            'status',
            'versao',
            'solicitada_por',
            'solicitada_por_nome',
            'solicitada_em',
            'iniciada_por',
            'iniciada_em',
            'decidida_por',
            'decidida_por_nome',
            'decidida_em',
            'observacao_vendedor',
            'justificativa_decisao',
            'valor_solicitado',
            'valor_maximo_aprovado',
            'valida_ate',
            'snapshot_proposta',
            'snapshot_indicadores',
            'condicao_solicitada',
            'condicao_aprovada',
            'substituida_por',
            'criada_em',
            'atualizada_em',
            'eventos',
        )
        read_only_fields = fields

    def get_solicitada_por_nome(self, obj):
        if not obj.solicitada_por_id:
            return None
        return (obj.solicitada_por.get_full_name() or '').strip() or obj.solicitada_por.get_username()

    def get_decidida_por_nome(self, obj):
        if not obj.decidida_por_id:
            return None
        return (obj.decidida_por.get_full_name() or '').strip() or obj.decidida_por.get_username()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        from apps.comercial.analise_financeira_permissions import (
            usuario_pode_decidir_analise,
            usuario_pode_ver_detalhe_financeiro,
        )

        data['permissoes'] = {
            'pode_decidir': usuario_pode_decidir_analise(user),
            'pode_ver_detalhe_financeiro': usuario_pode_ver_detalhe_financeiro(user),
        }
        if not usuario_pode_ver_detalhe_financeiro(user):
            # Resumo comercial: sem saldos/exposição detalhados.
            ind = dict(data.get('snapshot_indicadores') or {})
            qualidade = ind.get('qualidade') or {}
            data['snapshot_indicadores'] = {
                'schema_versao': ind.get('schema_versao'),
                'qualidade_dados': qualidade.get('status') or ind.get('qualidade_dados'),
                'qualidade': {
                    'status': qualidade.get('status') or ind.get('qualidade_dados'),
                    'mensagem': qualidade.get('mensagem'),
                }
                if qualidade or ind.get('qualidade_dados')
                else None,
                'dados_indisponiveis': ind.get('dados_indisponiveis'),
                'data_corte': ind.get('data_corte'),
                'resumo_restrito': True,
            }
            data['snapshot_proposta'] = {
                'proposta_id': (data.get('snapshot_proposta') or {}).get('proposta_id'),
                'numero': (data.get('snapshot_proposta') or {}).get('numero'),
                'valor_total': (data.get('snapshot_proposta') or {}).get('valor_total'),
                'condicao': (data.get('snapshot_proposta') or {}).get('condicao'),
                'vendedor': (data.get('snapshot_proposta') or {}).get('vendedor'),
                'data_proposta': (data.get('snapshot_proposta') or {}).get('data_proposta'),
            }
        return data


class AnaliseFinanceiraListSerializer(AnaliseFinanceiraPropostaSerializer):
    class Meta(AnaliseFinanceiraPropostaSerializer.Meta):
        fields = (
            'id',
            'proposta',
            'proposta_numero',
            'cliente',
            'cliente_nome',
            'status',
            'versao',
            'solicitada_em',
            'valor_solicitado',
            'condicao_solicitada',
            'condicao_aprovada',
            'valida_ate',
            'solicitada_por_nome',
        )
