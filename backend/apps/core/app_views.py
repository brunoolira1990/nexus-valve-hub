"""Endpoints de cabeçalho — ERP 4.0.14.9.3/4.0.14.9.4."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.app_contexto import montar_contexto_app, montar_minha_conta
from apps.core.busca_global import executar_busca_global
from apps.core.minha_conta_serializers import MinhaContaUpdateSerializer
from apps.core.minha_conta_service import atualizar_minha_conta


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def app_contexto(request):
    """GET /api/app/contexto/"""
    return Response(montar_contexto_app(request.user))


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def minha_conta(request):
    """GET/PATCH /api/minha-conta/"""
    if request.method == 'GET':
        return Response(montar_minha_conta(request.user))

    ser = MinhaContaUpdateSerializer(data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    try:
        atualizar_minha_conta(
            request.user,
            email=data.get('email'),
            telefone=data.get('telefone'),
        )
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({**montar_minha_conta(request.user), 'mensagem': 'Seus dados foram atualizados.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def busca_global(request):
    """GET /api/busca-global/?q=..."""
    q = (request.query_params.get('q') or '').strip()
    return Response(executar_busca_global(q))
