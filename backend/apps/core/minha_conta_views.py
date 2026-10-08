"""Minha conta — ERP 4.0.14.9.2."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cadastros.colaborador_senha import alterar_senha_proprio_usuario
from apps.cadastros.serializers import AlterarSenhaSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def alterar_senha(request):
    """POST /api/minha-conta/alterar-senha/"""
    ser = AlterarSenhaSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    try:
        alterar_senha_proprio_usuario(
            request.user,
            senha_atual=ser.validated_data['senha_atual'],
            nova_senha=ser.validated_data['nova_senha'],
            confirmar_senha=ser.validated_data['confirmar_senha'],
        )
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'mensagem': 'Senha alterada com sucesso.'})
