"""Permissões das consultas externas B2/B3."""

from rest_framework.permissions import BasePermission

from apps.comercial.analise_financeira_permissions import usuario_pode_ver_analise

PERM_SOLICITAR_CADASTRAL = 'comercial.solicitar_consulta_cadastral_analise'
PERM_VER_CADASTRAL = 'comercial.ver_resultado_cadastral_analise'
PERM_SOLICITAR_BURO = 'comercial.solicitar_consulta_buro_analise'
PERM_VER_BURO = 'comercial.ver_resultado_buro_analise'
PERM_VIEW_CONSULTA = 'comercial.view_consultaexternaanalisefinanceira'


def _auth(user) -> bool:
    return bool(user and user.is_authenticated)


def usuario_pode_solicitar_cadastral(user) -> bool:
    if not _auth(user):
        return False
    if user.is_superuser:
        return True
    return user.has_perm(PERM_SOLICITAR_CADASTRAL)


def usuario_pode_ver_cadastral(user) -> bool:
    if not _auth(user):
        return False
    if user.is_superuser:
        return True
    return user.has_perm(PERM_VER_CADASTRAL) or user.has_perm(PERM_SOLICITAR_CADASTRAL)


def usuario_pode_solicitar_buro(user) -> bool:
    if not _auth(user):
        return False
    if user.is_superuser:
        return True
    return user.has_perm(PERM_SOLICITAR_BURO)


def usuario_pode_ver_buro(user) -> bool:
    if not _auth(user):
        return False
    if user.is_superuser:
        return True
    # Comercial não deve ver resultado completo de birô só com view da análise.
    return user.has_perm(PERM_VER_BURO) or user.has_perm(PERM_SOLICITAR_BURO)


def usuario_pode_ver_capability(user) -> bool:
    """Capability do dossiê: mesma base de visualização da análise."""
    return usuario_pode_ver_analise(user)


class PodeVerCapabilityIntegracoes(BasePermission):
    message = 'Você não tem permissão para visualizar a capacidade das integrações.'

    def has_permission(self, request, view):
        return usuario_pode_ver_capability(request.user)


class PodeSolicitarConsultaCadastral(BasePermission):
    message = 'Você não tem permissão para solicitar consulta cadastral.'

    def has_permission(self, request, view):
        return usuario_pode_solicitar_cadastral(request.user)


class PodeSolicitarConsultaBuro(BasePermission):
    message = 'Você não tem permissão para solicitar consulta de birô.'

    def has_permission(self, request, view):
        return usuario_pode_solicitar_buro(request.user)


class PodeListarConsultasExternas(BasePermission):
    message = 'Você não tem permissão para listar consultas externas.'

    def has_permission(self, request, view):
        # Exige ao menos view da análise; filtragem por tipo ocorre na view.
        return usuario_pode_ver_analise(request.user)
