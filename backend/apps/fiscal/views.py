from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import response, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from apps.qualidade.models import Certificado
from apps.produtos.models import Produto

from .estoque_services import reverter_todos_itens_entrada, reverter_todos_itens_saida
from .cte_import.service import importar_arquivos_cte
from .consolidado_historico_gerencial import (
    agrupar_cte_por_transportadora,
    agrupar_cte_por_mes,
    agrupar_cte_por_trimestre,
    consolidar_queryset_cte,
    queryset_cte_historico_logistico,
    separar_totais_e_indicadores_cte,
)
from .models import (
    CTeEntrada,
    CTeHistoricoImportado,
    EstoqueCorrida,
    EventoNFeSaidaHistoricaPendente,
    NFeEntrada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)
from .serializers import ItemNFeEntradaConferenciaSerializer
from .saldo_dimensional import calcular_saldo_dimensional
from .nfe_historica_entrada_fiscal import (
    agrupar_por_mes_entrada,
    agrupar_por_trimestre_entrada,
    consolidar_queryset_entrada,
    queryset_compras_nf_entrada_historica,
    separar_totais_e_indicadores_entrada,
)
from .nfe_historica_fiscal import (
    agrupar_por_mes,
    agrupar_por_trimestre,
    consolidar_queryset,
    queryset_faturamento_nf_saida_historica,
    separar_totais_e_indicadores,
)
from .nfe_historica_periodo import PeriodoInvalido, aplicar_filtros_vinculo, bounds_para_listagem, resolver_periodo
from .nfe_import.service_entrada import importar_arquivos_entrada
from .nfe_import.service import importar_arquivos, reprocessar_eventos_pendentes_saida
from .serializers import (
    CTeEntradaSerializer,
    CTeHistoricoImportadoListSerializer,
    CTeHistoricoImportadoSerializer,
    NFeEntradaSerializer,
    NFeEntradaHistoricaImportadaListSerializer,
    NFeEntradaHistoricaImportadaSerializer,
    NFeEntradaConferenciaSerializer,
    EventoNFeSaidaHistoricaPendenteSerializer,
    NFeSaidaHistoricaImportadaListSerializer,
    NFeSaidaHistoricaImportadaSerializer,
    NFeSaidaSerializer,
)


def _dec(v):
    return Decimal(str(v)) if v is not None else Decimal('0')


def _extract_item_nf(prod_json: dict) -> dict:
    return {
        'unidade_nf': (prod_json.get('uCom') or prod_json.get('uTrib') or '').upper(),
        'quantidade_nf': _dec(prod_json.get('qCom') or prod_json.get('qTrib') or 0),
        'valor_unitario_nf': _dec(prod_json.get('vUnCom') or prod_json.get('vUnTrib') or 0),
        'valor_total_nf': _dec(prod_json.get('vProd') or 0),
    }


class NFeEntradaViewSet(viewsets.ModelViewSet):
    queryset = (
        NFeEntrada.objects.select_related('fornecedor', 'pedido_compra', 'cte')
        .prefetch_related('itens__produto', 'itens__corrida')
        .all()
    )
    serializer_class = NFeEntradaSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        reverter_todos_itens_entrada(instance)
        instance.delete()


class NFeSaidaViewSet(viewsets.ModelViewSet):
    queryset = (
        NFeSaida.objects.select_related('cliente', 'pedido_venda')
        .prefetch_related('itens__produto', 'itens__corrida')
        .all()
    )
    serializer_class = NFeSaidaSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        reverter_todos_itens_saida(instance)
        Certificado.objects.filter(nf_saida=instance).delete()
        instance.delete()


