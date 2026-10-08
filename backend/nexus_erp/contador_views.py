"""Views do módulo Contador."""

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from nexus_erp.contador_exportacao_service import (
    ContadorExportacaoError,
    montar_zip_xmls,
    validar_parametros_exportacao,
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contador_exportar_xmls(request):
    """GET /api/contador/exportar-xmls/?inicio=...&fim=...&tipo=..."""
    try:
        d_ini, d_fim, tipo = validar_parametros_exportacao(
            inicio=request.query_params.get('inicio', ''),
            fim=request.query_params.get('fim', ''),
            tipo=request.query_params.get('tipo', 'todos'),
        )
        conteudo, nome = montar_zip_xmls(inicio=d_ini, fim=d_fim, tipo=tipo)
    except ContadorExportacaoError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    response = HttpResponse(conteudo, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{nome}"'
    return response
