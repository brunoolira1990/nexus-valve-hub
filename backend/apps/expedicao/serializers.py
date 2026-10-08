from __future__ import annotations

from rest_framework import serializers

from apps.expedicao.models import Expedicao, StatusExpedicao, TipoOperacaoExpedicao
from apps.text_normalize import normalize_operational_fields


class ExpedicaoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.razao_social', read_only=True)
    fornecedor_nome = serializers.CharField(source='fornecedor.razao_social', read_only=True)
    transportadora_nome = serializers.CharField(source='transportadora.razao_social', read_only=True)
    pedido_venda_numero = serializers.CharField(source='pedido_venda.numero', read_only=True)
    pedido_compra_numero = serializers.CharField(source='pedido_compra.numero', read_only=True)
    faturamento_numero = serializers.CharField(source='faturamento.numero_faturamento', read_only=True)
    nfe_saida_numero = serializers.SerializerMethodField()
    alocacao_atendimento_id_display = serializers.IntegerField(source='alocacao_atendimento_id', read_only=True)
    nfe_entrada_numero = serializers.CharField(source='nfe_entrada.numero', read_only=True)
    cte_entrada_numero = serializers.CharField(source='cte_entrada.numero', read_only=True)
    tipo_operacao_label = serializers.CharField(source='get_tipo_operacao_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    criado_por_nome = serializers.SerializerMethodField()

    class Meta:
        model = Expedicao
        fields = [
            'id',
            'codigo',
            'tipo_operacao',
            'tipo_operacao_label',
            'status',
            'status_label',
            'cliente',
            'cliente_nome',
            'fornecedor',
            'fornecedor_nome',
            'transportadora',
            'transportadora_nome',
            'motorista_nome',
            'motorista_documento',
            'telefone_motorista',
            'placa_veiculo',
            'volumes',
            'peso_bruto',
            'peso_liquido',
            'data_prevista_retirada',
            'data_prevista_entrega',
            'data_hora_retirada_real',
            'data_hora_entrega_real',
            'observacoes',
            'ocorrencia_descricao',
            'pedido_venda',
            'pedido_venda_numero',
            'pedido_compra',
            'pedido_compra_numero',
            'faturamento',
            'faturamento_numero',
            'nfe_saida',
            'nfe_saida_numero',
            'alocacao_atendimento',
            'alocacao_atendimento_id_display',
            'nfe_entrada',
            'nfe_entrada_numero',
            'cte_entrada',
            'cte_entrada_numero',
            'criado_por',
            'criado_por_nome',
            'atualizado_por',
            'criado_em',
            'atualizado_em',
        ]
        read_only_fields = [
            'id',
            'codigo',
            'criado_por',
            'atualizado_por',
            'criado_em',
            'atualizado_em',
        ]

    def get_nfe_saida_numero(self, obj: Expedicao) -> str:
        if not obj.nfe_saida_id:
            return ''
        nf = obj.nfe_saida
        return str(getattr(nf, 'numero_nfe', None) or getattr(nf, 'numero', '') or nf.pk)

    def get_criado_por_nome(self, obj: Expedicao) -> str:
        u = obj.criado_por
        if not u:
            return ''
        return (u.get_full_name() or u.username or '').strip()

    def validate(self, attrs):
        normalize_operational_fields(attrs, {'tipo_operacao', 'status', 'placa_veiculo'})
        status = attrs.get('status')
        if status and status not in StatusExpedicao.values:
            raise serializers.ValidationError({'status': 'Status inválido.'})
        tipo = attrs.get('tipo_operacao')
        if tipo and tipo not in TipoOperacaoExpedicao.values:
            raise serializers.ValidationError({'tipo_operacao': 'Tipo de operação inválido.'})
        return attrs


class ExpedicaoAlterarStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=StatusExpedicao.choices)
    ocorrencia_descricao = serializers.CharField(required=False, allow_blank=True, default='')


class ExpedicaoCancelarSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=False, allow_blank=True, default='')
