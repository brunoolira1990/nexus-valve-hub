"""Endpoint de captura manual DF-e recebidos via SEFAZ."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fiscal.dfe_recebidos.captura_sefaz import capturar_dfe_recebidos_sefaz
from apps.fiscal.dfe_recebidos.permissoes import (
    MSG_SEM_PERMISSAO_CAPTURA,
    usuario_pode_capturar_dfe_recebidos,
)


class DfeRecebidosCapturaView(APIView):
    """POST /api/dfe-recebidos/capturar/ — captura NF-e/CT-e da SEFAZ para base importada."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return Response(
                {'sucesso': False, 'erros': [MSG_SEM_PERMISSAO_CAPTURA]},
                status=status.HTTP_403_FORBIDDEN,
            )

        body = request.data if isinstance(request.data, dict) else {}
        empresa_id = body.get('empresa_id')
        if not empresa_id:
            return Response(
                {'sucesso': False, 'erros': ['Informe empresa_id.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tipos = body.get('tipos')
        if isinstance(tipos, str):
            tipos = [tipos]
        modo = str(body.get('modo') or 'incremental')
        limite_lotes = body.get('limite_lotes', 3)

        try:
            limite_int = int(limite_lotes)
        except (TypeError, ValueError):
            limite_int = 3

        resultado = capturar_dfe_recebidos_sefaz(
            empresa_id=int(empresa_id),
            tipos=tipos,
            modo=modo,
            limite_lotes=limite_int,
        )

        http_status = status.HTTP_200_OK
        if not resultado.get('sucesso') and resultado.get('erros'):
            if any('não encontrada' in str(e).lower() for e in resultado['erros']):
                http_status = status.HTTP_400_BAD_REQUEST
            elif any('permissão' in str(e).lower() for e in resultado['erros']):
                http_status = status.HTTP_403_FORBIDDEN

        return Response(resultado, status=http_status)
