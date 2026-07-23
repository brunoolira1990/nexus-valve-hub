from rest_framework import viewsets
from django.db.models import Q

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination

from .models import Corrida
from .serializers import CorridaSerializer


class CorridaViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = Corrida.objects.select_related('produto', 'fornecedor').all()
    serializer_class = CorridaSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

            qs = filtrar_queryset_por_numeros_documento(
                qs,
                search,
                'numero',
                'nf_entrada',
                q_extra=(
                    Q(produto__descricao__icontains=search)
                    | Q(produto__codigo_completo__icontains=search)
                    | Q(fornecedor__razao_social__icontains=search)
                    | Q(material__icontains=search)
                ),
            )
        material = (self.request.query_params.get('material') or '').strip()
        if material:
            qs = qs.filter(material__icontains=material)
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'numero': 'numero', 'material': 'material'},
            '-id',
        )
