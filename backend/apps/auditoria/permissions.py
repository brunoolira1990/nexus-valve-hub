from rest_framework.permissions import BasePermission


class PodeVisualizarAuditoria(BasePermission):
    """Exige autenticação + permissão model view_registroauditoria."""

    message = 'Você não tem permissão para visualizar o histórico de auditoria.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm('auditoria.view_registroauditoria')