class NFeSaidaHistoricaImportadaViewSet(viewsets.ReadOnlyModelViewSet):
    """NF-e de saída importadas por XML (origem externa, não reemitíveis pelo ERP)."""

    queryset = NFeSaidaHistoricaImportada.objects.select_related('empresa_emitente', 'cliente').all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        incluir_canceladas = str(self.request.query_params.get('incluir_canceladas', '')).lower() in {'1', 'true', 'sim'}
        if not incluir_canceladas:
            qs = qs.filter(cancelada=False)
        if self.action == 'retrieve':
            return qs.prefetch_related('itens', 'eventos')
        if self.action == 'list':
            qs = qs.prefetch_related('eventos')
            p = self.request.query_params
            try:
                bounds = bounds_para_listagem(p)
            except PeriodoInvalido as exc:
                raise ValidationError({'detail': str(exc)}) from exc
            if bounds:
                di, df = bounds
                qs = qs.filter(dh_emissao__date__gte=di, dh_emissao__date__lte=df)
            try:
                qs = aplicar_filtros_vinculo(
                    qs,
                    p.get('cliente_id'),
                    p.get('empresa_emitente_id'),
                )
            except PeriodoInvalido as exc:
                raise ValidationError({'detail': str(exc)}) from exc
            # Painel de faturamento: apenas vendas com emitente = Empresa ERP (omitir param = auditoria / histórico completo)
            if str(p.get('apenas_faturamento_emitente_erp', '')).lower() in {'1', 'true', 'sim'}:
                qs = queryset_faturamento_nf_saida_historica(qs)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return NFeSaidaHistoricaImportadaListSerializer
        return NFeSaidaHistoricaImportadaSerializer

    def _base_historica_filtrada(self, request):
        try:
            di, df, meta = resolver_periodo(request.query_params)
        except PeriodoInvalido as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        qs = NFeSaidaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
        )
        incluir_canceladas = str(request.query_params.get('incluir_canceladas', '')).lower() in {'1', 'true', 'sim'}
        if not incluir_canceladas:
            qs = qs.filter(cancelada=False)
        try:
            qs = aplicar_filtros_vinculo(
                qs,
                request.query_params.get('cliente_id'),
                request.query_params.get('empresa_emitente_id'),
            )
        except PeriodoInvalido as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        qs = queryset_faturamento_nf_saida_historica(qs)
        return qs, di, df, meta

    @action(detail=False, methods=['get'], url_path='eventos-pendentes')
    def eventos_pendentes(self, request):
        try:
            limite = int(request.query_params.get('limit', '500'))
        except ValueError:
            limite = 500
        limite = max(1, min(limite, 2000))
        qs = (
            EventoNFeSaidaHistoricaPendente.objects.filter(status=EventoNFeSaidaHistoricaPendente.Status.PENDENTE)
            .order_by('-criado_em')[:limite]
        )
        return response.Response(EventoNFeSaidaHistoricaPendenteSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='reprocessar-eventos-pendentes')
    def reprocessar_eventos_pendentes(self, request):
        out = reprocessar_eventos_pendentes_saida()
        return response.Response(out, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='resumo-fiscal')
    def resumo_fiscal(self, request):
        """Consolidado de faturamento (vendas): apenas NF-e em que o emitente do XML = Empresa cadastrada."""
        qs, di, df, meta = self._base_historica_filtrada(request)
        linha = consolidar_queryset(qs)
        tot, ind = separar_totais_e_indicadores(linha)
        return response.Response(
            {
                'origem_dados': 'nf_saida_historica_importada',
                'tipo_fluxo': 'saida',
                'escopo_faturamento': (
                    'Somente NF-e cuja empresa emitente do XML foi reconhecida no cadastro Empresa '
                    '(vendas da empresa). Compras/fornecedor devem usar NF-e de entrada histórica.'
                ),
                'periodo': {
                    'data_inicio': di.isoformat(),
                    'data_fim': df.isoformat(),
                    **meta,
                },
                'filtros': {
                    'cliente_id': request.query_params.get('cliente_id'),
                    'empresa_emitente_id': request.query_params.get('empresa_emitente_id'),
                    'incluir_canceladas': str(request.query_params.get('incluir_canceladas', '')).lower()
                    in {'1', 'true', 'sim'},
                    'apenas_faturamento_emitente_erp': True,
                },
                'totais': tot,
                'indicadores_gerenciais': ind,
                'irpj_csll': {
                    'observacao': (
                        'IRPJ e CSLL não são calculados nem extraídos do XML nesta fase. '
                        'O faturamento consolidado alimenta apenas estimativas gerenciais futuras.'
                    )
                },
                'reforma_tributaria': {
                    'observacao': (
                        'CBS/IBS/IS na apuração: totais consolidados (NF-e + CT-e) e detalhe em reforma_tributaria.por_documento '
                        '(entrada, saida, cte).'
                    ),
                },
            }
        )

    @action(detail=False, methods=['get'], url_path='apuracao-mensal')
    def apuracao_mensal(self, request):
        qs, di, df, meta = self._base_historica_filtrada(request)
        return response.Response(
            {
                'origem_dados': 'nf_saida_historica_importada',
                'tipo_fluxo': 'saida',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'meses': agrupar_por_mes(qs),
            }
        )

    @action(detail=False, methods=['get'], url_path='apuracao-trimestral')
    def apuracao_trimestral(self, request):
        qs, di, df, meta = self._base_historica_filtrada(request)
        return response.Response(
            {
                'origem_dados': 'nf_saida_historica_importada',
                'tipo_fluxo': 'saida',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'trimestres': agrupar_por_trimestre(qs),
            }
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='importar-xml',
        parser_classes=[MultiPartParser],
    )
    def importar_xml(self, request):
        files = request.FILES.getlist('arquivos')
        if not files:
            single = request.FILES.get('arquivo')
            if single:
                files = [single]
        if not files:
            return response.Response(
                {'detail': 'Envie um ou mais arquivos no campo "arquivos" (multipart/form-data).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        batch: list[tuple[str, bytes]] = []
        for f in files:
            raw = f.read()
            batch.append((getattr(f, 'name', '') or 'nota.xml', raw))
        result = importar_arquivos(batch)
        return response.Response(result, status=status.HTTP_200_OK)


class NFeEntradaHistoricaImportadaViewSet(viewsets.ReadOnlyModelViewSet):
    """NF-e de entrada importadas por XML (origem externa, base fiscal/gerencial)."""

    queryset = NFeEntradaHistoricaImportada.objects.select_related('empresa_destinataria', 'fornecedor_emitente').all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'retrieve':
            return qs.prefetch_related('itens')
        if self.action == 'list':
            p = self.request.query_params
            try:
                bounds = bounds_para_listagem(p)
            except PeriodoInvalido as exc:
                raise ValidationError({'detail': str(exc)}) from exc
            if bounds:
                di, df = bounds
                qs = qs.filter(dh_emissao__date__gte=di, dh_emissao__date__lte=df)
            if p.get('empresa_destinataria_id'):
                try:
                    eid = int(p.get('empresa_destinataria_id') or '0')
                except ValueError:
                    raise ValidationError({'detail': 'empresa_destinataria_id inválido.'}) from None
                qs = qs.filter(empresa_destinataria_id=eid)
            if p.get('fornecedor_id'):
                try:
                    fid = int(p.get('fornecedor_id') or '0')
                except ValueError:
                    raise ValidationError({'detail': 'fornecedor_id inválido.'}) from None
                qs = qs.filter(fornecedor_emitente_id=fid)
            if str(p.get('apenas_compras_destinatario_erp', '')).lower() in {'1', 'true', 'sim'}:
                qs = queryset_compras_nf_entrada_historica(qs)
            qs = qs.select_related('conferencia')
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return NFeEntradaHistoricaImportadaListSerializer
        return NFeEntradaHistoricaImportadaSerializer

    def _base_entrada_historica_filtrada(self, request):
        try:
            di, df, meta = resolver_periodo(request.query_params)
        except PeriodoInvalido as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        qs = NFeEntradaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
        )
        qs = queryset_compras_nf_entrada_historica(qs)
        p = request.query_params
        if p.get('empresa_destinataria_id'):
            try:
                eid = int(p.get('empresa_destinataria_id') or '0')
            except ValueError:
                raise ValidationError({'detail': 'empresa_destinataria_id inválido.'}) from None
            qs = qs.filter(empresa_destinataria_id=eid)
        if p.get('fornecedor_id'):
            try:
                fid = int(p.get('fornecedor_id') or '0')
            except ValueError:
                raise ValidationError({'detail': 'fornecedor_id inválido.'}) from None
            qs = qs.filter(fornecedor_emitente_id=fid)
        return qs, di, df, meta

    @action(detail=False, methods=['get'], url_path='resumo-fiscal-entrada')
    def resumo_fiscal_entrada(self, request):
        """Compras/custo: apenas NF-e em que o destinatário do XML = Empresa cadastrada."""
        qs, di, df, meta = self._base_entrada_historica_filtrada(request)
        linha = consolidar_queryset_entrada(qs)
        tot, ind = separar_totais_e_indicadores_entrada(linha)
        return response.Response(
            {
                'origem_dados': 'nf_entrada_historica_importada',
                'tipo_fluxo': 'entrada',
                'escopo': 'Compras documentais (destinatário = empresa); não é faturamento/receita.',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'filtros': {
                    'empresa_destinataria_id': request.query_params.get('empresa_destinataria_id'),
                    'fornecedor_id': request.query_params.get('fornecedor_id'),
                    'apenas_compras_destinatario_erp': True,
                },
                'totais': tot,
                'indicadores_gerenciais': ind,
            }
        )

    @action(detail=False, methods=['get'], url_path='apuracao-mensal-entrada')
    def apuracao_mensal_entrada(self, request):
        qs, di, df, meta = self._base_entrada_historica_filtrada(request)
        return response.Response(
            {
                'origem_dados': 'nf_entrada_historica_importada',
                'tipo_fluxo': 'entrada',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'meses': agrupar_por_mes_entrada(qs),
            }
        )

    @action(detail=False, methods=['get'], url_path='apuracao-trimestral-entrada')
    def apuracao_trimestral_entrada(self, request):
        qs, di, df, meta = self._base_entrada_historica_filtrada(request)
        return response.Response(
            {
                'origem_dados': 'nf_entrada_historica_importada',
                'tipo_fluxo': 'entrada',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'trimestres': agrupar_por_trimestre_entrada(qs),
            }
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='importar-xml',
        parser_classes=[MultiPartParser],
    )
    def importar_xml(self, request):
        files = request.FILES.getlist('arquivos')
        if not files:
            single = request.FILES.get('arquivo')
            if single:
                files = [single]
        if not files:
            return response.Response(
                {'detail': 'Envie um ou mais arquivos no campo "arquivos" (multipart/form-data).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        batch: list[tuple[str, bytes]] = []
        for f in files:
            raw = f.read()
            batch.append((getattr(f, 'name', '') or 'nota.xml', raw))
        result = importar_arquivos_entrada(batch)
        return response.Response(result, status=status.HTTP_200_OK)

    def _get_or_build_conferencia(self, nf: NFeEntradaHistoricaImportada) -> NFeEntradaConferencia:
        conferencia, created = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=nf)
        if created:
            if nf.fornecedor_emitente_id:
                conferencia.pedido_compra = (
                    nf.fornecedor_emitente.pedidos_compra.order_by('-data', '-id').first()
                )
                conferencia.save(update_fields=['pedido_compra'])
        for item_nf in nf.itens.all():
            item_conf, was_created = conferencia.itens.get_or_create(item_nfe_historico=item_nf)
            if was_created:
                fields = _extract_item_nf(item_nf.prod_json or {})
                for k, v in fields.items():
                    setattr(item_conf, k, v)
                item_conf.save(
                    update_fields=['unidade_nf', 'quantidade_nf', 'valor_unitario_nf', 'valor_total_nf']
                )
        return conferencia

    @action(detail=True, methods=['get'], url_path='conferencia')
    def conferencia(self, request, pk=None):
        nf = self.get_queryset().prefetch_related('itens').get(pk=pk)
        conferencia = self._get_or_build_conferencia(nf)
        return response.Response(NFeEntradaConferenciaSerializer(conferencia).data)

    @action(detail=True, methods=['post'], url_path='conferencia')
    @transaction.atomic
    def salvar_conferencia(self, request, pk=None):
        nf = self.get_queryset().prefetch_related('itens').get(pk=pk)
        conferencia = self._get_or_build_conferencia(nf)
        payload = request.data or {}
        conf_serializer = NFeEntradaConferenciaSerializer(
            conferencia,
            data={
                'pedido_compra_id': payload.get('pedido_compra_id'),
                'status': payload.get('status', conferencia.status),
                'divergencias_aceitas': payload.get('divergencias_aceitas', conferencia.divergencias_aceitas),
                'observacao_divergencias': payload.get(
                    'observacao_divergencias',
                    conferencia.observacao_divergencias,
                ),
            },
            partial=True,
        )
        conf_serializer.is_valid(raise_exception=True)
        conf_serializer.save()

        itens_payload = payload.get('itens') or []
        ids = set()
        for raw_item in itens_payload:
            item_id = raw_item.get('id')
            if not item_id:
                continue
            item_obj = conferencia.itens.select_related('item_nfe_historico', 'produto').filter(id=item_id).first()
            if not item_obj:
                continue
            ids.add(item_id)
            item_serializer = ItemNFeEntradaConferenciaSerializer(item_obj, data=raw_item, partial=True)
            item_serializer.is_valid(raise_exception=True)
            saved = item_serializer.save()
            if saved.produto_id:
                unidade_destino = (
                    saved.produto.get_unidade_estoque_efetiva() or saved.produto.unidade or saved.unidade_nf or 'UN'
                ).upper()
                saved.unidade_estoque_calculada = unidade_destino
                alertas = list(saved.alertas or [])
                divergencias = list(saved.divergencias or [])
                try:
                    from apps.produtos.conversao_medidas import converter_quantidade_produto

                    res = converter_quantidade_produto(
                        produto=saved.produto,
                        quantidade=saved.quantidade_nf,
                        unidade_origem=saved.unidade_nf,
                        unidade_destino=unidade_destino,
                    )
                    saved.quantidade_estoque_calculada = res.quantidade_destino
                    saved.peso_total_kg = res.peso_kg or Decimal('0')
                    saved.metros_total = res.metros or Decimal('0')
                    saved.barras_total = res.barras or Decimal('0')
                    saved.toneladas_total = (
                        (saved.peso_total_kg / Decimal('1000')).quantize(Decimal('0.001'))
                        if saved.peso_total_kg
                        else Decimal('0')
                    )
                except Exception as exc:  # noqa: BLE001
                    alertas.append(str(exc))
                    if not saved.unidade_estoque_calculada:
                        saved.unidade_estoque_calculada = unidade_destino
                if conferencia.pedido_compra_id:
                    item_pc = saved.item_pedido_compra
                    if item_pc:
                        if item_pc.produto_id != saved.produto_id:
                            divergencias.append('produto_diferente_pedido')
                        if (item_pc.unidade_negociada or '').upper() != (saved.unidade_nf or '').upper():
                            divergencias.append('unidade_diferente')
                        if _dec(item_pc.quantidade_negociada or item_pc.quantidade) != _dec(saved.quantidade_nf):
                            divergencias.append('quantidade_diferente')
                        if _dec(item_pc.valor_unitario) != _dec(saved.valor_unitario_nf):
                            divergencias.append('preco_diferente')
                ncm_nf = ((saved.item_nfe_historico.prod_json or {}).get('NCM') or '').strip()
                ncm_produto = saved.produto.get_ncm_efetivo_codigo() if saved.produto_id else ''
                if ncm_nf and ncm_produto and ncm_nf != ncm_produto:
                    divergencias.append('ncm_divergente_nf_produto')
                    alertas.append(
                        'NCM da NF-e difere do NCM efetivo do produto. Confira antes de preparar estoque.'
                    )
                saved.alertas = list(dict.fromkeys(alertas))
                saved.divergencias = list(dict.fromkeys(divergencias))
                if saved.status != saved.Status.IGNORADO:
                    if not saved.produto_id:
                        saved.status = saved.Status.PENDENTE_PRODUTO
                    elif saved.divergencias:
                        saved.status = saved.Status.DIVERGENTE
                    elif saved.quantidade_estoque_calculada > 0:
                        saved.status = saved.Status.CONFERIDO
                    else:
                        saved.status = saved.Status.PRODUTO_VINCULADO
            saved.save()

        serializer = NFeEntradaConferenciaSerializer(conferencia)
        return response.Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='preparar-estoque')
    @transaction.atomic
    def preparar_estoque(self, request, pk=None):
        nf = self.get_queryset().prefetch_related('itens').get(pk=pk)
        conferencia = self._get_or_build_conferencia(nf)
        itens = list(conferencia.itens.all())
        pendencias = []
        for it in itens:
            if it.status == it.Status.IGNORADO and not (it.motivo_ignorado or '').strip():
                pendencias.append(f'Item {it.item_nfe_historico.n_item}: motivo de ignorado obrigatório.')
            elif it.status not in {it.Status.CONFERIDO, it.Status.IGNORADO}:
                pendencias.append(f'Item {it.item_nfe_historico.n_item}: item precisa estar conferido ou ignorado.')
        has_div = any(bool(i.divergencias) for i in itens if i.status != i.Status.IGNORADO)
        if has_div and not conferencia.divergencias_aceitas:
            pendencias.append('Existem divergências pendentes sem aceite.')
        if pendencias:
            return response.Response({'detail': 'Não foi possível preparar estoque.', 'pendencias': pendencias}, status=400)
        conferencia.status = NFeEntradaConferencia.Status.CONFERIDA
        conferencia.preparado_em = timezone.now()
        conferencia.status = NFeEntradaConferencia.Status.PREPARADA
        conferencia.save(update_fields=['status', 'preparado_em', 'atualizado_em'])
        return response.Response(NFeEntradaConferenciaSerializer(conferencia).data)


class CTeEntradaViewSet(viewsets.ModelViewSet):
    queryset = CTeEntrada.objects.select_related('transportadora', 'tomador').all()
    serializer_class = CTeEntradaSerializer
    permission_classes = [IsAuthenticated]


class CTeHistoricoImportadoViewSet(viewsets.ReadOnlyModelViewSet):
    """CT-e importados por XML (origem externa, base fiscal/logística/gerencial)."""

    queryset = CTeHistoricoImportado.objects.select_related('transportadora', 'empresa_tomadora').all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        incluir_cancelados = str(self.request.query_params.get('incluir_cancelados', '')).lower() in {'1', 'true', 'sim'}
        if not incluir_cancelados:
            qs = qs.filter(cancelado=False)
        if self.action == 'retrieve':
            return qs.prefetch_related('eventos')
        if self.action == 'list':
            p = self.request.query_params
            try:
                bounds = bounds_para_listagem(p)
            except PeriodoInvalido as exc:
                raise ValidationError({'detail': str(exc)}) from exc
            if bounds:
                di, df = bounds
                qs = qs.filter(dh_emissao__date__gte=di, dh_emissao__date__lte=df)
            if p.get('transportadora_id'):
                try:
                    tid = int(p.get('transportadora_id') or '0')
                except ValueError:
                    raise ValidationError({'detail': 'transportadora_id inválido.'}) from None
                qs = qs.filter(transportadora_id=tid)
            if p.get('empresa_tomadora_id'):
                try:
                    eid = int(p.get('empresa_tomadora_id') or '0')
                except ValueError:
                    raise ValidationError({'detail': 'empresa_tomadora_id inválido.'}) from None
                qs = qs.filter(empresa_tomadora_id=eid)
            if p.get('modal'):
                qs = qs.filter(modal=(p.get('modal') or '')[:16])
            if p.get('tipo_servico'):
                qs = qs.filter(tipo_servico=(p.get('tipo_servico') or '')[:16])
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return CTeHistoricoImportadoListSerializer
        return CTeHistoricoImportadoSerializer

    @action(
        detail=False,
        methods=['post'],
        url_path='importar-xml',
        parser_classes=[MultiPartParser],
    )
    def importar_xml(self, request):
        files = request.FILES.getlist('arquivos')
        if not files:
            single = request.FILES.get('arquivo')
            if single:
                files = [single]
        if not files:
            return response.Response(
                {'detail': 'Envie um ou mais arquivos no campo "arquivos" (multipart/form-data).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        batch: list[tuple[str, bytes]] = []
        for f in files:
            raw = f.read()
            batch.append((getattr(f, 'name', '') or 'cte.xml', raw))
        result = importar_arquivos_cte(batch)
        return response.Response(result, status=status.HTTP_200_OK)

    def _base_cte_gerencial(self, request):
        try:
            di, df, meta = resolver_periodo(request.query_params)
        except PeriodoInvalido as exc:
            raise ValidationError({'detail': str(exc)}) from exc

        p = request.query_params
        incluir_cancelados = str(p.get('incluir_cancelados', '')).lower() in {'1', 'true', 'sim'}
        qs_cte = CTeHistoricoImportado.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
        ).select_related('transportadora')
        if not incluir_cancelados:
            qs_cte = qs_cte.filter(cancelado=False)
        qs_cte = queryset_cte_historico_logistico(qs_cte)

        empresa_id = None
        if p.get('empresa_tomadora_id'):
            try:
                empresa_id = int(p.get('empresa_tomadora_id') or '0')
            except ValueError:
                raise ValidationError({'detail': 'empresa_tomadora_id inválido.'}) from None
            qs_cte = qs_cte.filter(empresa_tomadora_id=empresa_id)
        if p.get('transportadora_id'):
            try:
                tid = int(p.get('transportadora_id') or '0')
            except ValueError:
                raise ValidationError({'detail': 'transportadora_id inválido.'}) from None
            qs_cte = qs_cte.filter(transportadora_id=tid)
        if p.get('modal'):
            qs_cte = qs_cte.filter(modal=(p.get('modal') or '')[:16])
        if p.get('tipo_servico'):
            qs_cte = qs_cte.filter(tipo_servico=(p.get('tipo_servico') or '')[:16])

        return qs_cte, di, df, meta, incluir_cancelados, empresa_id

    @action(detail=False, methods=['get'], url_path='resumo-gerencial-fretes')
    def resumo_gerencial_fretes(self, request):
        qs_cte, di, df, meta, incluir_cancelados, empresa_id = self._base_cte_gerencial(request)
        linha = consolidar_queryset_cte(qs_cte)
        tot_cte, ind_cte = separar_totais_e_indicadores_cte(linha)

        qs_saida = queryset_faturamento_nf_saida_historica(
            NFeSaidaHistoricaImportada.objects.filter(
                dh_emissao__date__gte=di,
                dh_emissao__date__lte=df,
                cancelada=False,
            )
        )
        qs_entrada = queryset_compras_nf_entrada_historica(
            NFeEntradaHistoricaImportada.objects.filter(
                dh_emissao__date__gte=di,
                dh_emissao__date__lte=df,
            )
        )
        if empresa_id:
            qs_saida = qs_saida.filter(empresa_emitente_id=empresa_id)
            qs_entrada = qs_entrada.filter(empresa_destinataria_id=empresa_id)
        tot_saida, _ = separar_totais_e_indicadores(consolidar_queryset(qs_saida))
        tot_entrada, _ = separar_totais_e_indicadores_entrada(consolidar_queryset_entrada(qs_entrada))

        faturamento = tot_saida['faturamento_bruto']
        compras = tot_entrada['valor_total_compras']
        fretes = tot_cte['valor_total_fretes']
        peso_faturamento = round((fretes / faturamento) * 100, 4) if faturamento > 0 else None
        peso_compras = round((fretes / compras) * 100, 4) if compras > 0 else None

        return response.Response(
            {
                'origem_dados': 'cte_historico_importado',
                'tipo_fluxo': 'fretes_historicos_gerencial',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'filtros': {
                    'empresa_tomadora_id': request.query_params.get('empresa_tomadora_id'),
                    'transportadora_id': request.query_params.get('transportadora_id'),
                    'modal': request.query_params.get('modal'),
                    'tipo_servico': request.query_params.get('tipo_servico'),
                    'incluir_cancelados': incluir_cancelados,
                },
                'totais': tot_cte,
                'indicadores_gerenciais': {
                    **ind_cte,
                    'peso_frete_sobre_faturamento_pct': peso_faturamento,
                    'peso_frete_sobre_compras_pct': peso_compras,
                    'frete_medio_observado': tot_cte['frete_medio'],
                },
                'base_comparativa': {
                    'faturamento': faturamento,
                    'compras': compras,
                },
                'observacoes': {
                    'escopo': 'Somente CT-e histórico com Empresa do ERP como tomadora; não integra fluxo operacional.',
                },
            }
        )

    @action(detail=False, methods=['get'], url_path='transportadoras-gerencial')
    def transportadoras_gerencial(self, request):
        qs_cte, di, df, meta, incluir_cancelados, _empresa_id = self._base_cte_gerencial(request)
        return response.Response(
            {
                'origem_dados': 'cte_historico_importado',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'filtros': {
                    'empresa_tomadora_id': request.query_params.get('empresa_tomadora_id'),
                    'transportadora_id': request.query_params.get('transportadora_id'),
                    'modal': request.query_params.get('modal'),
                    'tipo_servico': request.query_params.get('tipo_servico'),
                    'incluir_cancelados': incluir_cancelados,
                },
                'transportadoras': agrupar_cte_por_transportadora(qs_cte),
            }
        )

    @action(detail=False, methods=['get'], url_path='serie-mensal-gerencial')
    def serie_mensal_gerencial(self, request):
        qs_cte, di, df, meta, incluir_cancelados, empresa_id = self._base_cte_gerencial(request)
        meses_frete = agrupar_cte_por_mes(qs_cte)
        out = []
        for row in meses_frete:
            ano_mes = row.get('ano_mes')
            base_saida = queryset_faturamento_nf_saida_historica(
                NFeSaidaHistoricaImportada.objects.filter(
                    dh_emissao__year=int(str(ano_mes).split('-')[0]),
                    dh_emissao__month=int(str(ano_mes).split('-')[1]),
                    cancelada=False,
                )
            )
            if empresa_id:
                base_saida = base_saida.filter(empresa_emitente_id=empresa_id)
            tot_saida, _ = separar_totais_e_indicadores(consolidar_queryset(base_saida))
            fat = tot_saida['faturamento_bruto']
            fre = row['totais']['valor_total_fretes']
            peso = round((fre / fat) * 100, 4) if fat > 0 else None
            out.append(
                {
                    **row,
                    'peso_frete_sobre_faturamento_pct': peso,
                    'faturamento_periodo': fat,
                }
            )
        return response.Response(
            {
                'origem_dados': 'cte_historico_importado',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'filtros': {
                    'empresa_tomadora_id': request.query_params.get('empresa_tomadora_id'),
                    'transportadora_id': request.query_params.get('transportadora_id'),
                    'modal': request.query_params.get('modal'),
                    'tipo_servico': request.query_params.get('tipo_servico'),
                    'incluir_cancelados': incluir_cancelados,
                },
                'meses': out,
            }
        )

    @action(detail=False, methods=['get'], url_path='serie-trimestral-gerencial')
    def serie_trimestral_gerencial(self, request):
        qs_cte, di, df, meta, incluir_cancelados, empresa_id = self._base_cte_gerencial(request)
        tris_frete = agrupar_cte_por_trimestre(qs_cte)
        out = []
        for row in tris_frete:
            ano = int(row['ano'])
            tri = int(row['trimestre'])
            mes_ini = (tri - 1) * 3 + 1
            mes_fim = mes_ini + 2
            base_saida = queryset_faturamento_nf_saida_historica(
                NFeSaidaHistoricaImportada.objects.filter(
                    dh_emissao__year=ano,
                    dh_emissao__month__gte=mes_ini,
                    dh_emissao__month__lte=mes_fim,
                    cancelada=False,
                )
            )
            if empresa_id:
                base_saida = base_saida.filter(empresa_emitente_id=empresa_id)
            tot_saida, _ = separar_totais_e_indicadores(consolidar_queryset(base_saida))
            fat = tot_saida['faturamento_bruto']
            fre = row['totais']['valor_total_fretes']
            peso = round((fre / fat) * 100, 4) if fat > 0 else None
            out.append(
                {
                    **row,
                    'peso_frete_sobre_faturamento_pct': peso,
                    'faturamento_periodo': fat,
                }
            )
        return response.Response(
            {
                'origem_dados': 'cte_historico_importado',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'filtros': {
                    'empresa_tomadora_id': request.query_params.get('empresa_tomadora_id'),
                    'transportadora_id': request.query_params.get('transportadora_id'),
                    'modal': request.query_params.get('modal'),
                    'tipo_servico': request.query_params.get('tipo_servico'),
                    'incluir_cancelados': incluir_cancelados,
                },
                'trimestres': out,
            }
        )


class PainelFiscalGerencialHistoricoViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        try:
            di, df, meta = resolver_periodo(request.query_params)
        except PeriodoInvalido as exc:
            raise ValidationError({'detail': str(exc)}) from exc

        p = request.query_params
        incluir_canceladas = str(p.get('incluir_canceladas', '')).lower() in {'1', 'true', 'sim'}
        incluir_cancelados_cte = str(p.get('incluir_cancelados_cte', '')).lower() in {'1', 'true', 'sim'}

        qs_saida = NFeSaidaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
        )
        if not incluir_canceladas:
            qs_saida = qs_saida.filter(cancelada=False)
        qs_saida = queryset_faturamento_nf_saida_historica(qs_saida)
        try:
            qs_saida = aplicar_filtros_vinculo(
                qs_saida,
                p.get('cliente_id'),
                p.get('empresa_id'),
            )
        except PeriodoInvalido as exc:
            raise ValidationError({'detail': str(exc)}) from exc

        qs_entrada = NFeEntradaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
        )
        qs_entrada = queryset_compras_nf_entrada_historica(qs_entrada)
        if p.get('empresa_id'):
            try:
                eid = int(p.get('empresa_id') or '0')
            except ValueError:
                raise ValidationError({'detail': 'empresa_id inválido.'}) from None
            qs_entrada = qs_entrada.filter(empresa_destinataria_id=eid)
        if p.get('fornecedor_id'):
            try:
                fid = int(p.get('fornecedor_id') or '0')
            except ValueError:
                raise ValidationError({'detail': 'fornecedor_id inválido.'}) from None
            qs_entrada = qs_entrada.filter(fornecedor_emitente_id=fid)

        qs_cte = CTeHistoricoImportado.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
        ).select_related('transportadora')
        if not incluir_cancelados_cte:
            qs_cte = qs_cte.filter(cancelado=False)
        qs_cte = queryset_cte_historico_logistico(qs_cte)
        if p.get('empresa_id'):
            try:
                eid = int(p.get('empresa_id') or '0')
            except ValueError:
                raise ValidationError({'detail': 'empresa_id inválido.'}) from None
            qs_cte = qs_cte.filter(empresa_tomadora_id=eid)
        if p.get('transportadora_id'):
            try:
                tid = int(p.get('transportadora_id') or '0')
            except ValueError:
                raise ValidationError({'detail': 'transportadora_id inválido.'}) from None
            qs_cte = qs_cte.filter(transportadora_id=tid)

        linha_saida = consolidar_queryset(qs_saida)
        tot_saida, ind_saida = separar_totais_e_indicadores(linha_saida)
        linha_entrada = consolidar_queryset_entrada(qs_entrada)
        tot_entrada, ind_entrada = separar_totais_e_indicadores_entrada(linha_entrada)
        linha_cte = consolidar_queryset_cte(qs_cte)
        tot_cte, ind_cte = separar_totais_e_indicadores_cte(linha_cte)

        faturamento = tot_saida['faturamento_bruto']
        compras = tot_entrada['valor_total_compras']
        fretes = tot_cte['valor_total_fretes']
        carga_tributaria_total = (
            tot_saida['icms_valor']
            + tot_saida['ipi_valor']
            + tot_saida['pis_valor']
            + tot_saida['cofins_valor']
            + tot_entrada['icms_valor']
            + tot_entrada['ipi_valor']
            + tot_entrada['pis_valor']
            + tot_entrada['cofins_valor']
            + tot_cte['icms_total']
        )
        peso_frete_sobre_faturamento = None
        peso_carga_sobre_faturamento = None
        if faturamento > 0:
            peso_frete_sobre_faturamento = round((fretes / faturamento) * 100, 4)
            peso_carga_sobre_faturamento = round((carga_tributaria_total / faturamento) * 100, 4)

        qs_saida_canceladas = NFeSaidaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
            cancelada=True,
        )
        try:
            qs_saida_canceladas = aplicar_filtros_vinculo(
                qs_saida_canceladas,
                p.get('cliente_id'),
                p.get('empresa_id'),
            )
        except PeriodoInvalido as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        qs_saida_canceladas = queryset_faturamento_nf_saida_historica(qs_saida_canceladas)

        qs_cte_cancelados = CTeHistoricoImportado.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
            cancelado=True,
        )
        qs_cte_cancelados = queryset_cte_historico_logistico(qs_cte_cancelados)
        if p.get('empresa_id'):
            eid = int(p.get('empresa_id') or '0')
            qs_cte_cancelados = qs_cte_cancelados.filter(empresa_tomadora_id=eid)
        if p.get('transportadora_id'):
            tid = int(p.get('transportadora_id') or '0')
            qs_cte_cancelados = qs_cte_cancelados.filter(transportadora_id=tid)

        return response.Response(
            {
                'origem_dados': 'consolidado_historico_fiscal_gerencial',
                'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
                'filtros': {
                    'empresa_id': p.get('empresa_id'),
                    'cliente_id': p.get('cliente_id'),
                    'fornecedor_id': p.get('fornecedor_id'),
                    'transportadora_id': p.get('transportadora_id'),
                    'incluir_canceladas': incluir_canceladas,
                    'incluir_cancelados_cte': incluir_cancelados_cte,
                },
                'bloco_faturamento': {
                    'totais': tot_saida,
                    'indicadores_gerenciais': ind_saida,
                    'notas_canceladas_historico': qs_saida_canceladas.count(),
                },
                'bloco_compras': {
                    'totais': tot_entrada,
                    'indicadores_gerenciais': ind_entrada,
                },
                'bloco_fretes': {
                    'totais': tot_cte,
                    'indicadores_gerenciais': ind_cte,
                    'ctes_cancelados_historico': qs_cte_cancelados.count(),
                },
                'visao_comparativa': {
                    'faturamento': faturamento,
                    'compras': compras,
                    'fretes': fretes,
                    'diferenca_venda_compra': round(faturamento - compras, 2),
                    'peso_frete_sobre_faturamento_pct': peso_frete_sobre_faturamento,
                    'carga_tributaria_total_observada': round(carga_tributaria_total, 2),
                    'peso_carga_tributaria_sobre_faturamento_pct': peso_carga_sobre_faturamento,
                },
                'series': {
                    'faturamento_mensal': agrupar_por_mes(qs_saida),
                    'faturamento_trimestral': agrupar_por_trimestre(qs_saida),
                    'compras_mensal': agrupar_por_mes_entrada(qs_entrada),
                    'compras_trimestral': agrupar_por_trimestre_entrada(qs_entrada),
                    'fretes_mensal': agrupar_cte_por_mes(qs_cte),
                    'fretes_trimestral': agrupar_cte_por_trimestre(qs_cte),
                },
                'observacoes': {
                    'separacao_fluxos': (
                        'Faturamento considera apenas NF-e de saída com empresa emitente reconhecida; '
                        'compras considera apenas NF-e de entrada com empresa destinatária reconhecida; '
                        'fretes considera somente CT-e histórico e não é receita.'
                    ),
                    'escopo_fase': 'Apenas dados históricos importados; não interfere no fluxo operacional do ERP.',
                },
            }
        )


class EstoqueViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        rows = EstoqueCorrida.objects.select_related('produto', 'corrida').all()
        data = []
        for r in rows:
            unidade_estoque = (r.produto.get_unidade_estoque_efetiva() or r.produto.unidade or 'UN').upper()
            dim = calcular_saldo_dimensional(
                produto=r.produto,
                quantidade_saldo=r.saldo,
                unidade_saldo=unidade_estoque,
            )
            data.append(
                {
                    'produto_id': r.produto_id,
                    'produto_nome': r.produto.descricao,
                    'corrida_id': r.corrida_id,
                    'corrida_numero': r.corrida.numero,
                    'saldo': float(r.saldo),
                    'codigo': dim['codigo'],
                    'saldo_principal': float(dim['saldo_principal']),
                    'unidade_principal': dim['unidade_principal'],
                    'peso_kg': float(dim['peso_kg']) if dim['peso_kg'] is not None else None,
                    'metros': float(dim['metros']) if dim['metros'] is not None else None,
                    'barras': float(dim['barras']) if dim['barras'] is not None else None,
                    'toneladas': float(dim['toneladas']) if dim['toneladas'] is not None else None,
                    'pecas': float(dim['pecas']) if dim['pecas'] is not None else None,
                    'chapas': float(dim['chapas']) if dim['chapas'] is not None else None,
                    'usa_conversao_dimensional': dim['usa_conversao_dimensional'],
                    'alertas': dim['alertas'],
                }
            )
        return response.Response(data)


