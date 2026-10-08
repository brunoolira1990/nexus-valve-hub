from decimal import Decimal

from django.db.models import ProtectedError
from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin
from nexus_erp.view_mixins import FriendlyDestroyMixin
from nexus_erp.pagination import NexusPageNumberPagination

from apps.produtos.models import (
    FamiliaProduto,
    FamiliaProdutoPolegadaPermitida,
    FamiliaProdutoRoscaConexaoPermitida,
    FamiliaProdutoSchedulePermitido,
    Ncm,
    Polegada,
    Produto,
    RoscaConexao,
    ScheduleEspessura,
)
from apps.produtos.serializers import (
    ConverterMedidaSerializer,
    FamiliaProdutoSerializer,
    FamiliaProdutoPolegadaPermitidaSerializer,
    FamiliaProdutoRoscaConexaoPermitidaSerializer,
    FamiliaProdutoSchedulePermitidoSerializer,
    NcmSerializer,
    PolegadaSerializer,
    PreviewCodigoSerializer,
    ProdutoSerializer,
    RoscaConexaoSerializer,
    ScheduleEspessuraSerializer,
)
from django.db.models import Q, Value
from django.db.models.functions import Coalesce
from apps.produtos.polegadas import extract_mm_from_term
from apps.produtos.produto_busca import aplicar_filtro_busca_produto, produto_busca_rank
from apps.produtos.painel_operacional import montar_painel_resumo_produto
from apps.produtos.painel_rastreabilidade import montar_painel_rastreabilidade
from apps.produtos.sorting import (
    natural_codigo_completo_key,
    natural_codigo_figura_key,
    rosca_ordenacao_tuple,
    schedule_ordenacao_tuple,
)


def _familia_busca_rank(term: str, obj: FamiliaProduto) -> int:
    q = term.lower()
    cf = (obj.codigo_figura or '').lower()
    db = (obj.descricao_base or '').lower()
    if cf == q:
        return 0
    if cf.startswith(q):
        return 1
    if db.startswith(q):
        return 2
    if q in db:
        return 3
    if q in cf:
        return 4
    return 5


def _produto_busca_rank(term: str, obj: Produto) -> tuple[int, int, int, str]:
    return produto_busca_rank(term, obj)


