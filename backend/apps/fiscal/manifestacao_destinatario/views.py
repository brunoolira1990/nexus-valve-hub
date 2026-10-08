"""API — Monitor NF-e Destinada / Manifestação do Destinatário."""

from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.fiscal.dfe_recebidos.permissoes import (
    MSG_SEM_PERMISSAO_CAPTURA,
    usuario_pode_capturar_dfe_recebidos,
)
from apps.fiscal.manifestacao_destinatario.baixar_xml_service import (
    BaixarXmlDestinatarioError,
    baixar_xml_documento_destinatario,
)
from apps.fiscal.manifestacao_destinatario.consulta_service import (
    ManifestacaoConsultaError,
    consultar_nfe_destinadas,
)
from apps.fiscal.manifestacao_destinatario.fechamento_service import fechamento_preview_manifestacao
from apps.fiscal.manifestacao_destinatario.iniciar_por_chave_service import (
    IniciarPorChaveError,
    iniciar_manifestacao_por_chave,
)
from apps.fiscal.manifestacao_destinatario.manifestacao_service import (
    ManifestacaoDestinatarioError,
    manifestar_documento_destinatario,
)
from apps.fiscal.manifestacao_destinatario.serializers import (
    BaixarXmlDestinatarioSerializer,
    ConsultaManifestacaoSerializer,
    IniciarPorChaveSerializer,
    ManifestarDestinatarioSerializer,
    NFeDestinadaManifestacaoDetailSerializer,
    NFeDestinadaManifestacaoListSerializer,
)
from apps.fiscal.models import NFeDestinadaManifestacao
from nexus_erp.list_mixins import AutocompleteOrPaginationMixin
from nexus_erp.pagination import NexusPageNumberPagination


def _sem_permissao_response():
    return Response({'detail': MSG_SEM_PERMISSAO_CAPTURA}, status=status.HTTP_403_FORBIDDEN)


class ManifestacaoDestinatarioViewSet(AutocompleteOrPaginationMixin, viewsets.ReadOnlyModelViewSet):
    """Monitor NF-e destinada — consulta, manifestação e download XML manuais."""

    queryset = NFeDestinadaManifestacao.objects.select_related(
        'empresa',
        'nf_entrada_historica',
    ).prefetch_related('eventos__usuario').all()
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return NFeDestinadaManifestacaoDetailSerializer
        return NFeDestinadaManifestacaoListSerializer

    def list(self, request, *args, **kwargs):
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        empresa_id = params.get('empresa_id')
        if empresa_id:
            try:
                qs = qs.filter(empresa_id=int(empresa_id))
            except (TypeError, ValueError):
                pass

        status_manifestacao = params.get('status_manifestacao')
        if status_manifestacao:
            qs = qs.filter(status_manifestacao=status_manifestacao.strip().upper())

        status_xml = params.get('status_xml')
        if status_xml:
            qs = qs.filter(status_xml=status_xml.strip().upper())

        data_inicio = params.get('data_inicio')
        if data_inicio:
            qs = qs.filter(dh_emissao__date__gte=str(data_inicio)[:10])

        data_fim = params.get('data_fim')
        if data_fim:
            qs = qs.filter(dh_emissao__date__lte=str(data_fim)[:10])

        chave = params.get('chave_acesso')
        if chave:
            qs = qs.filter(chave_acesso__icontains=''.join(c for c in chave if c.isdigit()))

        ordering = params.get('ordering') or '-dh_emissao'
        if ordering.lstrip('-') in {'dh_emissao', 'valor_nf', 'id', 'consultado_em'}:
            qs = qs.order_by(ordering, '-id')
        else:
            qs = qs.order_by('-dh_emissao', '-id')
        return qs

    @action(detail=False, methods=['post'], url_path='consultar')
    def consultar(self, request):
        """Sync automático permitido: consulta resumos destinados (dist NSU). Não envia evento fiscal."""
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        ser = ConsultaManifestacaoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            resultado = consultar_nfe_destinadas(
                empresa_id=ser.validated_data['empresa_id'],
                usuario=request.user,
                limite_lotes=ser.validated_data.get('limite_lotes', 3),
            )
        except ManifestacaoConsultaError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)

    @action(detail=False, methods=['post'], url_path='iniciar-por-chave')
    def iniciar_por_chave(self, request):
        """Prepara registro de manifestação por chave — somente ação manual; sem evento fiscal ou download XML."""
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        ser = IniciarPorChaveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            documento, criado = iniciar_manifestacao_por_chave(
                empresa_id=ser.validated_data['empresa_id'],
                chave_acesso=ser.validated_data['chave_acesso'],
                nf_entrada_historica_id=ser.validated_data.get('nf_entrada_historica_id'),
                usuario=request.user,
            )
        except IniciarPorChaveError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'criado': criado,
                'documento': NFeDestinadaManifestacaoDetailSerializer(documento).data,
            },
        )

    @action(detail=True, methods=['post'], url_path='manifestar')
    def manifestar(self, request, pk=None):
        """Ação manual exclusiva: envia evento fiscal de manifestação do destinatário à SEFAZ."""
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        documento = self.get_object()
        ser = ManifestarDestinatarioSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data.get('confirmacao_explicita'):
            return Response(
                {'detail': 'Confirmação explícita obrigatória.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = manifestar_documento_destinatario(
                documento,
                evento=ser.validated_data['evento'],
                justificativa=ser.validated_data.get('justificativa') or '',
                confirmacao_explicita=True,
                usuario=request.user,
            )
        except ManifestacaoDestinatarioError as exc:
            code = status.HTTP_409_CONFLICT if exc.etapa == 'SEFAZ' else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc), 'etapa': exc.etapa}, status=code)
        documento.refresh_from_db()
        return Response(
            {
                **resultado,
                'documento': NFeDestinadaManifestacaoDetailSerializer(documento).data,
            },
        )

    @action(detail=True, methods=['post'], url_path='baixar-xml')
    def baixar_xml(self, request, pk=None):
        """Ação manual exclusiva: baixa XML completo do documento destinado (sem sync automático)."""
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        documento = self.get_object()
        ser = BaixarXmlDestinatarioSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data.get('confirmacao_explicita'):
            return Response(
                {'detail': 'Confirmação explícita obrigatória.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = baixar_xml_documento_destinatario(
                documento,
                confirmacao_explicita=True,
                usuario=request.user,
            )
        except BaixarXmlDestinatarioError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        documento.refresh_from_db()
        return Response(
            {
                **resultado,
                'documento': NFeDestinadaManifestacaoDetailSerializer(documento).data,
            },
        )

    @action(detail=False, methods=['get'], url_path='fechamento-preview')
    def fechamento_preview(self, request):
        if not usuario_pode_capturar_dfe_recebidos(request.user):
            return _sem_permissao_response()
        empresa_id = request.query_params.get('empresa_id')
        try:
            emp_id = int(empresa_id) if empresa_id else None
        except (TypeError, ValueError):
            emp_id = None
        try:
            payload = fechamento_preview_manifestacao(
                empresa_id=emp_id,
                data_inicio=request.query_params.get('data_inicio'),
                data_fim=request.query_params.get('data_fim'),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)
