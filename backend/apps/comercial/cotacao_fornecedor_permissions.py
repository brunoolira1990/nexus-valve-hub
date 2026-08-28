from rest_framework.permissions import BasePermission


PERM_VIEW = 'comercial.view_cotacaofornecedor'
PERM_ADD = 'comercial.add_cotacaofornecedor'
PERM_CHANGE = 'comercial.change_cotacaofornecedor'
PERM_RESPONSE = 'comercial.registrar_resposta_cotacaofornecedor'
PERM_REFERENCE = 'comercial.selecionar_referencia_cotacaofornecedor'
PERM_CANCEL = 'comercial.cancel_cotacaofornecedor'


def _can(user, perm: str) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or user.has_perm(perm)))


class PodeVerCotacaoFornecedor(BasePermission):
    message = 'Você não tem permissão para visualizar cotações de fornecedores.'

    def has_permission(self, request, view):
        return _can(request.user, PERM_VIEW) or _can(request.user, PERM_ADD) or _can(request.user, PERM_CHANGE)


class PodeGerenciarCotacaoFornecedor(BasePermission):
    message = 'Você não tem permissão para gerenciar cotações de fornecedores.'

    def has_permission(self, request, view):
        return _can(request.user, PERM_ADD) or _can(request.user, PERM_CHANGE)


class PodeRegistrarRespostaCotacaoFornecedor(BasePermission):
    message = 'Você não tem permissão para registrar respostas de cotação.'

    def has_permission(self, request, view):
        return _can(request.user, PERM_RESPONSE)


class PodeSelecionarReferenciaCotacaoFornecedor(BasePermission):
    message = 'Você não tem permissão para selecionar referência de cotação.'

    def has_permission(self, request, view):
        return _can(request.user, PERM_REFERENCE)


class PodeCancelarCotacaoFornecedor(BasePermission):
    message = 'Você não tem permissão para cancelar cotações de fornecedores.'

    def has_permission(self, request, view):
        return _can(request.user, PERM_CANCEL)
