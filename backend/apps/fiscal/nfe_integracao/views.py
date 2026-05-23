"""API NF-e 3.6 / 3.6.1 — certificado A1 e status serviço SEFAZ."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeSefazStatusConsulta
from apps.fiscal.nfe_integracao.serializers import (
    ConsultarStatusServicoInputSerializer,
    NFeSefazStatusConsultaSerializer,
)
from apps.fiscal.nfe_integracao.services import (
    executar_status_servico,
    resposta_api_consulta,
)


class NFeSefazIntegracaoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Consultas de status SEFAZ persistidas.

    POST /api/nfe-sefaz-status/consultar/ — dispara consulta e grava histórico.
    """

    queryset = NFeSefazStatusConsulta.objects.select_related('empresa', 'consultado_por').all()
    serializer_class = NFeSefazStatusConsultaSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='consultar')
    def consultar(self, request):
        ser = ConsultarStatusServicoInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        empresa = Empresa.objects.filter(pk=data['empresa_id']).first()
        if not empresa:
            return Response({'detail': 'Empresa não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        uf = (data.get('uf') or '').strip() or None
        registro, resultado = executar_status_servico(
            empresa,
            uf=uf,
            homologacao=data.get('homologacao', True),
            usuario=request.user,
        )
        payload = resposta_api_consulta(registro, resultado)
        return Response(payload, status=status.HTTP_201_CREATED)