def _parse_bool_param(raw):
    if raw is None:
        return None
    normalized = str(raw).strip().lower()
    if normalized in {'1', 'true', 'sim', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'nao', 'não', 'no', 'off'}:
        return False
    raise ValidationError({'detail': f'Parâmetro booleano inválido: {raw}'})


def _fmt_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f'{value:.3f}'


class EstoqueSaldosViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _serializar_dimensional(self, row):
        unidade_estoque = (row.produto.get_unidade_estoque_efetiva() or row.produto.unidade or 'UN').upper()
        dim = calcular_saldo_dimensional(
            produto=row.produto,
            quantidade_saldo=row.saldo,
            unidade_saldo=unidade_estoque,
        )
        return {
            'produto_id': row.produto_id,
            'codigo': dim['codigo'],
            'descricao': row.produto.descricao,
            'corrida': row.corrida.numero,
            'saldo_principal': _fmt_decimal(dim['saldo_principal']),
            'unidade_principal': dim['unidade_principal'],
            'peso_kg': _fmt_decimal(dim['peso_kg']),
            'metros': _fmt_decimal(dim['metros']),
            'barras': _fmt_decimal(dim['barras']),
            'toneladas': _fmt_decimal(dim['toneladas']),
            'usa_conversao_dimensional': dim['usa_conversao_dimensional'],
            'tipo_fisico': row.produto.get_tipo_fisico_efetivo(),
            'alertas': dim['alertas'],
        }

    def _apply_filtros(self, rows, query_params):
        produto_id = query_params.get('produto_id')
        if produto_id:
            try:
                rows = rows.filter(produto_id=int(produto_id))
            except ValueError:
                raise ValidationError({'detail': 'produto_id inválido.'}) from None
        codigo = (query_params.get('codigo') or '').strip()
        if codigo:
            rows = rows.filter(produto__codigo_completo__icontains=codigo)
        descricao = (query_params.get('descricao') or '').strip()
        if descricao:
            rows = rows.filter(produto__descricao__icontains=descricao)
        corrida = (query_params.get('corrida') or '').strip()
        if corrida:
            rows = rows.filter(corrida__numero__icontains=corrida)
        return rows

    def _apply_filtros_payload(self, payload, query_params):
        somente_dimensionais = _parse_bool_param(query_params.get('somente_dimensionais'))
        com_saldo = _parse_bool_param(query_params.get('com_saldo'))
        com_alertas = _parse_bool_param(query_params.get('com_alertas'))
        tipo_fisico = (query_params.get('tipo_fisico') or '').strip().upper()

        out = payload
        if somente_dimensionais is True:
            out = [i for i in out if i['usa_conversao_dimensional']]
        elif somente_dimensionais is False:
            out = [i for i in out if not i['usa_conversao_dimensional']]

        if tipo_fisico:
            out = [i for i in out if (i.get('tipo_fisico') or '').upper() == tipo_fisico]

        if com_saldo is True:
            out = [i for i in out if Decimal(i['saldo_principal']) > Decimal('0')]
        elif com_saldo is False:
            out = [i for i in out if Decimal(i['saldo_principal']) <= Decimal('0')]

        if com_alertas is True:
            out = [i for i in out if i.get('alertas')]
        elif com_alertas is False:
            out = [i for i in out if not i.get('alertas')]

        return out

    def _agrupar_por_produto(self, payload):
        produtos_map = {
            p.id: p
            for p in Produto.objects.select_related('familia').filter(
                id__in=[item['produto_id'] for item in payload]
            )
        }
        grouped = {}
        for item in payload:
            key = item['produto_id']
            unidade = item['unidade_principal']
            saldo = Decimal(item['saldo_principal'])
            bucket = grouped.get(key)
            if not bucket:
                grouped[key] = {
                    'produto_id': item['produto_id'],
                    'codigo': item['codigo'],
                    'descricao': item['descricao'],
                    'unidade_principal': unidade,
                    'soma_saldo': saldo,
                    'usa_conversao_dimensional': item['usa_conversao_dimensional'],
                    'tipo_fisico': item['tipo_fisico'],
                    'alertas': list(item['alertas'] or []),
                    'corridas': [item['corrida']],
                    'unidades': {unidade},
                }
                continue
            bucket['soma_saldo'] += saldo
            bucket['corridas'].append(item['corrida'])
            bucket['unidades'].add(unidade)
            bucket['alertas'] = list(dict.fromkeys([*bucket['alertas'], *(item['alertas'] or [])]))

        out = []
        for row in grouped.values():
            unidade_base = row['unidade_principal']
            produto_obj = produtos_map[row['produto_id']]
            if len(row['unidades']) > 1:
                row['alertas'].append('Inconsistência de unidade principal entre corridas do produto.')
                dim = {
                    'saldo_principal': row['soma_saldo'],
                    'unidade_principal': unidade_base,
                    'peso_kg': None,
                    'metros': None,
                    'barras': None,
                    'toneladas': None,
                }
            else:
                dim = calcular_saldo_dimensional(
                    produto=produto_obj,
                    quantidade_saldo=row['soma_saldo'],
                    unidade_saldo=unidade_base,
                )
                row['alertas'] = list(dict.fromkeys([*row['alertas'], *(dim.get('alertas') or [])]))

            out.append(
                {
                    'produto_id': row['produto_id'],
                    'codigo': row['codigo'],
                    'descricao': row['descricao'],
                    'saldo_principal': _fmt_decimal(dim['saldo_principal']),
                    'unidade_principal': dim['unidade_principal'],
                    'peso_kg': _fmt_decimal(dim.get('peso_kg')),
                    'metros': _fmt_decimal(dim.get('metros')),
                    'barras': _fmt_decimal(dim.get('barras')),
                    'toneladas': _fmt_decimal(dim.get('toneladas')),
                    'usa_conversao_dimensional': row['usa_conversao_dimensional'],
                    'tipo_fisico': row['tipo_fisico'],
                    'alertas': list(dict.fromkeys(row['alertas'])),
                    'quantidade_corridas': len(row['corridas']),
                    'corridas_resumo': sorted(set(row['corridas']))[:5],
                }
            )
        return out

    def list(self, request):
        rows = (
            EstoqueCorrida.objects.select_related('produto', 'corrida', 'produto__familia')
            .all()
            .order_by('produto__codigo_completo', 'corrida__numero')
        )
        rows = self._apply_filtros(rows, request.query_params)
        payload = [self._serializar_dimensional(row) for row in rows]
        payload = self._apply_filtros_payload(payload, request.query_params)

        agrupar_produto = _parse_bool_param(request.query_params.get('agrupar_produto'))
        if agrupar_produto:
            payload = self._agrupar_por_produto(payload)
            payload = self._apply_filtros_payload(payload, request.query_params)
        return response.Response(payload)
