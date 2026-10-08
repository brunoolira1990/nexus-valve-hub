from django.contrib import admin

from apps.auditoria.models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'app_label', 'model_name', 'object_id', 'operacao', 'ator', 'criado_em')
    list_filter = ('operacao', 'app_label', 'model_name')
    search_fields = ('object_id',)
    readonly_fields = (
        'app_label',
        'model_name',
        'object_id',
        'operacao',
        'alteracoes',
        'ator',
        'criado_em',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
