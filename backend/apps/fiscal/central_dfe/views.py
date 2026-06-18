"""API read-only da Central DF-e."""

from __future__ import annotations

import logging

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.fiscal.central_dfe.service import (
    EmpresaCentralDfeError,
    calcular_resumo_central,
    coletar_documentos_central_dfe,
    parse_filtros_central_dfe,
    resolver_empresa_central,
)
from nexus_erp.pagination import paginate_sequence

logger = logging.getLogger(__name__)


class CentralDfeViewSet(viewsets.ViewSet):
    """DF-e recebidos contra o CNPJ da empresa — somente consulta."""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        # QueryDict.dict() retorna escalares; dict(QueryDict) retorna listas e quebra .strip().
        params = request.query_params.dict()
        try:
            filtros = parse_filtros_central_dfe(params)
            empresa = resolver_empresa_central(params)
        except EmpresaCentralDfeError as exc:
            return Response({'detail': exc.mensagem, 'codigo': exc.codigo}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rows = coletar_documentos_central_dfe(filtros, empresa=empresa)
            resumo = calcular_resumo_central(rows)
            payload = [r.to_dict() for r in rows]
            response = paginate_sequence(request, payload)
            response.data['resumo'] = resumo
            if empresa:
                response.data['empresa'] = {
                    'id': empresa.pk,
                    'razao_social': empresa.razao_social,
                    'cnpj': empresa.cnpj,
                }
            return response
        except Exception as exc:
            logger.exception(
                'Erro ao listar central-dfe empresa_id=%s: %s',
                params.get('empresa_id'),
                type(exc).__name__,
            )
            return Response(
                {'detail': 'Não foi possível carregar DF-e Recebidos. Tente novamente.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
