"""Views — capability e leitura segura (sem consulta operacional nesta fundação)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.comercial.integracoes_credito.capabilities import montar_capability_integracoes
from apps.comercial.integracoes_credito.exceptions import IntegracaoCreditoError
from apps.comercial.integracoes_credito.permissions import (
    PodeListarConsultasExternas,
    PodeRegistrarProtestoManual,
    PodeSolicitarConsultaBuro,
    PodeSolicitarConsultaCadastral,
    PodeVerCapabilityIntegracoes,
    PodeVerProtestoManual,
    usuario_pode_ver_buro,
    usuario_pode_ver_cadastral,
)
from apps.comercial.integracoes_credito.protesto_manual import (
    ProtestoManualError,
    listar_protestos_manuais as qs_protestos_manuais,
    registrar_protesto_manual,
)
from apps.comercial.integracoes_credito.serializers import (
    ConsultaExternaAnaliseFinanceiraSerializer,
    ProtestoManualRegistroSerializer,
)
from apps.comercial.integracoes_credito.servico import tentar_consulta_buro, tentar_consulta_cadastral
from apps.comercial.models import ConsultaExternaAnaliseFinanceira


class IntegracoesCreditoActionsMixin:
    """Actions no AnaliseFinanceiraPropostaViewSet."""

    @action(
        detail=False,
        methods=['get'],
        url_path='integracoes/capacidade',
        permission_classes=[IsAuthenticated, PodeVerCapabilityIntegracoes],
    )
    def integracoes_capacidade(self, request):
        # Capability não cria registro e não chama HTTP externo.
        return Response(montar_capability_integracoes())

    @action(
        detail=True,
        methods=['get'],
        url_path='consultas-externas',
        permission_classes=[IsAuthenticated, PodeListarConsultasExternas],
    )
    def listar_consultas_externas(self, request, pk=None):
        analise = self.get_object()
        qs = ConsultaExternaAnaliseFinanceira.objects.filter(
            analise_financeira=analise
        ).order_by('-solicitada_em', '-id')

        tipos_permitidos = []
        if usuario_pode_ver_cadastral(request.user):
            tipos_permitidos.append(ConsultaExternaAnaliseFinanceira.Tipo.CADASTRAL)
        if usuario_pode_ver_buro(request.user):
            tipos_permitidos.append(ConsultaExternaAnaliseFinanceira.Tipo.BURO)
        if not tipos_permitidos:
            # Pode ver a análise, mas sem permissão de resultado externo: lista vazia.
            page = self.paginate_queryset(qs.none())
            if page is not None:
                return self.get_paginated_response([])
            return Response([])

        qs = qs.filter(tipo__in=tipos_permitidos)
        page = self.paginate_queryset(qs)
        ser = ConsultaExternaAnaliseFinanceiraSerializer(
            page if page is not None else qs,
            many=True,
            context={'request': request},
        )
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)

    @action(
        detail=True,
        methods=['post'],
        url_path='consultas-externas/cadastral',
        permission_classes=[IsAuthenticated, PodeSolicitarConsultaCadastral],
    )
    def solicitar_consulta_cadastral(self, request, pk=None):
        analise = self.get_object()
        cnpj = str((request.data or {}).get('cnpj') or '')
        try:
            tentar_consulta_cadastral(cnpj=cnpj, analise_id=analise.pk)
        except IntegracaoCreditoError as exc:
            return Response(exc.to_dict(), status=status.HTTP_409_CONFLICT)
        return Response(
            {'code': 'CONSULTA_DESABILITADA', 'detail': 'Consulta não habilitada.'},
            status=status.HTTP_409_CONFLICT,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='consultas-externas/buro',
        permission_classes=[IsAuthenticated, PodeSolicitarConsultaBuro],
    )
    def solicitar_consulta_buro(self, request, pk=None):
        analise = self.get_object()
        data = request.data if isinstance(request.data, dict) else {}
        try:
            tentar_consulta_buro(
                cnpj=str(data.get('cnpj') or ''),
                finalidade=str(data.get('finalidade') or ''),
                id_solicitacao=str(data.get('id_solicitacao') or ''),
                analise_id=analise.pk,
            )
        except IntegracaoCreditoError as exc:
            return Response(exc.to_dict(), status=status.HTTP_409_CONFLICT)
        return Response(
            {'code': 'CONSULTA_DESABILITADA', 'detail': 'Consulta não habilitada.'},
            status=status.HTTP_409_CONFLICT,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='protestos-manuais',
        permission_classes=[IsAuthenticated, PodeVerProtestoManual],
    )
    def listar_protestos_manuais(self, request, pk=None):
        """Histórico append-only de protestos manuais — somente PROTESTO_MANUAL."""
        analise = self.get_object()
        qs = qs_protestos_manuais(analise)
        page = self.paginate_queryset(qs)
        ser = ProtestoManualRegistroSerializer(
            page if page is not None else qs,
            many=True,
            context={'request': request},
        )
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)

    @action(
        detail=True,
        methods=['post'],
        url_path='protestos-manuais/registrar',
        permission_classes=[IsAuthenticated, PodeRegistrarProtestoManual],
    )
    def registrar_protesto_manual_action(self, request, pk=None):
        """Registra resultado manual; não chama portal externo nem certificado A1."""
        analise = self.get_object()
        data = request.data if isinstance(request.data, dict) else {}
        try:
            registro = registrar_protesto_manual(
                analise=analise,
                usuario=request.user,
                payload=data,
            )
        except ProtestoManualError as exc:
            return Response(exc.to_dict(), status=exc.http_status)
        return Response(
            ProtestoManualRegistroSerializer(registro, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )
