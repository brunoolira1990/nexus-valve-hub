from rest_framework import viewsets
from django.db.models import Q

from .models import Corrida
from .serializers import CorridaSerializer


class CorridaViewSet(viewsets.ModelViewSet):
    queryset = Corrida.objects.select_related('produto', 'fornecedor').all()
    serializer_class = CorridaSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('-id')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(produto__descricao__icontains=search)
                | Q(produto__codigo_completo__icontains=search)
                | Q(fornecedor__razao_social__icontains=search)
                | Q(nf_entrada__icontains=search),
            )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs
