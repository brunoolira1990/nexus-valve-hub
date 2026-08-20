from rest_framework import serializers

from apps.cadastros.models import Cliente, Colaborador
from apps.cadastros.utils import normalizar_cnpj

from .models import Atividade, HistoricoLead, Lead, Oportunidade


class AtividadeSerializer(serializers.ModelSerializer):
    responsavel_id = serializers.PrimaryKeyRelatedField(
        source='responsavel',
        queryset=Colaborador.objects.filter(ativo=True),
        allow_null=True,
        required=False,
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        source='lead',
        queryset=Lead.objects.all(),
        allow_null=True,
        required=False,
    )
    oportunidade_id = serializers.PrimaryKeyRelatedField(
        source='oportunidade',
        queryset=Oportunidade.objects.select_related('lead').all(),
        allow_null=True,
        required=False,
    )
    responsavel_nome = serializers.SerializerMethodField()
    lead_nome = serializers.SerializerMethodField()
    oportunidade_titulo = serializers.SerializerMethodField()

    class Meta:
        model = Atividade
        fields = (
            'id',
            'titulo',
            'tipo',
            'status',
            'lead_id',
            'lead_nome',
            'oportunidade_id',
            'oportunidade_titulo',
            'responsavel_id',
            'responsavel_nome',
            'descricao',
            'agendada_para',
            'concluida_em',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = (
            'id',
            'lead_nome',
            'oportunidade_titulo',
            'responsavel_nome',
            'criado_em',
            'atualizado_em',
        )

    def validate(self, attrs):
        instance = self.instance
        lead = attrs.get('lead', instance.lead if instance else None)
        oportunidade = attrs.get('oportunidade', instance.oportunidade if instance else None)
        status = attrs.get('status', instance.status if instance else Atividade.Status.PENDENTE)
        titulo = attrs.get('titulo', instance.titulo if instance else '')
        errors = {}
        if not str(titulo or '').strip():
            errors['titulo'] = 'Informe o título da atividade.'
        if not lead and not oportunidade:
            errors['lead_id'] = 'Informe um lead ou uma oportunidade para a atividade.'
        if lead and oportunidade and oportunidade.lead_id and oportunidade.lead_id != lead.id:
            errors['oportunidade_id'] = 'A oportunidade deve pertencer ao lead informado.'
        if errors:
            raise serializers.ValidationError(errors)
        if status == Atividade.Status.CONCLUIDA and not attrs.get('concluida_em') and not getattr(instance, 'concluida_em', None):
            from django.utils import timezone

            attrs['concluida_em'] = timezone.now()
        if status != Atividade.Status.CONCLUIDA and 'status' in attrs:
            attrs['concluida_em'] = None
        return attrs

    def get_responsavel_nome(self, obj):
        return obj.responsavel.nome if obj.responsavel else ''

    def get_lead_nome(self, obj):
        return obj.lead.nome if obj.lead else ''

    def get_oportunidade_titulo(self, obj):
        return obj.oportunidade.titulo if obj.oportunidade else ''


class HistoricoLeadSerializer(serializers.ModelSerializer):
    lead_id = serializers.IntegerField(source='lead.id', read_only=True)
    lead_nome = serializers.SerializerMethodField()
    atividade_id = serializers.IntegerField(source='atividade.id', read_only=True)
    realizado_por_id = serializers.IntegerField(source='realizado_por.id', read_only=True)
    realizado_por_nome = serializers.SerializerMethodField()

    class Meta:
        model = HistoricoLead
        fields = (
            'id',
            'lead_id',
            'lead_nome',
            'evento',
            'titulo',
            'descricao',
            'atividade_id',
            'realizado_por_id',
            'realizado_por_nome',
            'dados',
            'criado_em',
        )
        read_only_fields = fields

    def get_lead_nome(self, obj):
        return obj.lead.nome if obj.lead else ''

    def get_realizado_por_nome(self, obj):
        return obj.realizado_por.nome if obj.realizado_por else ''


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
            'external_id',
            'nome',
            'cnpj',
            'nome_contato',
            'email',
            'telefone',
            'cidade',
            'uf',
            'produto_interesse',
            'pagina_origem',
            'utm_source',
            'utm_medium',
            'utm_campaign',
            'utm_content',
            'utm_term',
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
            'external_id',
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


class SiteLeadCaptureSerializer(serializers.Serializer):
    external_id = serializers.CharField(max_length=64)
    nome = serializers.CharField(max_length=160)
    empresa = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField()
    telefone = serializers.CharField(max_length=64, required=False, allow_blank=True)
    assunto = serializers.CharField(max_length=255)
    mensagem = serializers.CharField(max_length=10000, min_length=10)
    produto_interesse = serializers.CharField(max_length=255, required=False, allow_blank=True)
    pagina_origem = serializers.CharField(max_length=500, required=False, allow_blank=True)
    utm_source = serializers.CharField(max_length=120, required=False, allow_blank=True)
    utm_medium = serializers.CharField(max_length=120, required=False, allow_blank=True)
    utm_campaign = serializers.CharField(max_length=255, required=False, allow_blank=True)
    utm_content = serializers.CharField(max_length=255, required=False, allow_blank=True)
    utm_term = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        for field in ('external_id', 'nome', 'assunto', 'mensagem'):
            attrs[field] = attrs[field].strip()
        if not attrs['external_id']:
            raise serializers.ValidationError({'external_id': 'Identificador da submissão é obrigatório.'})
        if not attrs['nome']:
            raise serializers.ValidationError({'nome': 'Nome do contato é obrigatório.'})
        if not attrs['assunto']:
            raise serializers.ValidationError({'assunto': 'Assunto é obrigatório.'})
        if len(attrs['mensagem']) < 10:
            raise serializers.ValidationError({'mensagem': 'Mensagem deve ter pelo menos 10 caracteres.'})
        return attrs
