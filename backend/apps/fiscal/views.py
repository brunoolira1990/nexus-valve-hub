from rest_framework import response, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.qualidade.models import Certificado

from .estoque_services import reverter_todos_itens_entrada, reverter_todos_itens_saida
from .models import CTeEntrada, EstoqueCorrida, NFeEntrada, NFeSaida
from .serializers import (
    CTeEntradaSerializer,
    NFeEntradaSerializer,
    NFeSaidaSerializer,
)


class NFeEntradaViewSet(viewsets.ModelViewSet):
    queryset = (
        NFeEntrada.objects.select_related('fornecedor', 'pedido_compra', 'cte')
        .prefetch_related('itens__produto', 'itens__corrida')
        .all()
    )
    serializer_class = NFeEntradaSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        reverter_todos_itens_entrada(instance)
        instance.delete()


class NFeSaidaViewSet(viewsets.ModelViewSet):
    queryset = (
        NFeSaida.objects.select_related('cliente', 'pedido_venda')
        .prefetch_related('itens__produto', 'itens__corrida')
        .all()
    )
    serializer_class = NFeSaidaSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        reverter_todos_itens_saida(instance)
        Certificado.objects.filter(nf_saida=instance).delete()
        instance.delete()


class CTeEntradaViewSet(viewsets.ModelViewSet):
    queryset = CTeEntrada.objects.select_related('transportadora', 'tomador').all()
    serializer_class = CTeEntradaSerializer
    permission_classes = [IsAuthenticated]


class EstoqueViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        rows = EstoqueCorrida.objects.select_related('produto', 'corrida').all()
        data = [
            {
                'produto_id': r.produto_id,
                'produto_nome': r.produto.descricao,
                'corrida_id': r.corrida_id,
                'corrida_numero': r.corrida.numero,
                'saldo': float(r.saldo),
            }
            for r in rows
        ]
        return response.Response(data)
