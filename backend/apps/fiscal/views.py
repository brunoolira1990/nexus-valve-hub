from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import response, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from apps.qualidade.models import Certificado
from apps.comercial.models import ItemPedidoCompra
from apps.produtos.models import Produto

from .estoque_services import reverter_todos_itens_entrada, reverter_todos_itens_saida
from .nfe_saida_efeitos import (
    aplicar_efeitos_autorizacao_nfe_saida,
    aplicar_efeitos_cancelamento_nfe_saida,
    avaliar_efeitos_nfe_saida,
    listar_eventos_nfe_saida,
    montar_payload_eventos_nfe_saida,
)
from .nfe_saida_preview import (
    gerar_dados_preview_nfe_saida,
    gerar_preview_danfe_nfe_saida,
    gerar_preview_xml_nfe_saida,
)
from .nfe_saida_xml_nfelib import gerar_xml_oficial_nfe_saida
from .validacao_nfe_saida import validar_nfe_saida_para_emissao
from .cte_import.service import importar_arquivos_cte
from .consolidado_historico_gerencial import (
    agrupar_cte_por_transportadora,
    agrupar_cte_por_mes,
    agrupar_cte_por_trimestre,
    consolidar_queryset_cte,
    queryset_cte_historico_logistico,
    separar_totais_e_indicadores_cte,
)
from .atendimento_estoque import (
    desvincular_linha_atendimento,
    filtrar_atendimentos_estoque,
    listar_linhas_conferencia_elegiveis,
    listar_saldos_consolidados,
    montar_resposta_vinculo,
    queryset_atendimentos_estoque,
    sugerir_atendimentos_para_item_conferencia,
    vincular_item_conferencia_a_atendimento,
)
from .models import (
    AtendimentoEstoque,
    AtendimentoEstoqueLinha,
    CTeEntrada,
    CTeHistoricoImportado,
    EstoqueCorrida,
    EventoNFeSaidaHistoricaPendente,
    NFeEntrada,
    ItemNFeEntradaConferencia,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)
from .conferencia_pedido import (
    aplicar_pos_save_item_conferencia,
    limpar_vinculos_pedido_invalidos,
    validar_preparar_estoque_conferencia,
)
from .aplicacao_estoque_conferencia import (
    aplicar_estoque_fisico_conferencia,
    montar_preview_aplicacao_estoque_conferencia,
)
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
    AtendimentoEstoqueListSerializer,
    CTeEntradaSerializer,
    CTeHistoricoImportadoListSerializer,
    CTeHistoricoImportadoSerializer,
    NFeEntradaSerializer,
    NFeEntradaHistoricaImportadaListSerializer,
    NFeEntradaHistoricaImportadaSerializer,
    NFeEntradaConferenciaSerializer,
    ItemNFeEntradaConferenciaSerializer,
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
        NFeSaida.objects.select_related(
            'cliente',
            'transportadora',
            'pedido_venda',
            'pedido_venda__empresa_emitente',
            'faturamento_pedido_venda',
        )
        .prefetch_related('itens__produto', 'itens__corrida', 'itens__item_faturamento_pedido')
        .all()
    )
    serializer_class = NFeSaidaSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['get'], url_path='efeitos-emissao')
    def efeitos_emissao(self, request, pk=None):
        """NF-e Saída 3.1 — política prevista de efeitos (autorização/cancelamento), sem SEFAZ."""
        nf = self.get_object()
        payload = avaliar_efeitos_nfe_saida(nf)
        payload['eventos'] = listar_eventos_nfe_saida(nf.pk)
        return response.Response(payload)

    @action(detail=True, methods=['get'], url_path='eventos')
    def eventos(self, request, pk=None):
        """NF-e Saída 3.2 — histórico operacional (mais recente primeiro)."""
        nf = self.get_object()
        return response.Response(montar_payload_eventos_nfe_saida(nf.pk))

    @action(detail=True, methods=['post'], url_path='aplicar-efeitos-autorizacao-interna')
    def aplicar_efeitos_autorizacao_interna(self, request, pk=None):
        """Simulação interna — não transmite SEFAZ."""
        nf = self.get_object()
        try:
            resultado = aplicar_efeitos_autorizacao_nfe_saida(
                nf,
                usuario=request.user,
                observacao=(request.data.get('observacao') or '').strip(),
            )
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Falha ao aplicar efeitos de autorização interna NF-e id=%s', pk)
            return response.Response(
                {'detail': 'Não foi possível aplicar os efeitos de autorização.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return response.Response(resultado)

    @action(detail=True, methods=['post'], url_path='cancelar-interno')
    def cancelar_interno(self, request, pk=None):
        """Simulação interna de cancelamento — não cancela na SEFAZ."""
        nf = self.get_object()
        try:
            resultado = aplicar_efeitos_cancelamento_nfe_saida(
                nf,
                motivo=request.data.get('motivo') or '',
                usuario=request.user,
            )
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Falha ao cancelar internamente NF-e id=%s', pk)
            return response.Response(
                {'detail': 'Não foi possível aplicar o cancelamento interno.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return response.Response(resultado)

    @action(detail=True, methods=['get'], url_path='validar-emissao')
    def validar_emissao(self, request, pk=None):
        """NF-e Saída 2 — checklist pré-emissão (sem SEFAZ, estoque ou financeiro)."""
        nf = self.get_object()
        return response.Response(validar_nfe_saida_para_emissao(nf))

    @action(detail=True, methods=['get'], url_path='conferencia')
    def conferencia(self, request, pk=None):
        """NF-e Saída 3.5 — payload unificado de conferência pré-emissão."""
        from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida

        nf = self.get_object()
        return response.Response(montar_conferencia_nfe_saida(nf))

    @action(detail=True, methods=['get'], url_path='prontidao')
    def prontidao(self, request, pk=None):
        """NF-e Saída 3.5.3 — status de prontidão da conferência (sem SEFAZ)."""
        from apps.fiscal.nfe_saida_prontidao import montar_payload_prontidao

        nf = self.get_object()
        return response.Response(montar_payload_prontidao(nf))

    @action(detail=True, methods=['post'], url_path='validar-conferencia')
    def validar_conferencia(self, request, pk=None):
        """NF-e Saída 3.5.3 — valida checklist e atualiza status de conferência."""
        from apps.fiscal.nfe_saida_prontidao import validar_conferencia_nfe

        nf = self.get_object()
        try:
            resultado = validar_conferencia_nfe(nf, usuario=request.user)
        except ValueError as exc:
            return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(resultado)

    @action(detail=True, methods=['post'], url_path='marcar-pronta')
    def marcar_pronta(self, request, pk=None):
        """NF-e Saída 3.5.3 — marca pronta para emissão futura (sem transmitir SEFAZ)."""
        from apps.fiscal.nfe_saida_prontidao import marcar_nfe_pronta_para_emissao

        nf = self.get_object()
        try:
            resultado = marcar_nfe_pronta_para_emissao(nf, usuario=request.user)
        except ValueError as exc:
            return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(resultado)

    @action(detail=True, methods=['get'], url_path='atualizar-impostos/preview')
    def atualizar_impostos_preview(self, request, pk=None):
        """NF-e Saída 3.5.2 — comparativo de impostos (sem gravar)."""
        from apps.fiscal.nfe_saida_atualizar_impostos import preparar_atualizacao_impostos_nfe

        nf = self.get_object()
        return response.Response(preparar_atualizacao_impostos_nfe(nf, usuario=request.user))

    @action(detail=True, methods=['post'], url_path='atualizar-impostos/aplicar')
    def atualizar_impostos_aplicar(self, request, pk=None):
        """NF-e Saída 3.5.2 — aplica snapshot fiscal da regra atual (rascunho)."""
        from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe

        nf = self.get_object()
        motivo = (request.data.get('motivo') or '').strip()
        try:
            resultado = aplicar_atualizacao_impostos_nfe(nf, usuario=request.user, motivo=motivo)
        except ValueError as exc:
            return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(resultado)

    @action(detail=True, methods=['get'], url_path='preview-xml')
    def preview_xml(self, request, pk=None):
        """NF-e Saída 3 — XML de prévia (não transmitível)."""
        nf = self.get_object()
        payload = gerar_preview_xml_nfe_saida(nf)
        if payload.get('bloqueado'):
            return response.Response(payload, status=status.HTTP_409_CONFLICT)
        if str(request.query_params.get('download', '')).lower() in ('1', 'true', 'yes'):
            from django.http import HttpResponse

            return HttpResponse(
                payload.get('xml', ''),
                content_type='application/xml; charset=utf-8',
                headers={
                    'Content-Disposition': f'attachment; filename="nfe-previa-{nf.pk}.xml"',
                },
            )
        return response.Response(payload)

    @action(detail=True, methods=['get'], url_path='preview-xml-oficial')
    def preview_xml_oficial(self, request, pk=None):
        """NF-e Saída 4.0.1 — XML oficial NF-e 4.00 (nfelib), sem transmissão."""
        nf = self.get_object()
        payload = gerar_xml_oficial_nfe_saida(nf)
        if payload.get('bloqueado'):
            return response.Response(payload, status=status.HTTP_409_CONFLICT)
        if str(request.query_params.get('download', '')).lower() in ('1', 'true', 'yes'):
            from django.http import HttpResponse

            return HttpResponse(
                payload.get('xml', ''),
                content_type='application/xml; charset=utf-8',
                headers={
                    'Content-Disposition': (
                        f'attachment; filename="nfe-oficial-previa-{nf.pk}.xml"'
                    ),
                },
            )
        return response.Response(payload)

    @action(detail=True, methods=['get'], url_path='preview-danfe')
    def preview_danfe(self, request, pk=None):
        """NF-e Saída 3.5.4 — DANFE de conferência (layout real, sem valor fiscal)."""
        return self._resposta_danfe_conferencia(request, pk)

    @action(detail=True, methods=['get'], url_path='danfe-conferencia')
    def danfe_conferencia(self, request, pk=None):
        """NF-e Saída 3.5.4 — alias do DANFE de conferência."""
        return self._resposta_danfe_conferencia(request, pk)

    def _resposta_danfe_conferencia(self, request, pk=None):
        from django.http import HttpResponse

        nf = self.get_object()
        pdf, meta = gerar_preview_danfe_nfe_saida(nf)
        if meta.get('bloqueado'):
            return response.Response(meta, status=status.HTTP_409_CONFLICT)
        headers = {
            'Content-Disposition': f'inline; filename="{meta["filename"]}"',
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
        }
        if settings.DEBUG and meta.get('render_engine'):
            headers['X-Danfe-Renderer'] = str(meta.get('render_engine'))
            if meta.get('pdf_page_count') is not None:
                headers['X-Danfe-Pages'] = str(meta['pdf_page_count'])
        return HttpResponse(pdf, content_type='application/pdf', headers=headers)

    @action(detail=True, methods=['get'], url_path='preview-dados')
    def preview_dados(self, request, pk=None):
        """NF-e Saída 3 — dados normalizados usados no preview."""
        nf = self.get_object()
        payload = gerar_dados_preview_nfe_saida(nf)
        if payload.get('bloqueado'):
            return response.Response(payload, status=status.HTTP_409_CONFLICT)
        return response.Response(payload)

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

    @staticmethod
    def _conferencia_com_relacionamentos(conferencia_id: int) -> NFeEntradaConferencia | None:
        return (
            NFeEntradaConferencia.objects.filter(pk=conferencia_id)
            .select_related(
                'pedido_compra',
                'nf_entrada_historica__fornecedor_emitente',
                'nf_entrada_historica__empresa_destinataria',
            )
            .prefetch_related(
                Prefetch(
                    'itens',
                    queryset=ItemNFeEntradaConferencia.objects.select_related(
                        'item_nfe_historico',
                        'produto',
                        'item_pedido_compra__produto',
                        'item_pedido_compra__pedido',
                    ).order_by('item_nfe_historico__n_item'),
                ),
                Prefetch(
                    'pedido_compra__itens',
                    queryset=ItemPedidoCompra.objects.select_related('produto').order_by('id'),
                ),
            )
            .first()
        )

    @action(detail=True, methods=['get', 'post'], url_path='conferencia')
    def conferencia(self, request, pk=None):
        if request.method == 'POST':
            return self._salvar_conferencia(request, pk)
        nf = self.get_queryset().prefetch_related('itens').get(pk=pk)
        conferencia = self._get_or_build_conferencia(nf)
        conferencia = self._conferencia_com_relacionamentos(conferencia.id) or conferencia
        return response.Response(NFeEntradaConferenciaSerializer(conferencia).data)

    @transaction.atomic
    def _salvar_conferencia(self, request, pk=None):
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
        conferencia.refresh_from_db()
        limpar_vinculos_pedido_invalidos(conferencia)

        itens_payload = payload.get('itens') or []
        for raw_item in itens_payload:
            item_id = raw_item.get('id')
            if not item_id:
                continue
            item_obj = (
                conferencia.itens.select_related(
                    'item_nfe_historico',
                    'produto',
                    'item_pedido_compra__produto',
                    'item_pedido_compra__pedido',
                )
                .filter(id=item_id)
                .first()
            )
            if not item_obj:
                continue
            item_serializer = ItemNFeEntradaConferenciaSerializer(
                item_obj,
                data=raw_item,
                partial=True,
                context={
                    'conferencia': conferencia,
                    'pedido_compra_id': conferencia.pedido_compra_id,
                },
            )
            item_serializer.is_valid(raise_exception=True)
            saved = item_serializer.save()
            if saved.item_pedido_compra_id and not saved.item_pedido_compra:
                saved = (
                    ItemNFeEntradaConferencia.objects.select_related(
                        'item_nfe_historico',
                        'produto',
                        'item_pedido_compra__produto',
                        'item_pedido_compra__pedido',
                    )
                    .get(pk=saved.pk)
                )
            aplicar_pos_save_item_conferencia(saved, conferencia)

        conferencia = self._conferencia_com_relacionamentos(conferencia.id) or conferencia
        return response.Response(NFeEntradaConferenciaSerializer(conferencia).data)

    @action(detail=True, methods=['post'], url_path='preparar-estoque')
    @transaction.atomic
    def preparar_estoque(self, request, pk=None):
        nf = self.get_queryset().prefetch_related('itens').get(pk=pk)
        conferencia = self._get_or_build_conferencia(nf)
        conferencia = self._conferencia_com_relacionamentos(conferencia.id) or conferencia
        for item_obj in conferencia.itens.all():
            aplicar_pos_save_item_conferencia(item_obj, conferencia)
        conferencia.refresh_from_db()
        itens = list(
            conferencia.itens.select_related('item_nfe_historico', 'produto', 'item_pedido_compra').all(),
        )
        pendencias, bloqueio_fiscal = validar_preparar_estoque_conferencia(conferencia, itens)
        if pendencias:
            payload: dict = {
                'detail': 'Não foi possível preparar estoque.',
                'pendencias': pendencias,
            }
            if bloqueio_fiscal:
                payload['bloqueio_fiscal'] = True
            return response.Response(payload, status=400)
        conferencia.status = NFeEntradaConferencia.Status.CONFERIDA
        conferencia.preparado_em = timezone.now()
        conferencia.status = NFeEntradaConferencia.Status.PREPARADA
        conferencia.save(update_fields=['status', 'preparado_em', 'atualizado_em'])
        return response.Response(NFeEntradaConferenciaSerializer(conferencia).data)

    @action(detail=True, methods=['get', 'post'], url_path='conferencia/aplicar-estoque')
    def aplicar_estoque_conferencia(self, request, pk=None):
        nf = self.get_queryset().get(pk=pk)
        conferencia = self._get_or_build_conferencia(nf)
        conferencia = self._conferencia_com_relacionamentos(conferencia.id) or conferencia
        confirmar_alertas = False
        observacao = ''
        if request.method == 'POST':
            payload = request.data or {}
            confirmar_alertas = bool(payload.get('confirmar_alertas'))
            observacao = str(payload.get('observacao') or '')
        else:
            confirmar_alertas = str(request.query_params.get('confirmar_alertas', '')).lower() in {
                '1',
                'true',
                'sim',
            }

        if request.method == 'GET':
            data = montar_preview_aplicacao_estoque_conferencia(
                conferencia,
                confirmar_alertas=confirmar_alertas,
            )
            return response.Response(data)

        try:
            data = aplicar_estoque_fisico_conferencia(
                conferencia,
                confirmar_alertas=confirmar_alertas,
                observacao=observacao,
                usuario=request.user,
            )
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if data.get('pendencias') or (data.get('alertas') and not confirmar_alertas):
            return response.Response(
                {
                    'detail': 'Não foi possível aplicar estoque físico.',
                    **data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        conferencia = self._conferencia_com_relacionamentos(conferencia.id) or conferencia
        return response.Response(
            {
                **data,
                'conferencia': NFeEntradaConferenciaSerializer(conferencia).data,
            },
        )


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


class AtendimentoEstoqueViewSet(viewsets.ReadOnlyModelViewSet):
    """Compromissos de atendimento de estoque."""

    serializer_class = AtendimentoEstoqueListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = queryset_atendimentos_estoque()
        try:
            return filtrar_atendimentos_estoque(qs, self.request.query_params)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'detail': 'Parâmetro de filtro inválido.'}) from exc

    @action(detail=False, methods=['get'], url_path='sugestoes')
    def sugestoes(self, request):
        item_id = request.query_params.get('item_conferencia_id')
        if not item_id:
            raise ValidationError({'item_conferencia_id': 'Obrigatório.'})
        try:
            item_conf = ItemNFeEntradaConferencia.objects.select_related(
                'conferencia',
                'conferencia__nf_entrada_historica',
                'produto',
            ).get(pk=int(item_id))
        except (TypeError, ValueError, ItemNFeEntradaConferencia.DoesNotExist) as exc:
            raise ValidationError({'item_conferencia_id': 'Linha de conferência inválida.'}) from exc
        try:
            payload = sugerir_atendimentos_para_item_conferencia(item_conf)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return response.Response(payload)

    @action(detail=False, methods=['get'], url_path='linhas-conferencia-elegiveis')
    def linhas_conferencia_elegiveis(self, request):
        produto_id = request.query_params.get('produto_id')
        if not produto_id:
            raise ValidationError({'produto_id': 'Obrigatório.'})
        try:
            pid = int(produto_id)
        except ValueError as exc:
            raise ValidationError({'produto_id': 'produto_id inválido.'}) from exc
        return response.Response(listar_linhas_conferencia_elegiveis(produto_id=pid))

    @action(detail=False, methods=['post'], url_path='vincular')
    def vincular(self, request):
        item_id = request.data.get('item_conferencia_id')
        atendimento_id = request.data.get('atendimento_id')
        quantidade = request.data.get('quantidade')
        if not item_id or not atendimento_id or quantidade in (None, ''):
            raise ValidationError(
                {'detail': 'item_conferencia_id, atendimento_id e quantidade são obrigatórios.'},
            )
        try:
            item_conf = ItemNFeEntradaConferencia.objects.select_related(
                'conferencia',
                'produto',
            ).get(pk=int(item_id))
            atendimento = AtendimentoEstoque.objects.get(pk=int(atendimento_id))
        except (TypeError, ValueError, ItemNFeEntradaConferencia.DoesNotExist, AtendimentoEstoque.DoesNotExist) as exc:
            raise ValidationError({'detail': 'item_conferencia_id ou atendimento_id inválido.'}) from exc
        try:
            linha, atend = vincular_item_conferencia_a_atendimento(item_conf, atendimento, quantidade)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        atend.refresh_from_db()
        item_conf.refresh_from_db()
        return response.Response(montar_resposta_vinculo(atend, item_conf, linha=linha))

    @action(detail=False, methods=['post'], url_path='desvincular')
    def desvincular(self, request):
        linha_id = request.data.get('linha_id')
        if not linha_id:
            raise ValidationError({'linha_id': 'Obrigatório.'})
        try:
            atend, item_conf = desvincular_linha_atendimento(int(linha_id))
        except (TypeError, ValueError, AtendimentoEstoqueLinha.DoesNotExist) as exc:
            raise ValidationError({'linha_id': 'Linha de atendimento inválida.'}) from exc
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return response.Response(montar_resposta_vinculo(atend, item_conf, linha=None))


class EstoqueSaldosConsolidadosViewSet(viewsets.ViewSet):
    """Saldos físicos + compromissos antecipados por produto (read-only)."""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        produto_id = request.query_params.get('produto_id')
        pid = None
        if produto_id not in (None, ''):
            try:
                pid = int(produto_id)
            except ValueError as exc:
                raise ValidationError({'produto_id': 'produto_id inválido.'}) from exc
        payload = listar_saldos_consolidados(produto_id=pid)
        if pid is not None and len(payload) == 1:
            return response.Response(payload[0])
        return response.Response(payload)
