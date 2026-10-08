from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.escopo import entidade_auditada_permitida
from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.permissions import PodeVisualizarAuditoria
from apps.auditoria.serializers import RegistroAuditoriaSerializer


class AuditoriaHistoricoPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AuditoriaCapacidadeView(APIView):
    """Indica se o usuário autenticado pode ver histórico de auditoria."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        pode = bool(
            user.is_superuser or user.has_perm('auditoria.view_registroauditoria')
        )
        return Response({'pode_visualizar': pode})


class AuditoriaObjetoHistoricoView(APIView):
    """Histórico somente leitura de um objeto específico (Cliente/Produto)."""

    permission_classes = [IsAuthenticated, PodeVisualizarAuditoria]
    http_method_names = ['get', 'head', 'options']

    def get(self, request, app_label: str, model_name: str, object_id: int):
        chave = entidade_auditada_permitida(app_label, model_name)
        if chave is None:
            return Response(
                {'detail': 'Entidade não suportada para consulta de auditoria.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = (
            RegistroAuditoria.objects.filter(
                app_label=chave[0],
                model_name=chave[1],
                object_id=object_id,
            )
            .select_related('ator')
            .order_by('-criado_em', '-id')
        )

        paginator = AuditoriaHistoricoPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = RegistroAuditoriaSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
