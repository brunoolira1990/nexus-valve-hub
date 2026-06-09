"""API REST — financeiro operacional."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.financeiro.constants import formas_pagamento_api_payload, tipos_movimento_api_payload
from apps.financeiro.models import (
    BaixaFinanceira,
    CategoriaFinanceira,
    CentroCusto,
    ContaFinanceira,
    CreditoFinanceiro,
    TituloFinanceiro,
)
from apps.financeiro.serializers import (
    AbatimentoCreateSerializer,
    AplicarCreditoSerializer,
    BaixaCreateSerializer,
    BaixaFinanceiraSerializer,
    CancelarCreditoSerializer,
    CancelarTituloSerializer,
    CategoriaFinanceiraSerializer,
    CentroCustoSerializer,
    ContaFinanceiraSerializer,
    CreditoCreateSerializer,
    CreditoFinanceiroSerializer,
    CreditoUpdateSerializer,
    EstornoBaixaSerializer,
    ExcluirMotivoSerializer,
    ReembolsoCreditoSerializer,
    TituloFinanceiroCreateSerializer,
    TituloFinanceiroSerializer,
)
from apps.financeiro.services.baixa import BaixaFinanceiraError, estornar_baixa_financeira, registrar_baixa_financeira
from apps.financeiro.services.credito import (
    CreditoFinanceiroError,
    aplicar_credito_em_titulo,
    atualizar_credito_financeiro,
    cancelar_credito_financeiro,
    criar_credito_financeiro,
    excluir_credito_financeiro,
    reembolsar_credito,
)
from apps.financeiro.services.movimento import MovimentoFinanceiroError, registrar_abatimento_devolucao
from apps.financeiro.filtragem import aplicar_filtros_titulo
from apps.financeiro.relatorios import (
    relatorio_categorias,
    relatorio_clientes,
    relatorio_contas_pagar,
    relatorio_contas_receber,
    relatorio_fluxo_previsto,
    relatorio_fornecedores,
)
from apps.financeiro.relatorios_pdf import (
    pdf_relatorio_categorias,
    pdf_relatorio_clientes,
    pdf_relatorio_contas_pagar,
    pdf_relatorio_contas_receber,
    pdf_relatorio_fluxo_previsto,
    pdf_relatorio_fornecedores,
)
from apps.relatorios.http import pdf_http_response
from apps.relatorios.renderers import PdfBytesRenderer
from apps.financeiro.resumo import montar_resumo_financeiro
from apps.financeiro.services.titulo import (
    cancelar_titulo_financeiro,
    criar_titulo_financeiro,
    excluir_titulo_financeiro,
)
from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination
from nexus_erp.view_mixins import FriendlyDestroyMixin

logger = logging.getLogger(__name__)


def _friendly_error(exc: Exception) -> Response:
    msg = str(exc)
    return Response({'mensagem': msg, 'detail': msg}, status=status.HTTP_400_BAD_REQUEST)


def _titulo_detail_data(titulo, request) -> dict:
    return TituloFinanceiroSerializer(
        titulo,
        context={'request': request, 'detail': True},
    ).data


ORDERING_TITULO_FINANCEIRO = {
    'data_vencimento': 'data_vencimento',
    'data_emissao': 'data_emissao',
    'numero': 'numero',
    'valor_original': 'valor_original',
    'valor_aberto': 'valor_aberto',
    'status': 'status',
}


class ContaFinanceiraViewSet(AutocompleteOrPaginationMixin, FriendlyDestroyMixin, viewsets.ModelViewSet):
    queryset = ContaFinanceira.objects.all()
    serializer_class = ContaFinanceiraSerializer
    pagination_class = NexusPageNumberPagination


class CategoriaFinanceiraViewSet(AutocompleteOrPaginationMixin, FriendlyDestroyMixin, viewsets.ModelViewSet):
    queryset = CategoriaFinanceira.objects.select_related('categoria_pai').all()
    serializer_class = CategoriaFinanceiraSerializer
    pagination_class = NexusPageNumberPagination


class CentroCustoViewSet(AutocompleteOrPaginationMixin, FriendlyDestroyMixin, viewsets.ModelViewSet):
    queryset = CentroCusto.objects.all()
    serializer_class = CentroCustoSerializer
    pagination_class = NexusPageNumberPagination


class TituloFinanceiroViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    serializer_class = TituloFinanceiroSerializer
    pagination_class = NexusPageNumberPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = TituloFinanceiro.objects.select_related(
            'cliente', 'fornecedor', 'conta_financeira_prevista', 'categoria', 'centro_custo',
        ).prefetch_related('parcelas', 'baixas', 'baixas__conta_financeira', 'eventos', 'eventos__usuario')
        tipo = getattr(self, '_tipo_fixo', None) or (self.request.query_params.get('tipo') or '').strip()
        if tipo:
            qs = qs.filter(tipo=tipo)
        qs = aplicar_filtros_titulo(qs, self.request.query_params)
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            ORDERING_TITULO_FINANCEIRO,
            '-data_vencimento',
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return TituloFinanceiroCreateSerializer
        return TituloFinanceiroSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == 'retrieve':
            context['detail'] = True
        return context

    def create(self, request, *args, **kwargs):
        ser = TituloFinanceiroCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        tipo = getattr(self, '_tipo_fixo', None) or data.get('tipo') or TituloFinanceiro.Tipo.RECEBER
        try:
            titulo = criar_titulo_financeiro(
                tipo=tipo,
                numero=data.get('numero'),
                cliente_id=data.get('cliente'),
                fornecedor_id=data.get('fornecedor'),
                tipo_lancamento=data.get('tipo_lancamento') or '',
                descricao=data.get('descricao', ''),
                competencia=data.get('competencia'),
                tipo_tributo=data.get('tipo_tributo') or '',
                periodo_apuracao=data.get('periodo_apuracao', ''),
                numero_guia=data.get('numero_guia', ''),
                codigo_receita=data.get('codigo_receita', ''),
                data_emissao=data['data_emissao'],
                data_vencimento=data['data_vencimento'],
                valor_original=data['valor_original'],
                origem_tipo=data.get('origem_tipo') or TituloFinanceiro.OrigemTipo.MANUAL,
                origem_id=data.get('origem_id'),
                origem_numero=data.get('origem_numero', ''),
                origem_descricao=data.get('origem_descricao', ''),
                origem_data=data.get('origem_data'),
                documento_origem=data.get('documento_origem', ''),
                forma_pagamento_prevista_codigo=data.get('forma_pagamento_prevista_codigo', ''),
                conta_financeira_prevista_id=data.get('conta_financeira_prevista'),
                categoria_id=data.get('categoria'),
                centro_custo_id=data.get('centro_custo'),
                observacoes=data.get('observacoes', ''),
                gerar_parcelas=data.get('gerar_parcelas', False),
                quantidade_parcelas=data.get('quantidade_parcelas', 1),
                intervalo_dias=data.get('intervalo_dias', 30),
                primeiro_vencimento_dias=data.get('primeiro_vencimento_dias', 0),
                parcelas_custom=data.get('parcelas'),
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return _friendly_error(exc)
        return Response(TituloFinanceiroSerializer(titulo, context={'request': request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='baixar')
    def baixar(self, request, pk=None):
        titulo = self.get_object()
        ser = BaixaCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            baixa = registrar_baixa_financeira(
                titulo,
                data_baixa=data['data_baixa'],
                valor=data['valor'],
                conta_financeira_id=data.get('conta_financeira'),
                forma_pagamento_codigo=data['forma_pagamento_codigo'],
                parcela_id=data.get('parcela'),
                juros=data.get('juros', Decimal('0')),
                multa=data.get('multa', Decimal('0')),
                desconto=data.get('desconto', Decimal('0')),
                tarifa=data.get('tarifa', Decimal('0')),
                observacoes=data.get('observacoes', ''),
                usuario=request.user if request.user.is_authenticated else None,
            )
        except (BaixaFinanceiraError, ValueError) as exc:
            return _friendly_error(exc)
        titulo.refresh_from_db()
        return Response({'baixa': BaixaFinanceiraSerializer(baixa).data, 'titulo': _titulo_detail_data(titulo, request)})

    @action(detail=True, methods=['post'], url_path='abater-devolucao')
    def abater_devolucao(self, request, pk=None):
        titulo = self.get_object()
        ser = AbatimentoCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            baixa = registrar_abatimento_devolucao(
                titulo,
                valor=data['valor'],
                data_abatimento=data['data'],
                motivo=data['motivo'],
                parcela_id=data.get('parcela'),
                documento_referencia=data.get('documento_referencia', ''),
                observacoes=data.get('observacoes', ''),
                usuario=request.user if request.user.is_authenticated else None,
            )
        except (MovimentoFinanceiroError, ValueError) as exc:
            return _friendly_error(exc)
        titulo.refresh_from_db()
        return Response({'baixa': BaixaFinanceiraSerializer(baixa).data, 'titulo': _titulo_detail_data(titulo, request)})

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        titulo = self.get_object()
        ser = CancelarTituloSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            cancelar_titulo_financeiro(titulo, motivo=ser.validated_data['motivo'], usuario=request.user if request.user.is_authenticated else None)
        except ValueError as exc:
            return _friendly_error(exc)
        titulo.refresh_from_db()
        return Response({'titulo': _titulo_detail_data(titulo, request)})

    @action(detail=True, methods=['post'], url_path='excluir')
    def excluir(self, request, pk=None):
        titulo = self.get_object()
        ser = ExcluirMotivoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            excluir_titulo_financeiro(
                titulo,
                motivo=ser.validated_data['motivo'],
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return _friendly_error(exc)
        return Response({'mensagem': 'Título excluído com sucesso.'}, status=status.HTTP_200_OK)


class ContaReceberViewSet(TituloFinanceiroViewSet):
    _tipo_fixo = TituloFinanceiro.Tipo.RECEBER


class ContaPagarViewSet(TituloFinanceiroViewSet):
    _tipo_fixo = TituloFinanceiro.Tipo.PAGAR


class CreditoFinanceiroViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = CreditoFinanceiro.objects.select_related('cliente', 'fornecedor').prefetch_related(
        'eventos',
        'eventos__usuario',
        'movimentos',
        'movimentos__conta_financeira',
    ).all()
    serializer_class = CreditoFinanceiroSerializer
    pagination_class = NexusPageNumberPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == 'retrieve':
            context['detail'] = True
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        tipo = (self.request.query_params.get('tipo') or '').strip()
        if tipo:
            qs = qs.filter(tipo=tipo)
        st = (self.request.query_params.get('status') or '').strip()
        if st:
            qs = qs.filter(status=st)
        origem = (self.request.query_params.get('origem_tipo') or '').strip()
        if origem:
            qs = qs.filter(origem_tipo=origem)
        cliente_id = (self.request.query_params.get('cliente') or '').strip()
        if cliente_id.isdigit():
            qs = qs.filter(cliente_id=int(cliente_id))
        fornecedor_id = (self.request.query_params.get('fornecedor') or '').strip()
        if fornecedor_id.isdigit():
            qs = qs.filter(fornecedor_id=int(fornecedor_id))
        data_de = (self.request.query_params.get('data_de') or '').strip()
        if data_de:
            qs = qs.filter(data_credito__gte=data_de)
        data_ate = (self.request.query_params.get('data_ate') or '').strip()
        if data_ate:
            qs = qs.filter(data_credito__lte=data_ate)
        disponivel = (self.request.query_params.get('disponivel') or '').strip().lower()
        if disponivel in ('1', 'true', 'sim'):
            qs = qs.filter(cancelado=False, saldo__gt=Decimal('0.01'))
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(motivo__icontains=search)
                | Q(origem_numero__icontains=search)
                | Q(origem_descricao__icontains=search)
            )
        return qs.order_by('-data_credito', '-pk')

    def get_serializer_class(self):
        if self.action == 'create':
            return CreditoCreateSerializer
        if self.action in ('partial_update', 'update'):
            return CreditoUpdateSerializer
        return CreditoFinanceiroSerializer

    def create(self, request, *args, **kwargs):
        ser = CreditoCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            credito = criar_credito_financeiro(
                tipo=d['tipo'],
                cliente_id=d.get('cliente'),
                fornecedor_id=d.get('fornecedor'),
                valor_original=d['valor_original'],
                data_credito=d['data_credito'],
                motivo=d['motivo'],
                origem_tipo=d.get('origem_tipo') or CreditoFinanceiro.OrigemTipo.MANUAL,
                origem_descricao=d.get('origem_descricao', ''),
                origem_numero=d.get('origem_numero', ''),
                observacoes=d.get('observacoes', ''),
                usuario=request.user if request.user.is_authenticated else None,
            )
        except (CreditoFinanceiroError, ValueError) as exc:
            return _friendly_error(exc)
        return Response(CreditoFinanceiroSerializer(credito).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        credito = self.get_object()
        ser = CreditoUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            credito = atualizar_credito_financeiro(
                credito,
                usuario=request.user if request.user.is_authenticated else None,
                cliente_id=data.get('cliente'),
                fornecedor_id=data.get('fornecedor'),
                valor_original=data.get('valor_original'),
                origem_tipo=data.get('origem_tipo'),
                origem_numero=data.get('origem_numero'),
                origem_descricao=data.get('origem_descricao'),
                data_credito=data.get('data_credito'),
                motivo=data.get('motivo'),
                observacoes=data.get('observacoes'),
            )
        except (CreditoFinanceiroError, ValueError) as exc:
            return _friendly_error(exc)
        credito.refresh_from_db()
        return Response(
            CreditoFinanceiroSerializer(credito, context={'request': request, 'detail': True}).data,
        )

    @action(detail=True, methods=['post'], url_path='aplicar')
    def aplicar(self, request, pk=None):
        credito = self.get_object()
        ser = AplicarCreditoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        titulo = TituloFinanceiro.objects.filter(pk=d['titulo']).first()
        if not titulo:
            return _friendly_error(ValueError('Título não encontrado.'))
        try:
            baixa = aplicar_credito_em_titulo(
                credito,
                titulo,
                valor=d['valor'],
                data_aplicacao=d['data'],
                parcela_id=d.get('parcela'),
                motivo=d.get('motivo', ''),
                observacoes=d.get('observacoes', ''),
                usuario=request.user if request.user.is_authenticated else None,
            )
        except (CreditoFinanceiroError, ValueError) as exc:
            return _friendly_error(exc)
        credito.refresh_from_db()
        titulo.refresh_from_db()
        return Response({'baixa': BaixaFinanceiraSerializer(baixa).data, 'credito': CreditoFinanceiroSerializer(credito).data, 'titulo': _titulo_detail_data(titulo, request)})

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        credito = self.get_object()
        ser = CancelarCreditoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            credito = cancelar_credito_financeiro(credito, motivo=ser.validated_data['motivo'], usuario=request.user if request.user.is_authenticated else None)
        except (CreditoFinanceiroError, ValueError) as exc:
            return _friendly_error(exc)
        return Response(CreditoFinanceiroSerializer(credito).data)

    @action(detail=True, methods=['post'], url_path='excluir')
    def excluir(self, request, pk=None):
        credito = self.get_object()
        ser = ExcluirMotivoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            excluir_credito_financeiro(
                credito,
                motivo=ser.validated_data['motivo'],
                usuario=request.user if request.user.is_authenticated else None,
            )
        except (CreditoFinanceiroError, ValueError) as exc:
            return _friendly_error(exc)
        return Response({'mensagem': 'Crédito excluído com sucesso.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reembolsar')
    def reembolsar(self, request, pk=None):
        credito = self.get_object()
        ser = ReembolsoCreditoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            baixa = reembolsar_credito(
                credito,
                valor=d['valor'],
                data_reembolso=d['data'],
                conta_financeira_id=d['conta_financeira'],
                forma_pagamento_codigo=d['forma_pagamento_codigo'],
                observacoes=d['observacoes'],
                usuario=request.user if request.user.is_authenticated else None,
            )
        except (CreditoFinanceiroError, ValueError) as exc:
            return _friendly_error(exc)
        credito.refresh_from_db()
        return Response({'baixa': BaixaFinanceiraSerializer(baixa).data, 'credito': CreditoFinanceiroSerializer(credito).data})


class BaixaFinanceiraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BaixaFinanceira.objects.select_related('titulo', 'conta_financeira', 'credito').all()
    serializer_class = BaixaFinanceiraSerializer
    pagination_class = NexusPageNumberPagination

    @action(detail=True, methods=['post'], url_path='estornar')
    def estornar(self, request, pk=None):
        baixa = self.get_object()
        ser = EstornoBaixaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            estornar_baixa_financeira(baixa, motivo=ser.validated_data['motivo'], usuario=request.user if request.user.is_authenticated else None)
        except (BaixaFinanceiraError, ValueError) as exc:
            return _friendly_error(exc)
        baixa.refresh_from_db()
        titulo = baixa.titulo
        payload = {'baixa': BaixaFinanceiraSerializer(baixa).data}
        if titulo:
            titulo.refresh_from_db()
            payload['titulo'] = _titulo_detail_data(titulo, request)
        if baixa.credito_id:
            baixa.credito.refresh_from_db()
            payload['credito'] = CreditoFinanceiroSerializer(baixa.credito).data
        return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financeiro_formas_fixas(request):
    return Response({'formas_pagamento': formas_pagamento_api_payload(), 'tipos_movimento': tipos_movimento_api_payload()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financeiro_resumo_operacional(request):
    """ERP 4.0.14.5 — visão geral financeira operacional."""
    payload = montar_resumo_financeiro(
        periodo=request.query_params.get('periodo'),
        data_inicio=request.query_params.get('data_inicio'),
        data_fim=request.query_params.get('data_fim'),
    )
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financeiro_relatorio_contas_receber(request):
    return Response(relatorio_contas_receber(request.query_params))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financeiro_relatorio_contas_pagar(request):
    return Response(relatorio_contas_pagar(request.query_params))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financeiro_relatorio_fluxo_previsto(request):
    return Response(relatorio_fluxo_previsto(request.query_params))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financeiro_relatorio_categorias(request):
    return Response(relatorio_categorias(request.query_params))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financeiro_relatorio_clientes(request):
    return Response(relatorio_clientes(request.query_params))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financeiro_relatorio_fornecedores(request):
    return Response(relatorio_fornecedores(request.query_params))


_PDF_SLUGS = {
    pdf_relatorio_contas_receber: 'relatorio-contas-a-receber',
    pdf_relatorio_contas_pagar: 'relatorio-contas-a-pagar',
    pdf_relatorio_fluxo_previsto: 'fluxo-previsto',
    pdf_relatorio_categorias: 'receitas-despesas-categoria',
    pdf_relatorio_clientes: 'relatorio-por-cliente',
    pdf_relatorio_fornecedores: 'relatorio-por-fornecedor',
}


def _pdf_financeiro_response(request, builder):
    """PDF operacional — isolado do motor fiscal/DANFE."""
    try:
        content = builder(request.query_params, user=request.user)
    except Exception:
        logger.exception('financeiro_relatorio_pdf_falhou')
        return Response(
            {'detail': 'Não foi possível gerar o PDF do relatório. Tente novamente.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    slug = _PDF_SLUGS.get(builder, 'relatorio-financeiro')
    fname = f'{slug}-{timezone.localdate().isoformat()}.pdf'
    resp = pdf_http_response(content, filename=fname)
    # DRF: expor bytes para PdfBytesRenderer quando Accept: application/pdf
    return Response(
        resp.content,
        content_type='application/pdf',
        headers={
            'Content-Disposition': resp['Content-Disposition'],
            'Cache-Control': resp['Cache-Control'],
        },
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([PdfBytesRenderer])
def financeiro_relatorio_contas_receber_pdf(request):
    return _pdf_financeiro_response(request, pdf_relatorio_contas_receber)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([PdfBytesRenderer])
def financeiro_relatorio_contas_pagar_pdf(request):
    return _pdf_financeiro_response(request, pdf_relatorio_contas_pagar)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([PdfBytesRenderer])
def financeiro_relatorio_fluxo_previsto_pdf(request):
    return _pdf_financeiro_response(request, pdf_relatorio_fluxo_previsto)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([PdfBytesRenderer])
def financeiro_relatorio_categorias_pdf(request):
    return _pdf_financeiro_response(request, pdf_relatorio_categorias)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([PdfBytesRenderer])
def financeiro_relatorio_clientes_pdf(request):
    return _pdf_financeiro_response(request, pdf_relatorio_clientes)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([PdfBytesRenderer])
def financeiro_relatorio_fornecedores_pdf(request):
    return _pdf_financeiro_response(request, pdf_relatorio_fornecedores)