class FamiliaProdutoViewSet(viewsets.ModelViewSet):
    queryset = FamiliaProduto.objects.prefetch_related(
        'polegadas_permitidas__polegada',
        'roscas_permitidas__rosca_conexao',
        'schedules_permitidos__schedule',
    ).select_related(
        'ncm_padrao',
    ).all()
    serializer_class = FamiliaProdutoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('search')
        if q:
            q = q.strip()
            qs = qs.filter(Q(codigo_figura__icontains=q) | Q(descricao_base__icontains=q))
        if self.request.query_params.get('apenas_ativas') == '1':
            qs = qs.filter(ativo=True)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        term = (request.query_params.get('search') or '').strip()
        rows = list(qs)
        if term:
            rows.sort(
                key=lambda o: (
                    _familia_busca_rank(term, o),
                    natural_codigo_figura_key(o.codigo_figura or ''),
                ),
            )
        else:
            rows.sort(key=lambda o: natural_codigo_figura_key(o.codigo_figura or ''))
        serializer = self.get_serializer(rows, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        familia = self.get_object()
        total_produtos = familia.produtos.count()
        if total_produtos:
            plural = 's' if total_produtos > 1 else ''
            return Response(
                {
                    'detail': (
                        f'Não é possível excluir a família {familia.codigo_figura}: '
                        f'existem {total_produtos} produto{plural} cadastrado{plural} nesta família. '
                        'Exclua ou mova os produtos antes de excluir a família.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            # Salvaguarda para FKs PROTECT futuras que não sejam Produto.
            modelos = sorted({obj._meta.verbose_name for obj in exc.protected_objects})
            vinculos = ', '.join(str(m) for m in modelos) or 'registros vinculados'
            return Response(
                {
                    'detail': (
                        f'Não é possível excluir a família {familia.codigo_figura}: '
                        f'existem vínculos de {vinculos} impedindo a exclusão.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class RoscaConexaoViewSet(viewsets.ModelViewSet):
    queryset = RoscaConexao.objects.all()
    serializer_class = RoscaConexaoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(codigo__icontains=search) | Q(descricao__icontains=search))
        if self.request.query_params.get('apenas_ativas') == '1':
            qs = qs.filter(ativo=True)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        rows = list(qs)
        rows.sort(key=lambda o: rosca_ordenacao_tuple(o.codigo or ''))
        lim = request.query_params.get('limit')
        if lim:
            try:
                rows = rows[: max(1, min(int(lim), 100))]
            except (TypeError, ValueError):
                pass
        return Response(self.get_serializer(rows, many=True).data)


class ScheduleEspessuraViewSet(viewsets.ModelViewSet):
    queryset = ScheduleEspessura.objects.all()
    serializer_class = ScheduleEspessuraSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(codigo_schedule__icontains=search)
                | Q(codigo__icontains=search)
                | Q(descricao__icontains=search)
                | Q(aplicacao__icontains=search),
            )
        if self.request.query_params.get('apenas_ativas') == '1':
            qs = qs.filter(ativo=True)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        rows = list(qs)
        rows.sort(
            key=lambda o: schedule_ordenacao_tuple(
                ordem=o.ordem,
                codigo_schedule=o.codigo_schedule or '',
                codigo=o.codigo or '',
            ),
        )
        lim = request.query_params.get('limit')
        if lim:
            try:
                rows = rows[: max(1, min(int(lim), 100))]
            except (TypeError, ValueError):
                pass
        return Response(self.get_serializer(rows, many=True).data)


class FamiliaProdutoPolegadaPermitidaViewSet(viewsets.ModelViewSet):
    queryset = FamiliaProdutoPolegadaPermitida.objects.select_related('familia', 'polegada').all()
    serializer_class = FamiliaProdutoPolegadaPermitidaSerializer


class FamiliaProdutoRoscaConexaoPermitidaViewSet(viewsets.ModelViewSet):
    queryset = FamiliaProdutoRoscaConexaoPermitida.objects.select_related('familia', 'rosca_conexao').all()
    serializer_class = FamiliaProdutoRoscaConexaoPermitidaSerializer


class FamiliaProdutoSchedulePermitidoViewSet(viewsets.ModelViewSet):
    queryset = FamiliaProdutoSchedulePermitido.objects.select_related('familia', 'schedule').all()
    serializer_class = FamiliaProdutoSchedulePermitidoSerializer


class ProdutoViewSet(FriendlyDestroyMixin, AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    destroy_entity_label = 'produto'
    queryset = Produto.objects.select_related(
        'familia',
        'familia__ncm_padrao',
        'rosca_conexao',
        'schedule_ref',
        'polegada_principal_ref',
        'polegada_secundaria_ref',
    ).all()
    serializer_class = ProdutoSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = aplicar_filtro_busca_produto(qs, search)
        if (self.request.query_params.get('sem_ncm') or '').strip() in ('1', 'true', 'True'):
            qs = qs.filter(Q(ncm='') | Q(ncm__isnull=True))
        material = (self.request.query_params.get('material') or '').strip()
        if material:
            qs = qs.filter(material__icontains=material)
        return qs

    def list(self, request, *args, **kwargs):
        limit = (request.query_params.get('limit') or '').strip()
        page = (request.query_params.get('page') or '').strip()
        if limit and not page:
            qs = self.filter_queryset(self.get_queryset())
            term = (request.query_params.get('search') or '').strip()
            try:
                lim = max(1, min(int(limit), 100))
            except (TypeError, ValueError):
                lim = 20
            rows = list(qs)
            if term:
                rows.sort(
                    key=lambda o: (
                        _produto_busca_rank(term, o),
                        natural_codigo_completo_key(o.codigo_completo or ''),
                    ),
                )
            else:
                rows.sort(key=lambda o: natural_codigo_completo_key(o.codigo_completo or ''))
            rows = rows[:lim]
            return Response(self.get_serializer(rows, many=True).data)

        qs = self.filter_queryset(self.get_queryset())
        term = (request.query_params.get('search') or '').strip()
        rows = list(qs)
        if term:
            rows.sort(
                key=lambda o: (
                    _produto_busca_rank(term, o),
                    natural_codigo_completo_key(o.codigo_completo or ''),
                ),
            )
        else:
            rows.sort(key=lambda o: natural_codigo_completo_key(o.codigo_completo or ''))
        page_rows = self.paginate_queryset(rows)
        if page_rows is not None:
            serializer = self.get_serializer(page_rows, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(rows, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='preview-codigo')
    def preview_codigo(self, request):
        ser = PreviewCodigoSerializer(data=request.data)
        if not ser.is_valid():
            err = ser.errors
            msg = 'Ajuste os campos para prévia do código.'
            if isinstance(err, dict):
                for v in err.values():
                    if isinstance(v, (list, tuple)) and v:
                        msg = str(v[0])
                        break
                    if isinstance(v, dict):
                        for w in v.values():
                            if isinstance(w, (list, tuple)) and w:
                                msg = str(w[0])
                                break
            return Response({'codigo': '', 'descricao_sugerida': '', 'mensagem': msg})
        v = ser.validated_data
        return Response(
            {
                'codigo': v.get('_codigo', ''),
                'codigo_base': v.get('_codigo_base', v.get('_codigo', '')),
                'sequencia_tecnica': bool(v.get('_sequencia_tecnica', False)),
                'descricao_sugerida': v.get('_descricao', ''),
                'mensagem': v.get('_mensagem', ''),
                'ncm_efetivo': v.get('_ncm_efetivo', ''),
                'unidade_efetiva': v.get('_unidade_efetiva', ''),
                'origem_ncm': v.get('_origem_ncm', 'familia'),
                'origem_unidade': v.get('_origem_unidade', 'familia'),
                'mensagens': v.get('_mensagens', []),
            },
        )

    @action(detail=False, methods=['post'], url_path='converter-medida')
    def converter_medida(self, request):
        ser = ConverterMedidaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        r = v['_resultado']
        return Response(
            {
                'produto_id': v['produto'].id,
                'quantidade_origem': str(r.quantidade_origem),
                'unidade_origem': r.unidade_origem,
                'quantidade_destino': str(r.quantidade_destino),
                'unidade_destino': r.unidade_destino,
                'peso_kg': str(r.peso_kg) if r.peso_kg is not None else None,
                'metros': str(r.metros) if r.metros is not None else None,
                'barras': str(r.barras) if r.barras is not None else None,
                'unidade_estoque': v['produto'].get_unidade_estoque_efetiva(),
                'mensagem': r.mensagem,
            },
        )

    @action(detail=True, methods=['get'], url_path='painel/resumo')
    def painel_resumo(self, request, pk=None):
        produto = self.get_object()
        return Response(montar_painel_resumo_produto(produto))

    @action(detail=True, methods=['get'], url_path='painel/rastreabilidade')
    def painel_rastreabilidade(self, request, pk=None):
        produto = self.get_object()
        return JsonResponse(montar_painel_rastreabilidade(produto))


class PolegadaViewSet(viewsets.ModelViewSet):
    queryset = Polegada.objects.all()
    serializer_class = PolegadaSerializer

    def get_queryset(self):
        hi = Decimal('999999999')
        qs = (
            super()
            .get_queryset()
            .annotate(
                _sort_vd=Coalesce('valor_decimal', Value(hi)),
                _sort_mm=Coalesce('valor_mm', Value(hi)),
            )
            .order_by('tipo_medida', '_sort_vd', '_sort_mm', 'codigo_oficial')
        )
        tipo_medida = (self.request.query_params.get('tipo_medida') or '').strip().upper()
        if tipo_medida in {Polegada.TipoMedida.NPS, Polegada.TipoMedida.OD}:
            qs = qs.filter(tipo_medida=tipo_medida)
        if self.request.query_params.get('ativo') is None:
            qs = qs.filter(ativo=True)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            query = (
                Q(codigo_oficial__icontains=search)
                | Q(codigo__icontains=search)
                | Q(descricao__icontains=search)
                | Q(aliases__icontains=search)
            )
            mm = extract_mm_from_term(search)
            if mm is not None and (not tipo_medida or tipo_medida == Polegada.TipoMedida.OD):
                tol = Decimal('0.05')
                query = query | Q(valor_mm__gte=mm - tol, valor_mm__lte=mm + tol)
            qs = qs.filter(query)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        lim = request.query_params.get('limit')
        rows = list(qs)
        if lim:
            try:
                rows = rows[: max(1, min(int(lim), 100))]
            except (TypeError, ValueError):
                pass
        return Response(self.get_serializer(rows, many=True).data)


class NcmViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ncm.objects.all()
    serializer_class = NcmSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('codigo')
        ativo_param = self.request.query_params.get('ativo')
        if ativo_param is None:
            qs = qs.filter(ativo=True)
        else:
            flag = str(ativo_param).strip().lower() in {'1', 'true', 'sim', 'yes'}
            qs = qs.filter(ativo=flag)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            from django.db.models import Q

            qs = qs.filter(Q(codigo__icontains=search) | Q(descricao__icontains=search))
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                max_items = max(1, min(int(limit), 100))
                qs = qs[:max_items]
            except (TypeError, ValueError):
                pass
        return qs
