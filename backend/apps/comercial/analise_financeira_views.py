from datetime import date
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comercial.analise_financeira_permissions import (
    PodeDecidirAnaliseFinanceiraProposta,
    PodeSolicitarAnaliseFinanceiraProposta,
    PodeVerAnaliseFinanceiraProposta,
    usuario_pode_decidir_analise,
    usuario_pode_solicitar_analise,
    usuario_pode_ver_detalhe_financeiro,
)
from apps.comercial.analise_financeira_serializers import (
    AnaliseFinanceiraListSerializer,
    AnaliseFinanceiraPropostaSerializer,
)
from apps.comercial.analise_financeira_servico import (
    aprovar_como_solicitado,
    aprovar_com_ajuste,
    devolver_analise,
    iniciar_analise,
    nao_aprovar,
    solicitar_analise,
    situacao_proposta,
)
from apps.comercial.integracoes_credito.views import IntegracoesCreditoActionsMixin
from apps.comercial.models import AnaliseFinanceiraProposta, Proposta
from rest_framework.permissions import IsAuthenticated


class AnaliseFinanceiraPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _parse_decimal(raw) -> Decimal | None:
    if raw is None or raw == '':
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Valor monetário inválido.') from exc


def _parse_date(raw) -> date | None:
    if raw is None or raw == '':
        return None
    if isinstance(raw, date):
        return raw
    d = parse_date(str(raw)[:10])
    if not d:
        raise ValueError('Data inválida.')
    return d


class PropostaAnaliseFinanceiraActionsMixin:
    """Actions no PropostaViewSet."""

    @action(
        detail=True,
        methods=['get'],
        url_path='analise-financeira',
        permission_classes=[IsAuthenticated, PodeVerAnaliseFinanceiraProposta],
    )
    def analise_financeira(self, request, pk=None):
        proposta = self.get_object()
        situacao = situacao_proposta(proposta)
        situacao['permissoes'] = {
            'pode_solicitar': usuario_pode_solicitar_analise(request.user),
            'pode_decidir': usuario_pode_decidir_analise(request.user),
            'pode_ver_detalhe_financeiro': usuario_pode_ver_detalhe_financeiro(request.user),
        }
        qs = AnaliseFinanceiraProposta.objects.filter(proposta=proposta).select_related(
            'cliente', 'solicitada_por', 'decidida_por'
        ).prefetch_related('eventos__ator').order_by('-solicitada_em', '-id')
        historico = AnaliseFinanceiraListSerializer(qs[:20], many=True, context={'request': request}).data
        ultima = qs.first()
        detalhe = (
            AnaliseFinanceiraPropostaSerializer(ultima, context={'request': request}).data if ultima else None
        )
        return Response({'situacao': situacao, 'ultima': detalhe, 'historico': historico})

    @action(
        detail=True,
        methods=['post'],
        url_path='analise-financeira/solicitar',
        permission_classes=[IsAuthenticated, PodeSolicitarAnaliseFinanceiraProposta],
    )
    def solicitar_analise_financeira(self, request, pk=None):
        proposta = self.get_object()
        obs = str((request.data or {}).get('observacao_vendedor') or '')
        try:
            analise = solicitar_analise(proposta, usuario=request.user, observacao_vendedor=obs)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            AnaliseFinanceiraPropostaSerializer(analise, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class AnaliseFinanceiraPropostaViewSet(IntegracoesCreditoActionsMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, PodeVerAnaliseFinanceiraProposta]
    pagination_class = AnaliseFinanceiraPagination
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = AnaliseFinanceiraProposta.objects.select_related(
            'proposta', 'cliente', 'solicitada_por', 'decidida_por', 'iniciada_por'
        ).prefetch_related('eventos__ator')
        params = self.request.query_params
        status_f = (params.get('status') or '').strip()
        if status_f:
            qs = qs.filter(status=status_f.upper())
        cliente = (params.get('cliente') or params.get('cliente_id') or '').strip()
        if cliente.isdigit():
            qs = qs.filter(cliente_id=int(cliente))
        vendedor = (params.get('vendedor') or '').strip()
        if vendedor:
            qs = qs.filter(proposta__vendedor__icontains=vendedor)
        return qs.order_by('-solicitada_em', '-id')

    def get_serializer_class(self):
        if self.action == 'list':
            return AnaliseFinanceiraListSerializer
        return AnaliseFinanceiraPropostaSerializer

    @action(
        detail=True,
        methods=['post'],
        url_path='iniciar',
        permission_classes=[IsAuthenticated, PodeDecidirAnaliseFinanceiraProposta],
    )
    def iniciar(self, request, pk=None):
        try:
            analise = iniciar_analise(self.get_object(), usuario=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AnaliseFinanceiraPropostaSerializer(analise, context={'request': request}).data)

    @action(
        detail=True,
        methods=['post'],
        url_path='aprovar',
        permission_classes=[IsAuthenticated, PodeDecidirAnaliseFinanceiraProposta],
    )
    def aprovar(self, request, pk=None):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            analise = aprovar_como_solicitado(
                self.get_object(),
                usuario=request.user,
                valida_ate=_parse_date(data.get('valida_ate')),
                valor_maximo=_parse_decimal(data.get('valor_maximo_aprovado')),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AnaliseFinanceiraPropostaSerializer(analise, context={'request': request}).data)

    @action(
        detail=True,
        methods=['post'],
        url_path='aprovar-com-ajuste',
        permission_classes=[IsAuthenticated, PodeDecidirAnaliseFinanceiraProposta],
    )
    def aprovar_com_ajuste_action(self, request, pk=None):
        data = request.data if isinstance(request.data, dict) else {}
        dias = data.get('dias_aprovados') or data.get('dias')
        if not isinstance(dias, list):
            return Response({'detail': 'Informe dias_aprovados como lista de inteiros.'}, status=400)
        try:
            analise = aprovar_com_ajuste(
                self.get_object(),
                usuario=request.user,
                dias_aprovados=dias,
                justificativa=str(data.get('justificativa') or ''),
                valida_ate=_parse_date(data.get('valida_ate')),
                valor_maximo=_parse_decimal(data.get('valor_maximo_aprovado')),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AnaliseFinanceiraPropostaSerializer(analise, context={'request': request}).data)

    @action(
        detail=True,
        methods=['post'],
        url_path='devolver',
        permission_classes=[IsAuthenticated, PodeDecidirAnaliseFinanceiraProposta],
    )
    def devolver(self, request, pk=None):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            analise = devolver_analise(
                self.get_object(),
                usuario=request.user,
                justificativa=str(data.get('justificativa') or ''),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AnaliseFinanceiraPropostaSerializer(analise, context={'request': request}).data)

    @action(
        detail=True,
        methods=['post'],
        url_path='nao-aprovar',
        permission_classes=[IsAuthenticated, PodeDecidirAnaliseFinanceiraProposta],
    )
    def nao_aprovar_action(self, request, pk=None):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            analise = nao_aprovar(
                self.get_object(),
                usuario=request.user,
                justificativa=str(data.get('justificativa') or ''),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AnaliseFinanceiraPropostaSerializer(analise, context={'request': request}).data)
