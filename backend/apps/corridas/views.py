from rest_framework import viewsets

from .models import Corrida
from .serializers import CorridaSerializer


class CorridaViewSet(viewsets.ModelViewSet):
    queryset = Corrida.objects.select_related('produto', 'fornecedor').all()
    serializer_class = CorridaSerializer
