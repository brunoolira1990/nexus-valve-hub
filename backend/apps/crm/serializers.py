from rest_framework import serializers

from apps.cadastros.models import Cliente, Colaborador
from apps.cadastros.utils import normalizar_cnpj

from .models import Lead, Oportunidade


class LeadSerializer(serializers.ModelSerializer):
    responsavel_id = serializers.PrimaryKeyRelatedField(
        source='responsavel',
        queryset=Colaborador.objects.filter(ativo=True),
        allow_null=True,
        required=False,
    )
    cliente_id = serializers.PrimaryKeyRelatedField(
        source='cliente',
        queryset=Cliente.objects.all(),
        allow_null=True,
        required=False,
    )
    responsavel_nome = serializers.SerializerMethodField()
    cliente_nome = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = (
            'id',
            'nome',
            'cnpj',
            'nome_contato',
            'email',
            'telefone',
            'cidade',
            'uf',
            'origem',
            'status',
            'responsavel_id',
            'responsavel_nome',
            'cliente_id',
            'cliente_nome',
            'observacoes',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = (
            'id',
            'responsavel_nome',
            'cliente_nome',
            'criado_em',
            'atualizado_em',
        )

    def validate_cnpj(self, value):
        return normalizar_cnpj(value or '')

    def validate_uf(self, value):
        return (value or '').strip().upper()

    def get_responsavel_nome(self, obj):
        return obj.responsavel.nome if obj.responsavel else ''

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social if obj.cliente else ''


class OportunidadeSerializer(serializers.ModelSerializer):
    responsavel_id = serializers.PrimaryKeyRelatedField(
        source='responsavel',
        queryset=Colaborador.objects.filter(ativo=True),
        allow_null=True,
        required=False,
    )
    cliente_id = serializers.PrimaryKeyRelatedField(
        source='cliente',
        queryset=Cliente.objects.all(),
        allow_null=True,
        required=False,
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        source='lead',
        queryset=Lead.objects.all(),
        allow_null=True,
        required=False,
    )
    responsavel_nome = serializers.SerializerMethodField()
    cliente_nome = serializers.SerializerMethodField()
    lead_nome = serializers.SerializerMethodField()

    class Meta:
        model = Oportunidade
        fields = (
            'id',
            'titulo',
            'status',
            'etapa',
            'lead_id',
            'lead_nome',
            'cliente_id',
            'cliente_nome',
            'responsavel_id',
            'responsavel_nome',
            'valor_estimado',
            'probabilidade',
            'previsao_fechamento',
            'proxima_acao',
            'motivo_perda',
            'observacoes',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = (
            'id',
            'lead_nome',
            'cliente_nome',
            'responsavel_nome',
            'criado_em',
            'atualizado_em',
        )

    def validate(self, attrs):
        instance = self.instance
        lead = attrs.get('lead', instance.lead if instance else None)
        cliente = attrs.get('cliente', instance.cliente if instance else None)
        status = attrs.get('status', instance.status if instance else Oportunidade.Status.ABERTA)
        motivo_perda = attrs.get('motivo_perda', instance.motivo_perda if instance else '')
        errors = {}
        if not lead and not cliente:
            errors['cliente_id'] = 'Informe um cliente ou um lead para a oportunidade.'
        if status == Oportunidade.Status.PERDIDA and not (motivo_perda or '').strip():
            errors['motivo_perda'] = 'Informe o motivo da perda.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_responsavel_nome(self, obj):
        return obj.responsavel.nome if obj.responsavel else ''

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social if obj.cliente else ''

    def get_lead_nome(self, obj):
        return obj.lead.nome if obj.lead else ''
