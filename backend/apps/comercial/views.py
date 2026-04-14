from rest_framework import viewsets

from .models import PedidoCompra, PedidoVenda, Proposta
from .serializers import PedidoCompraSerializer, PedidoVendaSerializer, PropostaSerializer


class PropostaViewSet(viewsets.ModelViewSet):
    queryset = Proposta.objects.select_related('cliente').prefetch_related('itens__produto').all()
    serializer_class = PropostaSerializer


class PedidoVendaViewSet(viewsets.ModelViewSet):
    queryset = (
        PedidoVenda.objects.select_related('cliente', 'proposta')
        .prefetch_related('itens__produto', 'itens__corrida')
        .all()
    )
    serializer_class = PedidoVendaSerializer


class PedidoCompraViewSet(viewsets.ModelViewSet):
    queryset = PedidoCompra.objects.select_related('fornecedor').prefetch_related('itens__produto').all()
    serializer_class = PedidoCompraSerializer
