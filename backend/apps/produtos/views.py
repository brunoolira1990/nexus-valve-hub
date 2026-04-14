from rest_framework import viewsets

from .models import Ncm, Polegada, Produto
from .serializers import NcmSerializer, PolegadaSerializer, ProdutoSerializer


class ProdutoViewSet(viewsets.ModelViewSet):
    queryset = Produto.objects.all()
    serializer_class = ProdutoSerializer


class PolegadaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Polegada.objects.all()
    serializer_class = PolegadaSerializer


class NcmViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ncm.objects.all()
    serializer_class = NcmSerializer
