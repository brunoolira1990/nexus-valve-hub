from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import RegraFiscal
from .serializers import RegraFiscalSerializer


class RegraFiscalViewSet(viewsets.ModelViewSet):
    queryset = RegraFiscal.objects.all()
    serializer_class = RegraFiscalSerializer

    @action(detail=False, methods=['get'], url_path='buscar')
    def buscar(self, request):
        ncm = request.query_params.get('ncm', '').strip()
        uf_origem = request.query_params.get('uf_origem', '').strip().upper()
        uf_destino = request.query_params.get('uf_destino', '').strip().upper()
        operacao = request.query_params.get('operacao', '').strip()
        if not all([ncm, uf_origem, uf_destino, operacao]):
            return Response(
                {'detail': 'Informe ncm, uf_origem, uf_destino e operacao.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        regra = RegraFiscal.objects.filter(
            ncm=ncm,
            uf_origem=uf_origem,
            uf_destino=uf_destino,
            operacao=operacao,
        ).first()
        if not regra:
            return Response({'detail': 'Nenhuma regra encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RegraFiscalSerializer(regra).data)
