from rest_framework.permissions import BasePermission


PERM_VIEW = 'comercial.view_analisefinanceiraproposta'
PERM_SOLICITAR = 'comercial.solicitar_analisefinanceiraproposta'
PERM_DECIDIR = 'comercial.decidir_analisefinanceiraproposta'
PERM_DETALHE = 'comercial.ver_detalhe_financeiro_analisefinanceiraproposta'


def usuario_pode_ver_analise(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return (
        user.has_perm(PERM_VIEW)
        or user.has_perm(PERM_SOLICITAR)
        or user.has_perm(PERM_DECIDIR)
        or user.has_perm(PERM_DETALHE)
    )


def usuario_pode_solicitar_analise(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(PERM_SOLICITAR)


def usuario_pode_decidir_analise(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(PERM_DECIDIR)


def usuario_pode_ver_detalhe_financeiro(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    # Decisão e detalhe: quem decide precisa ver indicadores agregados.
    return user.has_perm(PERM_DETALHE) or user.has_perm(PERM_DECIDIR)


class PodeSolicitarAnaliseFinanceiraProposta(BasePermission):
    message = 'Você não tem permissão para solicitar análise financeira.'

    def has_permission(self, request, view):
        return usuario_pode_solicitar_analise(request.user)


class PodeVerAnaliseFinanceiraProposta(BasePermission):
    message = 'Você não tem permissão para visualizar análises financeiras.'

    def has_permission(self, request, view):
        return usuario_pode_ver_analise(request.user)


class PodeDecidirAnaliseFinanceiraProposta(BasePermission):
    message = 'Você não tem permissão para decidir análises financeiras.'

    def has_permission(self, request, view):
        return usuario_pode_decidir_analise(request.user)
