from decimal import Decimal

from rest_framework import serializers

from .models import ApuracaoAjusteManual, ApuracaoFiscal, ApuracaoItem, ApuracaoReforma, LogsAuditoriaApuracao
from .services.ajustes import impacto_ajuste, resumo_ajustes


class LogsAuditoriaApuracaoSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source='usuario.username', read_only=True, default=None)

    class Meta:
        model = LogsAuditoriaApuracao
        fields = (
            'id',
            'acao',
            'timestamp',
            'detalhe',
            'usuario',
            'usuario_username',
        )
        read_only_fields = fields


class ApuracaoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApuracaoItem
        fields = (
            'id',
            'lado',
            'origem_tipo',
            'origem_documento_id',
            'origem_item_id',
            'chave',
            'cfop',
            'ncm',
            'cst_icms',
            'cst_pis',
            'cst_cofins',
            'quantidade_itens',
            'valor_produtos',
            'base_icms',
            'valor_icms',
            'base_icms_st',
            'valor_icms_st',
            'valor_fcp_st',
            'valor_icms_uf_dest',
            'base_ipi',
            'valor_ipi',
            'base_pis',
            'valor_pis',
            'base_cofins',
            'valor_cofins',
            'detalhe_json',
        )
        read_only_fields = fields


class ApuracaoAjusteManualSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source='usuario.username', read_only=True, default=None)
    impacto = serializers.SerializerMethodField()

    class Meta:
        model = ApuracaoAjusteManual
        fields = (
            'id',
            'apuracao',
            'tipo',
            'valor',
            'motivo',
            'usuario',
            'usuario_username',
            'criado_em',
            'impacto',
        )
        read_only_fields = (
            'id',
            'apuracao',
            'usuario',
            'usuario_username',
            'criado_em',
            'impacto',
        )

    def get_impacto(self, obj: ApuracaoAjusteManual):
        try:
            return float(impacto_ajuste(obj.tipo, obj.valor))
        except Exception:
            return 0.0


class CriarAjusteManualSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=['DEBITO', 'CREDITO', 'ESTORNO'])
    valor = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal('0.01'))
    motivo = serializers.CharField(min_length=5, max_length=500)


class ApuracaoReformaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApuracaoReforma
        fields = (
            'id',
            'apuracao',
            'cbs_credito',
            'cbs_debito',
            'ibs_credito',
            'ibs_debito',
            'is_valor',
            'detalhe_json',
            'atualizado_em',
        )
        read_only_fields = fields


class ApuracaoFiscalSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.CharField(source='empresa.razao_social', read_only=True)
    criado_por_username = serializers.CharField(
        source='criado_por.username', read_only=True, default=None
    )
    fechado_por_username = serializers.CharField(
        source='fechado_por.username', read_only=True, default=None
    )
    quantidade_itens = serializers.IntegerField(source='itens.count', read_only=True)
    logs = LogsAuditoriaApuracaoSerializer(source='logs_auditoria', many=True, read_only=True)
    ajustes_liquido = serializers.SerializerMethodField()
    saldo_final = serializers.SerializerMethodField()
    quantidade_ajustes = serializers.SerializerMethodField()
    reforma = ApuracaoReformaSerializer(read_only=True)

    class Meta:
        model = ApuracaoFiscal
        fields = (
            'id',
            'empresa',
            'empresa_nome',
            'data_inicio',
            'data_fim',
            'status',
            'tipo',
            'fonte',
            'valor_entradas',
            'valor_saidas',
            'icms_debito',
            'icms_credito',
            'icms_st_debito',
            'difal_valor',
            'ipi_debito',
            'ipi_credito',
            'pis_debito',
            'pis_credito',
            'cofins_debito',
            'cofins_credito',
            'saldo_icms',
            'ajustes_liquido',
            'saldo_final',
            'quantidade_ajustes',
            'totais_json',
            'filtros_json',
            'versao_api_apuracao',
            'criado_em',
            'atualizado_em',
            'criado_por',
            'criado_por_username',
            'fechado_em',
            'fechado_por',
            'fechado_por_username',
            'quantidade_itens',
            'logs',
            'reforma',
        )
        read_only_fields = fields

    def _resumo(self, obj: ApuracaoFiscal):
        cache = getattr(self, '_resumo_cache', None)
        if cache is None:
            cache = {}
            self._resumo_cache = cache
        if obj.pk not in cache:
            cache[obj.pk] = resumo_ajustes(obj)
        return cache[obj.pk]

    def get_ajustes_liquido(self, obj: ApuracaoFiscal):
        return float(self._resumo(obj)['ajustes_liquido'])

    def get_saldo_final(self, obj: ApuracaoFiscal):
        return float(self._resumo(obj)['saldo_final'])

    def get_quantidade_ajustes(self, obj: ApuracaoFiscal):
        return int(self._resumo(obj)['quantidade'])


class ApuracaoFiscalListSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.CharField(source='empresa.razao_social', read_only=True)
    saldo_final = serializers.SerializerMethodField()

    class Meta:
        model = ApuracaoFiscal
        fields = (
            'id',
            'empresa',
            'empresa_nome',
            'data_inicio',
            'data_fim',
            'status',
            'tipo',
            'fonte',
            'valor_entradas',
            'valor_saidas',
            'icms_st_debito',
            'pis_credito',
            'cofins_credito',
            'saldo_icms',
            'saldo_final',
            'criado_em',
            'fechado_em',
            'versao_api_apuracao',
        )
        read_only_fields = fields

    def get_saldo_final(self, obj: ApuracaoFiscal):
        return float(resumo_ajustes(obj)['saldo_final'])


class CriarRascunhoSerializer(serializers.Serializer):
    empresa_id = serializers.IntegerField()
    data_inicio = serializers.DateField()
    data_fim = serializers.DateField()
    tipo = serializers.ChoiceField(
        choices=['ENTRADA', 'SAIDA', 'AMBOS'],
        default='AMBOS',
        required=False,
    )
    fonte = serializers.ChoiceField(
        choices=['TODOS', 'OPERACIONAIS', 'HISTORICOS'],
        default='TODOS',
        required=False,
    )
    status = serializers.CharField(required=False, allow_blank=True, default='')
    cliente_id = serializers.IntegerField(required=False, allow_null=True)
    fornecedor_id = serializers.IntegerField(required=False, allow_null=True)
    cfop = serializers.CharField(required=False, allow_blank=True, default='')
    ncm = serializers.CharField(required=False, allow_blank=True, default='')
    modelo_documento = serializers.CharField(required=False, allow_blank=True, default='')
    incluir_canceladas = serializers.BooleanField(required=False, default=False)


class ReabrirSerializer(serializers.Serializer):
    motivo = serializers.CharField(min_length=5, max_length=500)
