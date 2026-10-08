from __future__ import annotations

from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination
from nexus_erp.view_mixins import FriendlyDestroyMixin

from apps.expedicao.etiquetas import ExpedicaoEtiquetaErro, gerar_etiquetas_pdf
from apps.expedicao.models import Expedicao, StatusExpedicao
from apps.expedicao.serializers import (
    ExpedicaoAlterarStatusSerializer,
    ExpedicaoCancelarSerializer,
    ExpedicaoSerializer,
)
from apps.expedicao.services.expedicao_service import (
    ExpedicaoErro,
    alterar_status_expedicao,
    atualizar_expedicao,
    cancelar_expedicao,
    criar_expedicao,
    resumo_expedicoes_por_status,
)


class ExpedicaoViewSet(FriendlyDestroyMixin, AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = Expedicao.objects.select_related(
        'cliente',
        'fornecedor',
        'transportadora',
        'pedido_venda',
        'pedido_compra',
        'faturamento',
        'nfe_saida',
        'alocacao_atendimento',
        'nfe_entrada',
        'cte_entrada',
        'criado_por',
    ).all()
    serializer_class = ExpedicaoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params

        search = (p.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(codigo__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(fornecedor__razao_social__icontains=search)
                | Q(transportadora__razao_social__icontains=search)
                | Q(motorista_nome__icontains=search)
                | Q(placa_veiculo__icontains=search)
                | Q(observacoes__icontains=search)
                | Q(ocorrencia_descricao__icontains=search),
            )

        status_f = (p.get('status') or '').strip()
        if status_f:
            qs = qs.filter(status=status_f)

        tipo = (p.get('tipo_operacao') or '').strip()
        if tipo:
            qs = qs.filter(tipo_operacao=tipo)

        for param, campo in (
            ('cliente_id', 'cliente_id'),
            ('fornecedor_id', 'fornecedor_id'),
            ('transportadora_id', 'transportadora_id'),
            ('pedido_venda_id', 'pedido_venda_id'),
            ('pedido_compra_id', 'pedido_compra_id'),
            ('faturamento_id', 'faturamento_id'),
            ('nfe_saida_id', 'nfe_saida_id'),
            ('alocacao_atendimento_id', 'alocacao_atendimento_id'),
        ):
            val = (p.get(param) or '').strip()
            if val.isdigit():
                qs = qs.filter(**{campo: int(val)})

        motorista = (p.get('motorista') or '').strip()
        if motorista:
            qs = qs.filter(
                Q(motorista_nome__icontains=motorista) | Q(transportadora__razao_social__icontains=motorista),
            )

        def _filtro_periodo(inicio_key: str, fim_key: str, campo: str):
            nonlocal qs
            di = parse_date((p.get(inicio_key) or '').strip())
            df = parse_date((p.get(fim_key) or '').strip())
            if di:
                qs = qs.filter(**{f'{campo}__gte': di})
            if df:
                qs = qs.filter(**{f'{campo}__lte': df})

        _filtro_periodo('prev_retirada_de', 'prev_retirada_ate', 'data_prevista_retirada')
        _filtro_periodo('prev_entrega_de', 'prev_entrega_ate', 'data_prevista_entrega')

        entrega_de = parse_datetime((p.get('entrega_real_de') or '').strip())
        entrega_ate = parse_datetime((p.get('entrega_real_ate') or '').strip())
        if entrega_de:
            qs = qs.filter(data_hora_entrega_real__gte=entrega_de)
        if entrega_ate:
            qs = qs.filter(data_hora_entrega_real__lte=entrega_ate)

        return aplicar_ordering(
            qs,
            p.get('ordering'),
            {
                'codigo': 'codigo',
                'status': 'status',
                'tipo_operacao': 'tipo_operacao',
                'criado_em': 'criado_em',
                'data_prevista_retirada': 'data_prevista_retirada',
                'data_prevista_entrega': 'data_prevista_entrega',
                'data_hora_entrega_real': 'data_hora_entrega_real',
            },
            '-criado_em',
        )

    def create(self, request, *args, **kwargs):
        try:
            exp = criar_expedicao(request.data, usuario=request.user)
        except (ExpedicaoErro, ValueError) as exc:
            return Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(exp).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            exp = atualizar_expedicao(instance, request.data, usuario=request.user)
        except (ExpedicaoErro, ValueError) as exc:
            return Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(exp).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != StatusExpedicao.RASCUNHO:
            return Response(
                {'ok': False, 'mensagem': 'Somente expedições em rascunho podem ser excluídas. Use cancelamento.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if isinstance(response.data, dict) and 'results' in response.data:
            response.data['resumo'] = resumo_expedicoes_por_status()
        return response

    @action(detail=True, methods=['post'], url_path='etiquetas-pdf')
    def etiquetas_pdf(self, request, pk=None):
        try:
            return gerar_etiquetas_pdf(int(pk))
        except Expedicao.DoesNotExist:
            return Response({'ok': False, 'mensagem': 'Expedição não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except ExpedicaoEtiquetaErro as exc:
            return Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='resumo')
    def resumo(self, request):
        return Response(resumo_expedicoes_por_status())

    @action(detail=True, methods=['post'], url_path='alterar-status')
    def alterar_status(self, request, pk=None):
        exp = self.get_object()
        ser = ExpedicaoAlterarStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            exp = alterar_status_expedicao(
                exp,
                status=ser.validated_data['status'],
                ocorrencia_descricao=ser.validated_data.get('ocorrencia_descricao') or '',
                usuario=request.user,
            )
        except ExpedicaoErro as exc:
            return Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(exp).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        exp = self.get_object()
        ser = ExpedicaoCancelarSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            exp = cancelar_expedicao(exp, motivo=ser.validated_data.get('motivo') or '', usuario=request.user)
        except ExpedicaoErro as exc:
            return Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(exp).data)
