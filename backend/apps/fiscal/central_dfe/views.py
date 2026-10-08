"""API read-only da Central DF-e."""

from __future__ import annotations

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.fiscal.central_dfe.armazenar_xml_service import (
    ArmazenarXmlCentralError,
    armazenar_xml_cte_central,
    armazenar_xml_nfe_central,
)
from apps.fiscal.central_dfe.serializers import ArmazenarXmlCentralSerializer
from apps.fiscal.central_dfe.service import (
    EmpresaCentralDfeError,
    calcular_resumo_central,
    coletar_documentos_central_dfe,
    parse_filtros_central_dfe,
    resolver_empresa_central,
)
from apps.fiscal.dfe_recebidos.permissoes import (
    MSG_SEM_PERMISSAO_CAPTURA,
    usuario_pode_capturar_dfe_recebidos,
)
from nexus_erp.pagination import paginate_sequence

logger = logging.getLogger(__name__)


def _sem_permissao_response():
    return Response({'detail': MSG_SEM_PERMISSAO_CAPTURA}, status=status.HTTP_403_FORBIDDEN)


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

    @action(detail=True, methods=['post'], url_path='armazenar-xml-nfe')
    def armazenar_xml_nfe(self, request, pk=None):
        """Armazena XML NF-e na Base NF-e Entrada Importada — somente ação manual explícita."""
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        ser = ArmazenarXmlCentralSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data.get('confirmacao_explicita'):
            return Response(
                {'detail': 'Confirmação explícita obrigatória.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            chave_raw = (ser.validated_data.get('chave_acesso') or '').strip()
            resultado = armazenar_xml_nfe_central(
                empresa_id=ser.validated_data['empresa_id'],
                documento_id=int(pk),
                chave_acesso=chave_raw or None,
                usuario=request.user,
                confirmacao_explicita=True,
            )
        except ArmazenarXmlCentralError as exc:
            logger.warning(
                'armazenar-xml-nfe 400 empresa_id=%s documento_id=%s chave=%s: %s',
                ser.validated_data.get('empresa_id'),
                pk,
                (chave_raw or '')[:8],
                exc,
            )
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)

    @action(detail=True, methods=['post'], url_path='armazenar-xml-cte')
    def armazenar_xml_cte(self, request, pk=None):
        """Confirma XML CT-e na Base CT-e Importada — somente ação manual explícita."""
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        ser = ArmazenarXmlCentralSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data.get('confirmacao_explicita'):
            return Response(
                {'detail': 'Confirmação explícita obrigatória.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = armazenar_xml_cte_central(
                empresa_id=ser.validated_data['empresa_id'],
                documento_id=int(pk),
                usuario=request.user,
                confirmacao_explicita=True,
            )
        except ArmazenarXmlCentralError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)
