from decimal import Decimal

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

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
from django.db.models import Case, IntegerField, Q, Value, When
from apps.produtos.polegadas import extract_mm_from_term


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
        return qs.order_by('codigo_figura')


class RoscaConexaoViewSet(viewsets.ModelViewSet):
    queryset = RoscaConexao.objects.all()
    serializer_class = RoscaConexaoSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('codigo')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(codigo__icontains=search) | Q(descricao__icontains=search))
        if self.request.query_params.get('apenas_ativas') == '1':
            qs = qs.filter(ativo=True)
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs


class ScheduleEspessuraViewSet(viewsets.ModelViewSet):
    queryset = ScheduleEspessura.objects.all()
    serializer_class = ScheduleEspessuraSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('ordem', 'codigo_schedule')
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
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs


class FamiliaProdutoPolegadaPermitidaViewSet(viewsets.ModelViewSet):
    queryset = FamiliaProdutoPolegadaPermitida.objects.select_related('familia', 'polegada').all()
    serializer_class = FamiliaProdutoPolegadaPermitidaSerializer


class FamiliaProdutoRoscaConexaoPermitidaViewSet(viewsets.ModelViewSet):
    queryset = FamiliaProdutoRoscaConexaoPermitida.objects.select_related('familia', 'rosca_conexao').all()
    serializer_class = FamiliaProdutoRoscaConexaoPermitidaSerializer


class FamiliaProdutoSchedulePermitidoViewSet(viewsets.ModelViewSet):
    queryset = FamiliaProdutoSchedulePermitido.objects.select_related('familia', 'schedule').all()
    serializer_class = FamiliaProdutoSchedulePermitidoSerializer


class ProdutoViewSet(viewsets.ModelViewSet):
    queryset = Produto.objects.select_related(
        'familia',
        'familia__ncm_padrao',
        'rosca_conexao',
        'schedule_ref',
        'polegada_principal_ref',
        'polegada_secundaria_ref',
    ).all()
    serializer_class = ProdutoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        limit_raw = self.request.query_params.get('limit')
        lim = None
        if limit_raw:
            try:
                lim = max(1, min(int(limit_raw), 100))
            except (TypeError, ValueError):
                lim = None

        if search:
            qs = qs.filter(
                Q(codigo_completo__icontains=search)
                | Q(descricao__icontains=search)
                | Q(material__icontains=search)
                | Q(norma__icontains=search)
                | Q(ncm__icontains=search)
                | Q(figura__icontains=search)
                | Q(sufixo__icontains=search)
                | Q(schedule__icontains=search)
                | Q(polegada_principal__icontains=search)
                | Q(polegada_secundaria__icontains=search)
                | Q(tipo_peca__icontains=search)
                | Q(conexao__icontains=search)
                | Q(familia__codigo_figura__icontains=search)
                | Q(familia__descricao_base__icontains=search)
                | Q(familia__ncm_padrao__codigo__icontains=search)
            )
            if lim is not None:
                qs = (
                    qs.annotate(
                        _search_rank=Case(
                            When(codigo_completo__iexact=search, then=Value(0)),
                            When(codigo_completo__istartswith=search, then=Value(1)),
                            default=Value(2),
                            output_field=IntegerField(),
                        )
                    )
                    .order_by('_search_rank', 'codigo_completo')[:lim]
                )
                return qs
            qs = qs.order_by('-id')
        else:
            qs = qs.order_by('-id')

        if lim is not None:
            qs = qs[:lim]
        return qs

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


class PolegadaViewSet(viewsets.ModelViewSet):
    queryset = Polegada.objects.all()
    serializer_class = PolegadaSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('valor_decimal')
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
                tol =  Decimal('0.05')
                query = query | Q(valor_mm__gte=mm - tol, valor_mm__lte=mm + tol)
            qs = qs.filter(query)
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs


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
