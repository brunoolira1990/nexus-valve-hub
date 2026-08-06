from django.contrib import admin

from .models import ApuracaoAjusteManual, ApuracaoFiscal, ApuracaoItem, ApuracaoReforma, LogsAuditoriaApuracao


class ApuracaoItemInline(admin.TabularInline):
    model = ApuracaoItem
    extra = 0
    readonly_fields = (
        'lado',
        'origem_tipo',
        'chave',
        'cfop',
        'valor_icms',
        'valor_icms_st',
        'valor_pis',
        'valor_cofins',
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ApuracaoAjusteInline(admin.TabularInline):
    model = ApuracaoAjusteManual
    extra = 0
    readonly_fields = ('tipo', 'valor', 'motivo', 'usuario', 'criado_em')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class LogsInline(admin.TabularInline):
    model = LogsAuditoriaApuracao
    extra = 0
    readonly_fields = ('acao', 'usuario', 'timestamp', 'detalhe')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ApuracaoFiscal)
class ApuracaoFiscalAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'empresa',
        'data_inicio',
        'data_fim',
        'status',
        'saldo_icms',
        'fechado_em',
    )
    list_filter = ('status', 'empresa')
    search_fields = ('empresa__razao_social',)
    readonly_fields = (
        'criado_em',
        'atualizado_em',
        'fechado_em',
        'payload_snapshot',
        'totais_json',
        'filtros_json',
    )
    inlines = [ApuracaoItemInline, ApuracaoAjusteInline, LogsInline]


@admin.register(ApuracaoAjusteManual)
class ApuracaoAjusteManualAdmin(admin.ModelAdmin):
    list_display = ('id', 'apuracao', 'tipo', 'valor', 'usuario', 'criado_em')
    list_filter = ('tipo',)
    search_fields = ('motivo',)
    readonly_fields = ('apuracao', 'tipo', 'valor', 'motivo', 'usuario', 'criado_em')


@admin.register(ApuracaoReforma)
class ApuracaoReformaAdmin(admin.ModelAdmin):
    list_display = ('id', 'apuracao', 'cbs_credito', 'cbs_debito', 'ibs_credito', 'ibs_debito', 'is_valor')
    readonly_fields = (
        'apuracao',
        'cbs_credito',
        'cbs_debito',
        'ibs_credito',
        'ibs_debito',
        'is_valor',
        'detalhe_json',
        'atualizado_em',
    )


@admin.register(LogsAuditoriaApuracao)
class LogsAuditoriaApuracaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'apuracao', 'acao', 'usuario', 'timestamp')
    list_filter = ('acao',)
    readonly_fields = ('apuracao', 'usuario', 'acao', 'timestamp', 'detalhe')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
