"""RBAC do ajuste manual de classificação fiscal.

Produção futura pode conceder ``fiscal.can_adjust_fiscal_classification`` a
perfis ANALISTA_FISCAL/SUPERVISOR; hoje o acesso vem dos grupos operacionais.
"""

from rest_framework.permissions import BasePermission

PERM_AJUSTAR_CLASSIFICACAO_FISCAL = 'fiscal.can_adjust_fiscal_classification'
GRUPOS_AJUSTE_CLASSIFICACAO_FISCAL = ('admin', 'administrador', 'fiscal')


def usuario_pode_ajustar_classificacao_fiscal(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.has_perm(PERM_AJUSTAR_CLASSIFICACAO_FISCAL):
        return True
    return user.groups.filter(name__in=GRUPOS_AJUSTE_CLASSIFICACAO_FISCAL).exists()


class PodeAjustarClassificacaoFiscal(BasePermission):
    message = 'Você não tem permissão para ajustar a classificação fiscal.'

    def has_permission(self, request, view):
        return usuario_pode_ajustar_classificacao_fiscal(request.user)
