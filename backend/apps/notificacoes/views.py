from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nexus_erp.pagination import NexusPageNumberPagination

from .models import Notificacao
from .serializers import NotificacaoSerializer
from .service import arquivar, marcar_como_lida


class NotificacaoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificacaoSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        queryset = Notificacao.objects.filter(destinatario=self.request.user)
        params = self.request.query_params
        if params.get('incluir_arquivadas') not in ('1', 'true', 'True'):
            queryset = queryset.filter(arquivada=False)
        for field in ('modulo', 'tipo', 'prioridade'):
            value = params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        lida = params.get('lida')
        if lida in ('true', '1', 'True'):
            queryset = queryset.filter(lida=True)
        elif lida in ('false', '0', 'False'):
            queryset = queryset.filter(lida=False)
        busca = (params.get('busca') or '').strip()
        if busca:
            queryset = queryset.filter(titulo__icontains=busca) | queryset.filter(mensagem__icontains=busca)
        return queryset.order_by('-criado_em', '-id')

    @action(detail=False, methods=['get'], url_path='nao-lidas-count')
    def nao_lidas_count(self, request):
        count = self.get_queryset().filter(lida=False).count()
        return Response({'count': count})

    @action(detail=False, methods=['post'], url_path='marcar-todas-lidas')
    def marcar_todas_lidas(self, request):
        agora = timezone.now()
        atualizadas = self.get_queryset().filter(lida=False).update(lida=True, lida_em=agora)
        return Response({'atualizadas': atualizadas, 'count': 0})

    @action(detail=True, methods=['post'], url_path='marcar-lida')
    def marcar_lida(self, request, pk=None):
        notificacao = self.get_object()
        marcar_como_lida(notificacao)
        return Response(self.get_serializer(notificacao).data)

    @action(detail=True, methods=['post'], url_path='arquivar')
    def arquivar(self, request, pk=None):
        notificacao = self.get_object()
        arquivar(notificacao)
        return Response(self.get_serializer(notificacao).data)
