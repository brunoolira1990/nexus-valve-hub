from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination

from .cenario_fiscal_entrada import (
    copiar_configuracao_escopo,
    duplicar_regra_fiscal_entrada,
    garantir_cenarios_entrada_para_api,
    montar_matriz_escopo,
)
from .cenario_fiscal_saida import garantir_cenarios_saida_para_api, montar_matriz_escopo_saida
from .models import (
    CenarioFiscalEntrada,
    CenarioFiscalEntradaEscopo,
    CenarioFiscalSaida,
    CenarioFiscalSaidaEscopo,
    RegraFiscal,
    RegraFiscalEntrada,
    RegraFiscalSaida,
)
from .serializers import (
    CenarioFiscalEntradaDetailSerializer,
    CenarioFiscalEntradaEscopoSerializer,
    CenarioFiscalEntradaSerializer,
    CenarioFiscalSaidaDetailSerializer,
    CenarioFiscalSaidaEscopoSerializer,
    CenarioFiscalSaidaSerializer,
    CopiarConfiguracaoEscopoSerializer,
    DuplicarRegraFiscalEntradaSerializer,
    RegraFiscalEntradaSerializer,
    RegraFiscalSaidaSerializer,
    RegraFiscalSerializer,
)


class RegraFiscalViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = RegraFiscal.objects.all()
    serializer_class = RegraFiscalSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(ncm__icontains=search)
                | Q(cfop__icontains=search)
                | Q(cst_icms__icontains=search)
                | Q(cst_pis__icontains=search)
                | Q(operacao__icontains=search),
            )
        ncm = (self.request.query_params.get('ncm') or '').strip()
        if ncm:
            qs = qs.filter(ncm__icontains=ncm)
        cfop = (self.request.query_params.get('cfop') or '').strip()
        if cfop:
            qs = qs.filter(cfop__icontains=cfop)
        operacao = (self.request.query_params.get('operacao') or '').strip()
        if operacao:
            qs = qs.filter(operacao__icontains=operacao)
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'ncm': 'ncm', 'cfop': 'cfop', 'operacao': 'operacao'},
            'ncm',
        )

    @action(detail=False, methods=['get'], url_path='buscar')
    def buscar(self, request):
        ncm = request.query_params.get('ncm', '').strip()
        uf_origem = request.query_params.get('uf_origem', '').strip().upper()
        uf_destino = request.query_params.get('uf_destino', '').strip().upper()
        operacao = request.query_params.get('operacao', '').strip()
        if not all([ncm, uf_origem, uf_destino, operacao]):
            return Response(
                {'detail': 'Informe ncm, uf_origem, uf_destino e operacao.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        regra = RegraFiscal.objects.filter(
            ncm=ncm,
            uf_origem=uf_origem,
            uf_destino=uf_destino,
            operacao=operacao,
        ).first()
        if not regra:
            return Response({'detail': 'Nenhuma regra encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RegraFiscalSerializer(regra).data)

    @action(detail=False, methods=['get'], url_path='checklist-producao')
    def checklist_producao(self, request):
        from apps.regras_fiscais.regras_fiscais_minimas import validar_regras_fiscais_minimas

        return Response(validar_regras_fiscais_minimas())


class RegraFiscalEntradaViewSet(viewsets.ModelViewSet):
    queryset = RegraFiscalEntrada.objects.select_related(
        'produto',
        'fornecedor',
        'cenario',
        'escopo',
    ).all()
    serializer_class = RegraFiscalEntradaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        escopo_id = self.request.query_params.get('escopo_id')
        if escopo_id:
            qs = qs.filter(escopo_id=escopo_id)
        cenario_id = self.request.query_params.get('cenario_id')
        if cenario_id:
            qs = qs.filter(cenario_id=cenario_id)
        return qs

    @action(detail=True, methods=['post'], url_path='duplicar')
    def duplicar(self, request, pk=None):
        regra = self.get_object()
        serializer = DuplicarRegraFiscalEntradaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        destino = {
            k: data[k]
            for k in ('uf_origem', 'uf_destino', 'cfop_origem', 'cfop_entrada')
            if k in data
        }
        try:
            nova = duplicar_regra_fiscal_entrada(
                regra.id,
                destino,
                sobrescrever=data.get('sobrescrever', False),
            )
        except DjangoValidationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            RegraFiscalEntradaSerializer(nova).data,
            status=status.HTTP_201_CREATED,
        )


class CenarioFiscalEntradaViewSet(viewsets.ReadOnlyModelViewSet):
    """Lista e detalha cenários fiscais de entrada; escopos via actions."""

    serializer_class = CenarioFiscalEntradaSerializer

    def get_queryset(self):
        return (
            CenarioFiscalEntrada.objects.select_related('empresa')
            .annotate(
                total_escopos=Count('escopos', distinct=True),
                total_configuracoes=Count('escopos__configuracoes', distinct=True),
            )
            .order_by('-padrao', 'nome', 'id')
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CenarioFiscalEntradaDetailSerializer
        return CenarioFiscalEntradaSerializer

    def list(self, request, *args, **kwargs):
        garantir_cenarios_entrada_para_api()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        garantir_cenarios_entrada_para_api()
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['get', 'post'], url_path='escopos')
    def escopos(self, request, pk=None):
        cenario = self.get_object()
        if request.method == 'GET':
            qs = (
                cenario.escopos.annotate(configuracoes_count=Count('configuracoes'))
                .order_by('tipo_escopo', 'ncm', 'produto_id', 'id')
            )
            return Response(CenarioFiscalEntradaEscopoSerializer(qs, many=True).data)

        serializer = CenarioFiscalEntradaEscopoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        escopo = serializer.save(cenario=cenario)
        return Response(
            CenarioFiscalEntradaEscopoSerializer(escopo).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path=r'escopos/(?P<escopo_id>[^/.]+)/configuracoes',
    )
    def configuracoes_escopo(self, request, pk=None, escopo_id=None):
        cenario = self.get_object()
        escopo = get_object_or_404(CenarioFiscalEntradaEscopo, pk=escopo_id, cenario=cenario)
        qs = RegraFiscalEntrada.objects.filter(escopo=escopo).select_related('produto', 'fornecedor')
        return Response(RegraFiscalEntradaSerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=['get'],
        url_path=r'escopos/(?P<escopo_id>[^/.]+)/matriz',
    )
    def matriz_escopo(self, request, pk=None, escopo_id=None):
        cenario = self.get_object()
        escopo = get_object_or_404(CenarioFiscalEntradaEscopo, pk=escopo_id, cenario=cenario)
        return Response(montar_matriz_escopo(escopo))

    @action(
        detail=True,
        methods=['post'],
        url_path=r'escopos/(?P<escopo_id>[^/.]+)/copiar-configuracao',
    )
    def copiar_configuracao(self, request, pk=None, escopo_id=None):
        cenario = self.get_object()
        escopo = get_object_or_404(CenarioFiscalEntradaEscopo, pk=escopo_id, cenario=cenario)
        serializer = CopiarConfiguracaoEscopoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            resultado = copiar_configuracao_escopo(
                escopo,
                origem_regra_id=data['origem_regra_id'],
                destinos=data['destinos'],
                sobrescrever=data.get('sobrescrever', False),
            )
        except RegraFiscalEntrada.DoesNotExist as exc:
            raise ValidationError('Regra de origem não pertence a este escopo.') from exc
        return Response(resultado)


def _parse_params_busca_regra_fiscal_saida(request):
    """Extrai parâmetros comuns de busca/comparativo de regra fiscal de saída."""
    uf_origem = request.query_params.get('uf_origem', '').strip().upper()
    uf_destino = request.query_params.get('uf_destino', '').strip().upper()
    if not uf_origem or not uf_destino:
        return None, 'Informe uf_origem e uf_destino.'

    produto_id = request.query_params.get('produto_id', '').strip()
    ncm = request.query_params.get('ncm', '').strip()
    dest = request.query_params.get('destinatario_contribuinte', '').strip().upper() or None
    tipo_op = request.query_params.get('tipo_operacao', 'VENDA').strip() or 'VENDA'
    cenario_id = request.query_params.get('cenario_id', '').strip()
    cf_raw = request.query_params.get('consumidor_final', '').strip().lower()
    consumidor_final = None
    if cf_raw in ('1', 'true', 'sim', 'yes'):
        consumidor_final = True
    elif cf_raw in ('0', 'false', 'nao', 'não', 'no'):
        consumidor_final = False

    return {
        'produto_id': int(produto_id) if produto_id.isdigit() else None,
        'ncm': ncm,
        'uf_origem': uf_origem,
        'uf_destino': uf_destino,
        'destinatario_contribuinte': dest,
        'consumidor_final': consumidor_final,
        'tipo_operacao': tipo_op,
        'cenario_id': int(cenario_id) if cenario_id.isdigit() else None,
    }, None


class RegraFiscalSaidaViewSet(viewsets.ModelViewSet):
    queryset = RegraFiscalSaida.objects.select_related('cenario', 'escopo').all()
    serializer_class = RegraFiscalSaidaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        escopo_id = self.request.query_params.get('escopo_id')
        if escopo_id:
            qs = qs.filter(escopo_id=escopo_id)
        cenario_id = self.request.query_params.get('cenario_id')
        if cenario_id:
            qs = qs.filter(cenario_id=cenario_id)
        return qs

    @action(detail=False, methods=['get'], url_path='buscar')
    def buscar(self, request):
        from apps.regras_fiscais.saida_fiscal import buscar_regra_fiscal_saida

        params, erro = _parse_params_busca_regra_fiscal_saida(request)
        if erro:
            return Response({'detail': erro}, status=status.HTTP_400_BAD_REQUEST)

        resultado = buscar_regra_fiscal_saida(**params)
        if resultado['origem'] == 'NAO_ENCONTRADA':
            return Response(resultado, status=status.HTTP_404_NOT_FOUND)
        return Response(resultado)

    @action(detail=False, methods=['get'], url_path='comparar')
    def comparar(self, request):
        from apps.regras_fiscais.saida_fiscal import comparar_regra_fiscal_saida_legado_cenario

        params, erro = _parse_params_busca_regra_fiscal_saida(request)
        if erro:
            return Response({'detail': erro}, status=status.HTTP_400_BAD_REQUEST)

        resultado = comparar_regra_fiscal_saida_legado_cenario(**params)
        return Response(resultado)

    @action(detail=False, methods=['get'], url_path='cobertura-propostas')
    def cobertura_propostas(self, request):
        from apps.regras_fiscais.saida_fiscal import (
            cobertura_propostas_fiscal_saida,
            parse_filtros_cobertura_propostas_request,
        )

        filtros, erro = parse_filtros_cobertura_propostas_request(request)
        if erro:
            return Response({'detail': erro}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultado = cobertura_propostas_fiscal_saida(**filtros)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)

    @action(detail=False, methods=['get'], url_path='checklist-ativacao')
    def checklist_ativacao(self, request):
        from apps.regras_fiscais.saida_fiscal import (
            avaliar_prontidao_ativacao_cenario_saida,
            parse_filtros_cobertura_propostas_request,
        )

        filtros, erro = parse_filtros_cobertura_propostas_request(request)
        if erro:
            return Response({'detail': erro}, status=status.HTTP_400_BAD_REQUEST)
        filtros_checklist = {
            k: filtros[k]
            for k in (
                'data_inicial',
                'data_final',
                'proposta_id',
                'cliente_id',
                'status_proposta',
                'ncm',
                'uf_origem',
                'uf_destino',
                'limite',
                'max_scan',
                'cenario_id',
            )
            if k in filtros
        }
        try:
            resultado = avaliar_prontidao_ativacao_cenario_saida(**filtros_checklist)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)


class CenarioFiscalSaidaViewSet(viewsets.ReadOnlyModelViewSet):
    """Lista e detalha cenários fiscais de saída; escopos via actions."""

    serializer_class = CenarioFiscalSaidaSerializer

    def get_queryset(self):
        return (
            CenarioFiscalSaida.objects.select_related('empresa')
            .annotate(
                total_escopos=Count('escopos', distinct=True),
                total_configuracoes=Count('escopos__configuracoes', distinct=True),
            )
            .order_by('-padrao', 'nome', 'id')
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CenarioFiscalSaidaDetailSerializer
        return CenarioFiscalSaidaSerializer

    def list(self, request, *args, **kwargs):
        garantir_cenarios_saida_para_api()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        garantir_cenarios_saida_para_api()
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['get', 'post'], url_path='escopos')
    def escopos(self, request, pk=None):
        cenario = self.get_object()
        if request.method == 'GET':
            qs = (
                cenario.escopos.annotate(configuracoes_count=Count('configuracoes'))
                .order_by('tipo_escopo', 'ncm', 'produto_id', 'id')
            )
            return Response(CenarioFiscalSaidaEscopoSerializer(qs, many=True).data)

        serializer = CenarioFiscalSaidaEscopoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        escopo = serializer.save(cenario=cenario)
        return Response(
            CenarioFiscalSaidaEscopoSerializer(escopo).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path=r'escopos/(?P<escopo_id>[^/.]+)/configuracoes',
    )
    def configuracoes_escopo(self, request, pk=None, escopo_id=None):
        cenario = self.get_object()
        escopo = get_object_or_404(CenarioFiscalSaidaEscopo, pk=escopo_id, cenario=cenario)
        qs = RegraFiscalSaida.objects.filter(escopo=escopo).select_related('cenario', 'escopo')
        return Response(RegraFiscalSaidaSerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=['get'],
        url_path=r'escopos/(?P<escopo_id>[^/.]+)/matriz',
    )
    def matriz_escopo(self, request, pk=None, escopo_id=None):
        cenario = self.get_object()
        escopo = get_object_or_404(CenarioFiscalSaidaEscopo, pk=escopo_id, cenario=cenario)
        return Response(montar_matriz_escopo_saida(escopo))
