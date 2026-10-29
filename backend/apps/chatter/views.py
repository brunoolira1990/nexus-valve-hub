from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from nexus_erp.pagination import NexusPageNumberPagination

from .models import AnexoChatter, NotaChatter
from .serializers import AnexoChatterSerializer, NotaChatterSerializer


class NotaChatterViewSet(viewsets.ModelViewSet):
    """Notas internas do chatter: leitura para qualquer autenticado, escrita só no autor."""

    serializer_class = NotaChatterSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        queryset = NotaChatter.objects.select_related('autor').prefetch_related('anexos')
        params = self.request.query_params
        entity_type = (params.get('entity_type') or '').strip().lower()
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        entity_id = (params.get('entity_id') or '').strip()
        if entity_id:
            try:
                entity_id = int(entity_id)
            except ValueError:
                raise ValidationError({'entity_id': 'Identificador numérico inválido.'})
            queryset = queryset.filter(entity_id=entity_id)
        return queryset.order_by('-criado_em', '-id')

    def perform_create(self, serializer):
        serializer.save(autor=self.request.user)

    def perform_update(self, serializer):
        self._garantir_autor(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._garantir_autor(instance)
        instance.delete()

    def _garantir_autor(self, nota: NotaChatter) -> None:
        user = self.request.user
        if nota.autor_id == user.pk or user.is_superuser:
            return
        raise PermissionDenied('Só o autor pode editar ou excluir a própria nota.')


class AnexoChatterViewSet(viewsets.ModelViewSet):
    """Anexos das notas internas: leitura para qualquer autenticado, exclusão só no autor da nota."""

    serializer_class = AnexoChatterSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NexusPageNumberPagination
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = AnexoChatter.objects.select_related('nota', 'nota__autor')
        nota_id = (self.request.query_params.get('nota') or '').strip()
        if nota_id:
            try:
                nota_id = int(nota_id)
            except ValueError:
                raise ValidationError({'nota': 'Identificador numérico inválido.'})
            queryset = queryset.filter(nota_id=nota_id)
        return queryset.order_by('id')

    def perform_destroy(self, instance):
        nota = instance.nota
        user = self.request.user
        if nota.autor_id != user.pk and not user.is_superuser:
            raise PermissionDenied('Só o autor da nota pode excluir o anexo.')
        instance.delete()
