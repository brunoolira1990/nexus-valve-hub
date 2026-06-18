"""API read-only da Central DF-e."""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.fiscal.central_dfe.service import (
    calcular_resumo_central,
    coletar_documentos_central_dfe,
    parse_filtros_central_dfe,
    resolver_empresa_central,
)
from nexus_erp.pagination import paginate_sequence


class CentralDfeViewSet(viewsets.ViewSet):
    """DF-e recebidos contra o CNPJ da empresa — somente consulta."""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        params = dict(request.query_params)
        filtros = parse_filtros_central_dfe(params)
        empresa = resolver_empresa_central(params)
        rows = coletar_documentos_central_dfe(filtros, empresa=empresa)
        resumo = calcular_resumo_central(rows)
        response = paginate_sequence(request, [r.to_dict() for r in rows])
        response.data['resumo'] = resumo
        if empresa:
            response.data['empresa'] = {
                'id': empresa.pk,
                'razao_social': empresa.razao_social,
                'cnpj': empresa.cnpj,
            }
        return response
