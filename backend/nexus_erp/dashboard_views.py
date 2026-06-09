"""Views do BI modular (ERP 4.0.8)."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from nexus_erp.dashboard_bi_service import (
    MODULO_BUILDERS,
    montar_dashboard_home,
)
from nexus_erp.dashboard_filters import parse_dashboard_filters
from nexus_erp.dashboard_permissions import exigir_modulo, permissoes_dashboard
from nexus_erp.dashboard_service import montar_dashboard_resumo


def _filters_from_request(request):
    return parse_dashboard_filters(request.query_params)


def _deny_modulo(modulo: str):
    return Response(
        {'detail': f'Sem permissão para acessar o painel {modulo}.'},
        status=status.HTTP_403_FORBIDDEN,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_permissoes(request):
    """GET /api/dashboard/permissoes/ — mapa leve de permissões BI."""
    return Response(permissoes_dashboard(request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_home(request):
    """GET /api/dashboard/home/ — home personalizada por permissões."""
    return Response(montar_dashboard_home(request.user, _filters_from_request(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_comercial(request):
    if not exigir_modulo(request.user, 'comercial'):
        return _deny_modulo('comercial')
    return Response(MODULO_BUILDERS['comercial'](_filters_from_request(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_fiscal(request):
    if not exigir_modulo(request.user, 'fiscal'):
        return _deny_modulo('fiscal')
    return Response(MODULO_BUILDERS['fiscal'](_filters_from_request(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_estoque(request):
    if not exigir_modulo(request.user, 'estoque'):
        return _deny_modulo('estoque')
    return Response(MODULO_BUILDERS['estoque'](_filters_from_request(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_compras(request):
    if not exigir_modulo(request.user, 'compras'):
        return _deny_modulo('compras')
    return Response(MODULO_BUILDERS['compras'](_filters_from_request(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_qualidade(request):
    if not exigir_modulo(request.user, 'qualidade'):
        return _deny_modulo('qualidade')
    return Response(MODULO_BUILDERS['qualidade'](_filters_from_request(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_financeiro(request):
    if not exigir_modulo(request.user, 'financeiro'):
        return _deny_modulo('financeiro')
    return Response(MODULO_BUILDERS['financeiro'](_filters_from_request(request)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_resumo(request):
    """GET /api/dashboard/resumo/ — compatibilidade 4.0.6; filtra por permissão."""
    return Response(montar_dashboard_resumo(request.user))
