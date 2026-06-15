from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import response, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from apps.qualidade.models import Certificado
from apps.comercial.models import ItemPedidoCompra
from apps.produtos.models import Produto

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination

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
    NFeEntradaAgrupamentoConferencia,
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
    AlocacaoAtendimentoSerializer,
    AtendimentoEstoqueListSerializer,
    CTeEntradaOperacionalSerializer,
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
    NFeNumeracaoConfiguracaoSerializer,
    NFeSaidaListSerializer,
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


class NFeEntradaViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = (
        NFeEntrada.objects.select_related(
            'fornecedor',
            'empresa_emitente',
            'cliente_destinatario',
            'pedido_compra',
            'cte',
        )
        .prefetch_related('itens__produto', 'itens__corrida')
        .all()
    )
    serializer_class = NFeEntradaSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_serializer_class(self):
        if getattr(self, 'action', None) == 'list':
            from .serializers import NFeEntradaListSerializer

            return NFeEntradaListSerializer
        return NFeEntradaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(chave_acesso__icontains=search)
                | Q(fornecedor__razao_social__icontains=search)
                | Q(fornecedor__cnpj__icontains=search)
                | Q(empresa_emitente__razao_social__icontains=search)
                | Q(cliente_destinatario__razao_social__icontains=search),
            )
        fornecedor_id = self.request.query_params.get('fornecedor_id')
        if fornecedor_id:
            try:
                qs = qs.filter(fornecedor_id=int(fornecedor_id))
            except (TypeError, ValueError):
                pass
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'data': 'data', 'numero': 'numero', 'valor_total': 'valor_total'},
            '-id',
        )

    def perform_destroy(self, instance):
        if instance.tipo_origem == NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_IMPORTADA:
            instance.delete()
            return
        reverter_todos_itens_entrada(instance)
        instance.delete()

    @action(
        detail=False,
        methods=['post'],
        url_path='importar-entrada-propria-emitida',
        parser_classes=[MultiPartParser],
    )
    def importar_entrada_propria_emitida(self, request):
        from .nfe_import.service_entrada_propria import importar_arquivos_entrada_propria_emitida

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
            batch.append((getattr(f, 'name', '') or 'entrada_propria.xml', raw))
        result = importar_arquivos_entrada_propria_emitida(batch)
        return response.Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='validar-emissao-homologacao')
    def validar_emissao_homologacao(self, request, pk=None):
        from apps.fiscal.nfe_entrada_emissao.resposta import montar_resposta_validacao_entrada
        from apps.fiscal.nfe_entrada_emissao.validacao import validar_pre_emissao_homologacao_entrada

        nf = self.get_object()
        validacao = validar_pre_emissao_homologacao_entrada(nf, exigir_numeracao=False)
        payload = montar_resposta_validacao_entrada(validacao, nf=nf)
        status_code = status.HTTP_200_OK if payload['ok'] else status.HTTP_409_CONFLICT
        return response.Response(payload, status=status_code)

    @action(detail=True, methods=['get'], url_path='preview-xml-oficial')
    def preview_xml_oficial(self, request, pk=None):
        from apps.fiscal.nfe_entrada_emissao.xml_oficial import gerar_preview_xml_oficial_nfe_entrada

        nf = self.get_object()
        payload = gerar_preview_xml_oficial_nfe_entrada(nf)
        if payload.get('bloqueado'):
            return response.Response(payload, status=status.HTTP_409_CONFLICT)
        if str(request.query_params.get('download', '')).lower() in ('1', 'true', 'yes'):
            from django.http import HttpResponse

            return HttpResponse(
                payload.get('xml', ''),
                content_type='application/xml; charset=utf-8',
                headers={
                    'Content-Disposition': f'attachment; filename="nf-entrada-oficial-previa-{nf.pk}.xml"',
                },
            )
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='gerar-xml-oficial-emissao')
    def gerar_xml_oficial_emissao(self, request, pk=None):
        from apps.fiscal.nfe_entrada_emissao.xml_oficial import gerar_xml_oficial_nfe_entrada

        nf = self.get_object()
        payload = gerar_xml_oficial_nfe_entrada(nf, persistir=True)
        if payload.get('bloqueado'):
            return response.Response(payload, status=status.HTTP_409_CONFLICT)
        return response.Response(payload)

    @action(detail=True, methods=['get'], url_path='xml-gerado')
    def xml_gerado(self, request, pk=None):
        nf = self.get_object()
        xml = (nf.xml_nfe_gerado or '').strip()
        if not xml:
            return response.Response(
                {'detail': 'Nenhum XML oficial gerado para esta NF-e entrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if str(request.query_params.get('download', '')).lower() in ('1', 'true', 'yes'):
            from django.http import HttpResponse

            return HttpResponse(
                xml,
                content_type='application/xml; charset=utf-8',
                headers={
                    'Content-Disposition': f'attachment; filename="nf-entrada-gerado-{nf.pk}.xml"',
                },
            )
        return response.Response(
            {
                'nf_entrada_id': nf.pk,
                'xml': xml,
                'status_emissao_sefaz': nf.status_emissao_sefaz or '',
                'sem_autorizacao': True,
            },
        )

    @action(detail=True, methods=['post'], url_path='reservar-numeracao')
    def reservar_numeracao(self, request, pk=None):
        from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError
        from apps.fiscal.nfe_entrada_emissao.numeracao import reservar_numeracao_nfe_entrada

        nf = self.get_object()
        try:
            num = reservar_numeracao_nfe_entrada(nf, usuario=request.user)
        except NFeNumeracaoError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        nf.refresh_from_db()
        return response.Response(
            {
                'ok': True,
                'nf_entrada_id': nf.pk,
                'serie_nfe': num.serie,
                'numero_nfe': num.nnf,
                'chave_acesso': nf.chave_acesso,
                'status_emissao_sefaz': nf.status_emissao_sefaz,
            },
        )


class NFeSaidaViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
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
    pagination_class = NexusPageNumberPagination

    def get_serializer_class(self):
        if getattr(self, 'action', None) == 'list':
            return NFeSaidaListSerializer
        return NFeSaidaSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if getattr(self, 'action', None) == 'list':
            ctx['listagem'] = True
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(numero_nfe__icontains=search)
                | Q(chave_acesso__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(pedido_venda__numero__icontains=search)
                | Q(faturamento_pedido_venda__numero_faturamento__icontains=search),
            )
        status_f = (self.request.query_params.get('status') or '').strip()
        if status_f:
            qs = qs.filter(status__icontains=status_f)
        status_emissao = (self.request.query_params.get('status_emissao') or '').strip()
        if status_emissao:
            qs = qs.filter(status_emissao_sefaz__iexact=status_emissao)
        cliente_id = self.request.query_params.get('cliente_id')
        if cliente_id:
            try:
                qs = qs.filter(cliente_id=int(cliente_id))
            except (TypeError, ValueError):
                pass

        ambiente = (self.request.query_params.get('ambiente') or '').strip().lower()
        if ambiente == 'homologacao':
            qs = qs.filter(
                Q(ambiente_emissao__iexact='homologacao')
                | Q(status_emissao_sefaz__icontains='HOMOLOGACAO'),
            )
        elif ambiente == 'producao':
            qs = qs.filter(ambiente_emissao__iexact='producao')

        data_de = (self.request.query_params.get('data_de') or '').strip()
        if data_de:
            qs = qs.filter(data__gte=data_de)
        data_ate = (self.request.query_params.get('data_ate') or '').strip()
        if data_ate:
            qs = qs.filter(data__lte=data_ate)

        if (self.request.query_params.get('tem_duplicatas') or '').strip().lower() in (
            '1',
            'true',
            'yes',
        ):
            qs = qs.filter(quantidade_parcelas__gt=0)

        reforma_st = (self.request.query_params.get('reforma_tributaria_status') or '').strip()
        if reforma_st:
            from apps.fiscal.reforma_tributaria.config import status_reforma_nfe_documento

            ids = [nf.pk for nf in qs if status_reforma_nfe_documento(nf) == reforma_st]
            qs = qs.filter(pk__in=ids) if ids else qs.none()

        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {
                'data': 'data',
                'numero': 'numero',
                'valor_total': 'valor_total',
                'status': 'status',
                'numero_nfe': 'numero_nfe',
            },
            '-id',
        )

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

    @action(detail=True, methods=['post'], url_path='descartar-rascunho')
    def descartar_rascunho(self, request, pk=None):
        """Descarte interno de NF-e rascunho — sem evento SEFAZ."""
        from apps.fiscal.nfe_saida_ciclo_vida import descartar_nfe_rascunho

        nf = self.get_object()
        try:
            resultado = descartar_nfe_rascunho(
                nf,
                motivo=request.data.get('motivo') or '',
                usuario=request.user,
                liberar_faturamento=True,
            )
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Falha ao descartar rascunho NF-e id=%s', pk)
            return response.Response(
                {'detail': 'Não foi possível descartar o rascunho da NF-e.'},
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
        from apps.fiscal.nfe_perf import medir_nfe_perf
        from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida

        nf = self.get_object()
        modo = (request.query_params.get('modo') or 'abertura').strip().lower()
        incluir_checklist = request.query_params.get('incluir_checklist', '').lower() in (
            '1',
            'true',
            'yes',
        )
        with medir_nfe_perf('abrir_nfe', nfe_id=nf.pk, modo=modo):
            payload = montar_conferencia_nfe_saida(
                nf,
                modo=modo,
                incluir_checklist=incluir_checklist if incluir_checklist else None,
                usuario=request.user,
            )
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='salvar-conferencia')
    def salvar_conferencia(self, request, pk=None):
        """Salva complementos da conferência e retorna payload leve (sem checklist pesado)."""
        from apps.fiscal.nfe_perf import medir_nfe_perf
        from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida

        nf = self.get_object()
        serializer = self.get_serializer(nf, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with medir_nfe_perf('salvar_conferencia', nfe_id=nf.pk):
            serializer.save()
        nf.refresh_from_db()
        conf = montar_conferencia_nfe_saida(nf, modo='abertura', incluir_checklist=False, usuario=request.user)
        return response.Response({'conferencia': conf, 'prontidao': conf.get('prontidao')})

    @action(detail=True, methods=['post'], url_path='salvar-e-validar-conferencia')
    def salvar_e_validar_conferencia(self, request, pk=None):
        """Salva complementos e valida em uma única requisição."""
        from apps.fiscal.nfe_saida_prontidao import validar_conferencia_nfe

        nf = self.get_object()
        serializer = self.get_serializer(nf, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        nf.refresh_from_db()
        try:
            resultado = validar_conferencia_nfe(nf, usuario=request.user)
        except ValueError as exc:
            return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(resultado)

    @action(detail=True, methods=['get'], url_path='alocacoes-atendimento')
    def alocacoes_atendimento(self, request, pk=None):
        """ERP 4.0.12 — alocações operacionais vinculadas à NF-e (sem efeito fiscal)."""
        from apps.comercial.services.alocacao_atendimento_service import listar_alocacoes_por_nfe_saida
        from apps.comercial.services.resumo_atendimento_operacional import obter_resumo_atendimento_operacional

        nf = self.get_object()
        qs = listar_alocacoes_por_nfe_saida(nf.pk)
        return response.Response(
            {
                'alocacoes': AlocacaoAtendimentoSerializer(qs, many=True).data,
                'count': qs.count(),
                'resumo_atendimento_operacional': obter_resumo_atendimento_operacional(
                    nf,
                    contexto='nfe_saida',
                ),
            },
        )

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

    @action(detail=True, methods=['get'], url_path='preview-xml-preliminar')
    def preview_xml_preliminar(self, request, pk=None):
        """NF-e 4.0.1 — XML preliminar NF-e 4.00 (chave calculada, homologação, sem SEFAZ)."""
        from apps.fiscal.nfe_integracao.nfe_xml_preliminar import (
            NFeXmlPreliminarError,
            gerar_resultado_xml_preliminar,
        )

        nf = self.get_object()
        try:
            payload = gerar_resultado_xml_preliminar(nf)
        except NFeXmlPreliminarError as exc:
            return response.Response({'mensagem': str(exc), 'bloqueado': True}, status=400)
        if payload.get('bloqueado'):
            return response.Response(payload, status=status.HTTP_409_CONFLICT)
        if str(request.query_params.get('download', '')).lower() in ('1', 'true', 'yes'):
            from django.http import HttpResponse

            return HttpResponse(
                payload.get('xml', ''),
                content_type='application/xml; charset=utf-8',
                headers={
                    'Content-Disposition': (
                        f'attachment; filename="nfe-preliminar-{nf.pk}.xml"'
                    ),
                },
            )
        return response.Response(payload)

    @action(detail=False, methods=['post'], url_path='checklist-homologacao')
    def checklist_homologacao_create(self, request):
        """ERP 4.0.13.5 — checklist fiscal pré-homologação (sem transmitir / sem efeitos)."""
        from apps.comercial.models import FaturamentoPedidoVenda, PedidoVenda
        from apps.fiscal.nfe_saida_checklist_homologacao import validar_prontidao_nfe_homologacao

        pedido = fat = nf = None
        pid = request.data.get('pedido_venda_id')
        fid = request.data.get('faturamento_id')
        nid = request.data.get('nfe_saida_id')
        try:
            if pid:
                pedido = PedidoVenda.objects.get(pk=int(pid))
            if fid:
                fat = FaturamentoPedidoVenda.objects.get(pk=int(fid))
            if nid:
                nf = self.get_queryset().get(pk=int(nid))
        except (PedidoVenda.DoesNotExist, FaturamentoPedidoVenda.DoesNotExist, NFeSaida.DoesNotExist, TypeError, ValueError):
            return response.Response({'detail': 'Referência inválida para checklist.'}, status=status.HTTP_404_NOT_FOUND)
        if not any([pedido, fat, nf]):
            return response.Response(
                {'detail': 'Informe pedido_venda_id, faturamento_id ou nfe_saida_id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(
            validar_prontidao_nfe_homologacao(pedido_venda=pedido, faturamento=fat, nfe_saida=nf),
        )

    @action(detail=True, methods=['post'], url_path='checklist-homologacao')
    def checklist_homologacao(self, request, pk=None):
        """ERP 4.0.13.5 — checklist fiscal pré-homologação para NF-e existente."""
        from apps.fiscal.nfe_saida_checklist_homologacao import validar_prontidao_nfe_homologacao

        nf = self.get_object()
        return response.Response(validar_prontidao_nfe_homologacao(nfe_saida=nf))

    @action(detail=True, methods=['post'], url_path='reservar-numeracao')
    def reservar_numeracao(self, request, pk=None):
        """NF-e 4.0.2 — reserva numeração fiscal homologação."""
        from apps.fiscal.nfe_emissao.servico import (
            NFeEmissaoHomologacaoError,
            reservar_numeracao_nfe_saida,
        )

        nf = self.get_object()
        try:
            payload = reservar_numeracao_nfe_saida(nf, usuario=request.user)
        except (ValueError, NFeEmissaoHomologacaoError) as exc:
            return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='xml-transmissao-homologacao')
    def xml_transmissao_homologacao(self, request, pk=None):
        """Gera XML limpo de transmissão homologação + higienização."""
        from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError
        from apps.fiscal.nfe_emissao.xml_oficial import NFeXmlEmissaoError
        from apps.fiscal.nfe_xml_transmissao import montar_payload_xml_transmissao_homologacao

        nf = self.get_object()
        try:
            payload = montar_payload_xml_transmissao_homologacao(nf)
        except (NFeXmlEmissaoError, NFeEmissaoHomologacaoError, ValueError) as exc:
            return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='validar-higienizacao-xml')
    def validar_higienizacao_xml(self, request, pk=None):
        from apps.fiscal.nfe_xml_transmissao import validar_xml_transmissao_existente

        nf = self.get_object()
        xml = (request.data.get('xml') or '').strip()
        if not xml and nf.chave_acesso and nf.indicadores_fiscais_confirmados:
            try:
                from apps.fiscal.nfe_xml_transmissao import gerar_xml_transmissao_homologacao

                xml = gerar_xml_transmissao_homologacao(nf).decode('utf-8')
            except Exception as exc:
                return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not xml:
            return response.Response(
                {'mensagem': 'Informe o XML ou confirme indicadores e reserve numeração.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(validar_xml_transmissao_existente(nf, xml))

    @action(detail=True, methods=['post'], url_path='gerar-xml-oficial-emissao')
    def gerar_xml_oficial_emissao(self, request, pk=None):
        from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError, gerar_xml_nfe_saida_oficial

        nf = self.get_object()
        try:
            payload = gerar_xml_nfe_saida_oficial(nf, usuario=request.user)
        except (ValueError, NFeEmissaoHomologacaoError) as exc:
            return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='assinar-xml-emissao')
    def assinar_xml_emissao(self, request, pk=None):
        from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError, assinar_xml_nfe_saida

        nf = self.get_object()
        try:
            payload = assinar_xml_nfe_saida(nf, usuario=request.user)
        except (ValueError, NFeEmissaoHomologacaoError) as exc:
            return response.Response({'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='corrigir-serie-homologacao')
    def corrigir_serie_homologacao(self, request, pk=None):
        """Recalcula série/chave homologação (ex.: 900 → 0 após cStat 266)."""
        from apps.fiscal.nfe_emissao.corrigir_serie_homologacao import (
            NFeCorrigirSerieHomologacaoError,
            corrigir_serie_homologacao_nfe,
            pode_corrigir_serie_homologacao,
        )

        nf = self.get_object()
        ok, motivo = pode_corrigir_serie_homologacao(nf)
        if not ok:
            return response.Response({'ok': False, 'mensagem': motivo}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = corrigir_serie_homologacao_nfe(nf, usuario=request.user)
        except NFeCorrigirSerieHomologacaoError as exc:
            return response.Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        payload['ok'] = True
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='emitir-homologacao')
    def emitir_homologacao(self, request, pk=None):
        """NF-e 4.0.2 — emissão real SEFAZ homologação (sem produção / estoque / financeiro)."""
        import logging

        from apps.fiscal.nfe_emissao.assinatura import NFeAssinaturaError
        from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError
        from apps.fiscal.nfe_emissao.resposta import montar_resposta_emissao_homologacao
        from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError, emitir_nfe_homologacao
        from apps.fiscal.nfe_emissao.transmissao import NFeTransmissaoError
        from apps.fiscal.nfe_emissao.validacao import NFeEmissaoValidacaoError
        from apps.fiscal.nfe_emissao.xml_oficial import NFeXmlEmissaoError
        from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error

        log = logging.getLogger(__name__)
        nf = self.get_object()
        try:
            payload = emitir_nfe_homologacao(nf, usuario=request.user)
        except NFeEmissaoValidacaoError as exc:
            payload = montar_resposta_emissao_homologacao(
                nf,
                ok=False,
                mensagem=exc.mensagens[0] if exc.mensagens else str(exc),
                erros=exc.mensagens,
            )
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        except NFeEmissaoHomologacaoError as exc:
            det = getattr(exc, 'detalhes', None) or {}
            erros = det.get('erros') or [str(exc)]
            etapa = str(det.get('etapa') or getattr(exc, 'etapa', '') or '')
            nf.refresh_from_db()
            payload = montar_resposta_emissao_homologacao(
                nf,
                ok=False,
                mensagem=str(exc),
                erros=erros if isinstance(erros, list) else [str(erros)],
                cstat=str(det.get('cStat') or det.get('cstat') or nf.cstat_autorizacao or ''),
                xmotivo=str(det.get('xMotivo') or det.get('xmotivo') or nf.motivo_autorizacao or ''),
                etapa=etapa,
            )
            payload.update(
                {
                    'numero_nfe': nf.numero_nfe or payload.get('numero_nfe'),
                    'serie_nfe': nf.serie_nfe or payload.get('serie_nfe'),
                    'chave_acesso': nf.chave_acesso or payload.get('chave_acesso'),
                },
            )
            from apps.fiscal.nfe_emissao.xsd_erros import aplicar_erros_validacao_no_payload

            aplicar_erros_validacao_no_payload(payload, det, mensagem=str(exc))
            payload['status'] = nf.status_emissao_sefaz or nf.status
            return response.Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (NFeXmlEmissaoError, NFeAssinaturaError, NFeNumeracaoError, NFeTransmissaoError, CertificadoA1Error) as exc:
            etapa = getattr(exc, 'etapa', '') or 'PRE_TRANSMISSAO'
            log.warning('Emissão homologação bloqueada nfe_id=%s etapa=%s: %s', pk, etapa, exc)
            nf.refresh_from_db()
            payload = montar_resposta_emissao_homologacao(
                nf,
                ok=False,
                mensagem=str(exc),
                erros=[str(exc)],
                etapa=etapa,
            )
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            payload = montar_resposta_emissao_homologacao(nf, ok=False, mensagem=str(exc), erros=[str(exc)])
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            log.exception('Erro técnico emissão homologação nfe_id=%s', pk)
            payload = montar_resposta_emissao_homologacao(
                nf,
                ok=False,
                mensagem='Erro técnico ao transmitir para a SEFAZ. Tente novamente ou contate o suporte.',
                erros=['erro_tecnico'],
            )
            return response.Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        code = status.HTTP_200_OK if payload.get('ok') else status.HTTP_422_UNPROCESSABLE_ENTITY
        return response.Response(payload, status=code)

    @action(detail=True, methods=['get'], url_path='validar-emissao-producao')
    def validar_emissao_producao(self, request, pk=None):
        """Checklist read-only pré-emissão produção SEFAZ (Fase 3B — sem transmitir)."""
        from apps.fiscal.nfe_emissao.validacao_producao import montar_validacao_emissao_producao

        nf = self.get_object()
        return response.Response(montar_validacao_emissao_producao(nf))

    @action(detail=True, methods=['post'], url_path='emitir-producao')
    def emitir_producao(self, request, pk=None):
        """NF-e 4.0.15.x Fase 3B — emissão produção SEFAZ (flag + confirmação; sem UI)."""
        import logging

        from apps.fiscal.nfe_emissao.assinatura import NFeAssinaturaError
        from apps.fiscal.nfe_emissao.config_producao import (
            MSG_PRODUCAO_NAO_HABILITADA,
            NFeProducaoConfirmacaoError,
            NFeProducaoDesabilitadaError,
            nfe_producao_habilitada,
        )
        from apps.fiscal.nfe_emissao.permissoes_producao import (
            MSG_SEM_PERMISSAO_USUARIO,
            usuario_pode_emitir_nfe_producao,
        )
        from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError
        from apps.fiscal.nfe_emissao.resposta_producao import montar_resposta_emissao_producao
        from apps.fiscal.nfe_emissao.servico_producao import NFeEmissaoProducaoError, emitir_nfe_producao
        from apps.fiscal.nfe_emissao.transmissao_producao import NFeTransmissaoProducaoError
        from apps.fiscal.nfe_emissao.validacao import NFeEmissaoValidacaoError
        from apps.fiscal.nfe_emissao.xml_oficial import NFeXmlEmissaoError
        from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error

        log = logging.getLogger(__name__)
        nf = self.get_object()

        if not nfe_producao_habilitada():
            payload = montar_resposta_emissao_producao(
                nf,
                ok=False,
                mensagem=MSG_PRODUCAO_NAO_HABILITADA,
                erros=[MSG_PRODUCAO_NAO_HABILITADA],
            )
            return response.Response(payload, status=status.HTTP_403_FORBIDDEN)

        if not usuario_pode_emitir_nfe_producao(request.user):
            payload = montar_resposta_emissao_producao(
                nf,
                ok=False,
                mensagem=MSG_SEM_PERMISSAO_USUARIO,
                erros=[MSG_SEM_PERMISSAO_USUARIO],
            )
            return response.Response(payload, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = emitir_nfe_producao(
                nf,
                usuario=request.user,
                confirmacao_payload=request.data if isinstance(request.data, dict) else {},
            )
        except NFeProducaoDesabilitadaError as exc:
            payload = montar_resposta_emissao_producao(
                nf,
                ok=False,
                mensagem=str(exc),
                erros=[str(exc)],
            )
            return response.Response(payload, status=status.HTTP_403_FORBIDDEN)
        except NFeProducaoConfirmacaoError as exc:
            payload = montar_resposta_emissao_producao(
                nf,
                ok=False,
                mensagem=str(exc),
                erros=[str(exc)],
                etapa='CONFIRMACAO',
            )
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        except NFeEmissaoValidacaoError as exc:
            payload = montar_resposta_emissao_producao(
                nf,
                ok=False,
                mensagem=exc.mensagens[0] if exc.mensagens else str(exc),
                erros=exc.mensagens,
            )
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        except NFeEmissaoProducaoError as exc:
            det = getattr(exc, 'detalhes', None) or {}
            erros = det.get('erros') or [str(exc)]
            etapa = str(det.get('etapa') or getattr(exc, 'etapa', '') or '')
            nf.refresh_from_db()
            payload = montar_resposta_emissao_producao(
                nf,
                ok=False,
                mensagem=str(exc),
                erros=erros if isinstance(erros, list) else [str(erros)],
                cstat=str(det.get('cStat') or det.get('cstat') or nf.cstat_autorizacao or ''),
                xmotivo=str(det.get('xMotivo') or det.get('xmotivo') or nf.motivo_autorizacao or ''),
                etapa=etapa,
            )
            payload.update(
                {
                    'numero_nfe': nf.numero_nfe or payload.get('numero_nfe'),
                    'serie_nfe': nf.serie_nfe or payload.get('serie_nfe'),
                    'chave_acesso': nf.chave_acesso or payload.get('chave_acesso'),
                },
            )
            from apps.fiscal.nfe_emissao.xsd_erros import aplicar_erros_validacao_no_payload

            aplicar_erros_validacao_no_payload(payload, det, mensagem=str(exc))
            payload['status'] = nf.status_emissao_sefaz or nf.status
            return response.Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (NFeXmlEmissaoError, NFeAssinaturaError, NFeNumeracaoError, NFeTransmissaoProducaoError, CertificadoA1Error) as exc:
            etapa = getattr(exc, 'etapa', '') or 'PRE_TRANSMISSAO'
            log.warning('Emissão produção bloqueada nfe_id=%s etapa=%s: %s', pk, etapa, exc)
            nf.refresh_from_db()
            payload = montar_resposta_emissao_producao(
                nf,
                ok=False,
                mensagem=str(exc),
                erros=[str(exc)],
                etapa=etapa,
            )
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            payload = montar_resposta_emissao_producao(nf, ok=False, mensagem=str(exc), erros=[str(exc)])
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            log.exception('Erro técnico emissão produção nfe_id=%s', pk)
            payload = montar_resposta_emissao_producao(
                nf,
                ok=False,
                mensagem='Erro técnico ao transmitir NF-e produção. Tente novamente ou contate o suporte.',
                erros=['erro_tecnico'],
            )
            return response.Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        code = status.HTTP_200_OK if payload.get('ok') else status.HTTP_422_UNPROCESSABLE_ENTITY
        return response.Response(payload, status=code)

    @action(detail=True, methods=['post'], url_path='consultar-situacao-sefaz')
    def consultar_situacao_sefaz(self, request, pk=None):
        """Consulta situação da NF-e na SEFAZ (read-only — sem emitir/cancelar/corrigir)."""
        import logging

        from apps.fiscal.nfe_emissao.consulta_situacao import (
            NFeConsultaSituacaoError,
            consultar_situacao_nfe_saida,
        )
        from apps.fiscal.nfe_emissao.resposta_consulta import montar_resposta_consulta_situacao
        from apps.fiscal.nfe_integracao.adapters.consulta_situacao_parser import (
            ResultadoConsultaSituacaoSefaz,
        )
        from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error

        log = logging.getLogger(__name__)
        nf = self.get_object()
        try:
            payload = consultar_situacao_nfe_saida(nf, usuario=request.user)
        except NFeConsultaSituacaoError as exc:
            nf.refresh_from_db()
            payload = montar_resposta_consulta_situacao(
                nf,
                ResultadoConsultaSituacaoSefaz(
                    ok=False,
                    c_stat_consulta='',
                    x_motivo_consulta=str(exc),
                    c_stat_nfe='',
                    x_motivo_nfe='',
                    protocolo='',
                    chave_acesso=nf.chave_acesso or '',
                    dh_recbto='',
                    tp_amb='',
                    xml_retorno='',
                    autorizada=False,
                    cancelada=False,
                    denegada=False,
                ),
                ok=False,
                mensagem=str(exc),
            )
            etapa = getattr(exc, 'etapa', '')
            if etapa == 'CERTIFICADO':
                return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return response.Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except CertificadoA1Error as exc:
            nf.refresh_from_db()
            payload = montar_resposta_consulta_situacao(
                nf,
                ResultadoConsultaSituacaoSefaz(
                    ok=False,
                    c_stat_consulta='',
                    x_motivo_consulta=str(exc),
                    c_stat_nfe='',
                    x_motivo_nfe='',
                    protocolo='',
                    chave_acesso=nf.chave_acesso or '',
                    dh_recbto='',
                    tp_amb='',
                    xml_retorno='',
                    autorizada=False,
                    cancelada=False,
                    denegada=False,
                ),
                ok=False,
                mensagem=str(exc),
            )
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            log.exception('Erro técnico consulta SEFAZ nfe_id=%s', pk)
            nf.refresh_from_db()
            payload = montar_resposta_consulta_situacao(
                nf,
                ResultadoConsultaSituacaoSefaz(
                    ok=False,
                    c_stat_consulta='',
                    x_motivo_consulta='Erro técnico na consulta SEFAZ.',
                    c_stat_nfe='',
                    x_motivo_nfe='',
                    protocolo='',
                    chave_acesso=nf.chave_acesso or '',
                    dh_recbto='',
                    tp_amb='',
                    xml_retorno='',
                    autorizada=False,
                    cancelada=False,
                    denegada=False,
                ),
                ok=False,
                mensagem='Erro técnico ao consultar a SEFAZ. Tente novamente ou contate o suporte.',
            )
            return response.Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        code = status.HTTP_200_OK if payload.get('ok') else status.HTTP_422_UNPROCESSABLE_ENTITY
        return response.Response(payload, status=code)

    def _nf_cce_com_relacionamentos(self, pk=None):
        return (
            NFeSaida.objects.select_related('cliente', 'empresa_emitente', 'pedido_venda')
            .filter(pk=pk or self.kwargs.get('pk'))
            .first()
        )

    @action(detail=True, methods=['get'], url_path='carta-correcao/dados')
    def carta_correcao_dados(self, request, pk=None):
        """Contexto read-only da CC-e (emitente, sequência prevista, CC-e anteriores) — sem transmissão."""
        from apps.fiscal.nfe_emissao.carta_correcao import NFeCartaCorrecaoError, pode_emitir_carta_correcao
        from apps.fiscal.nfe_emissao.carta_correcao_dados import (
            NFeCartaCorrecaoDadosError,
            montar_dados_contexto_cce,
        )

        nf = self._nf_cce_com_relacionamentos(pk) or self.get_object()
        pode, motivo = pode_emitir_carta_correcao(nf)
        if not pode:
            return response.Response({'ok': False, 'mensagem': motivo}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = montar_dados_contexto_cce(nf)
        except NFeCartaCorrecaoDadosError as exc:
            return response.Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='previa-carta-correcao')
    def previa_carta_correcao(self, request, pk=None):
        """Prévia read-only da CC-e — valida texto e retorna dados confiáveis; não transmite à SEFAZ."""
        from apps.fiscal.nfe_emissao.carta_correcao import NFeCartaCorrecaoError, pode_emitir_carta_correcao
        from apps.fiscal.nfe_emissao.carta_correcao_dados import (
            NFeCartaCorrecaoDadosError,
            montar_dados_previa_cce,
        )

        nf = self._nf_cce_com_relacionamentos(pk) or self.get_object()
        pode, motivo = pode_emitir_carta_correcao(nf)
        if not pode:
            return response.Response({'ok': False, 'mensagem': motivo}, status=status.HTTP_400_BAD_REQUEST)
        texto = request.data.get('texto_correcao', request.data.get('correcao', ''))
        try:
            payload = montar_dados_previa_cce(nf, texto_correcao=texto)
        except NFeCartaCorrecaoError as exc:
            return response.Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except NFeCartaCorrecaoDadosError as exc:
            return response.Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='previa-carta-correcao/pdf')
    def previa_carta_correcao_pdf(self, request, pk=None):
        """PDF de prévia da CC-e — somente leitura, sem transmissão à SEFAZ."""
        from django.http import HttpResponse

        from apps.fiscal.nfe_emissao.carta_correcao import NFeCartaCorrecaoError, pode_emitir_carta_correcao
        from apps.fiscal.nfe_emissao.carta_correcao_dados import (
            NFeCartaCorrecaoDadosError,
            montar_dados_previa_cce,
        )
        from apps.fiscal.nfe_emissao.carta_correcao_pdf import gerar_pdf_previa_cce

        nf = self._nf_cce_com_relacionamentos(pk) or self.get_object()
        pode, motivo = pode_emitir_carta_correcao(nf)
        if not pode:
            return response.Response({'ok': False, 'mensagem': motivo}, status=status.HTTP_400_BAD_REQUEST)
        texto = request.data.get('texto_correcao', request.data.get('correcao', ''))
        try:
            dados = montar_dados_previa_cce(nf, texto_correcao=texto)
            pdf = gerar_pdf_previa_cce(dados)
        except NFeCartaCorrecaoError as exc:
            return response.Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except NFeCartaCorrecaoDadosError as exc:
            return response.Response({'ok': False, 'mensagem': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        filename = f'previa-cce-nfe-{nf.numero or nf.pk}.pdf'
        return HttpResponse(
            pdf,
            content_type='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="{filename}"',
                'Cache-Control': 'no-store, no-cache, must-revalidate',
                'Pragma': 'no-cache',
                'X-Cce-Pdf-Tipo': 'previa',
            },
        )

    @action(
        detail=True,
        methods=['get'],
        url_path=r'comprovante-carta-correcao/(?P<evento_id>[^/.]+)',
    )
    def comprovante_carta_correcao_pdf(self, request, pk=None, evento_id=None):
        """PDF comprovante de CC-e já transmitida — não é DANFE."""
        from django.http import HttpResponse

        from apps.fiscal.models import NFeSaidaEvento
        from apps.fiscal.nfe_emissao.carta_correcao_dados import (
            NFeCartaCorrecaoDadosError,
            montar_dados_comprovante_cce,
        )
        from apps.fiscal.nfe_emissao.carta_correcao_pdf import gerar_pdf_comprovante_cce

        nf = self.get_object()
        try:
            evento_pk = int(evento_id)
        except (TypeError, ValueError):
            return response.Response({'detail': 'Evento inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        evento = (
            NFeSaidaEvento.objects.select_related('nfe_saida', 'nfe_saida__cliente', 'criado_por')
            .filter(pk=evento_pk, nfe_saida_id=nf.pk)
            .first()
        )
        if not evento:
            return response.Response({'detail': 'Evento de CC-e não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            dados = montar_dados_comprovante_cce(evento)
            pdf = gerar_pdf_comprovante_cce(dados)
        except NFeCartaCorrecaoDadosError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        seq = dados.get('sequencia_evento') or evento_pk
        filename = f'comprovante-cce-nfe-{nf.numero or nf.pk}-seq-{seq}.pdf'
        return HttpResponse(
            pdf,
            content_type='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="{filename}"',
                'Cache-Control': 'no-store, no-cache, must-revalidate',
                'Pragma': 'no-cache',
                'X-Cce-Pdf-Tipo': 'comprovante',
            },
        )

    @action(detail=True, methods=['post'], url_path='emitir-carta-correcao')
    def emitir_carta_correcao(self, request, pk=None):
        """Emite Carta de Correção Eletrônica (CC-e) — evento SEFAZ, sem alterar XML autorizado."""
        import logging

        from apps.fiscal.nfe_emissao.carta_correcao import (
            NFeCartaCorrecaoError,
            emitir_carta_correcao_nfe_saida,
        )
        from apps.fiscal.nfe_emissao.resposta_carta_correcao import montar_resposta_carta_correcao
        from apps.fiscal.nfe_integracao.adapters.carta_correcao_parser import ResultadoCartaCorrecaoSefaz
        from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error

        log = logging.getLogger(__name__)
        nf = self.get_object()
        texto = request.data.get('texto_correcao', request.data.get('correcao', ''))

        def _payload_erro(msg: str, *, ok: bool = False) -> dict:
            nf.refresh_from_db()
            return montar_resposta_carta_correcao(
                nf,
                ResultadoCartaCorrecaoSefaz(
                    ok=ok,
                    c_stat_lote='',
                    x_motivo_lote=msg,
                    c_stat_evento='',
                    x_motivo_evento='',
                    protocolo='',
                    chave_acesso=nf.chave_acesso or '',
                    n_seq_evento='',
                    tp_evento='110110',
                    dh_reg_evento='',
                    tp_amb='',
                    id_evento='',
                    xml_retorno='',
                ),
                ok=False,
                mensagem=msg,
                texto_correcao=texto.strip() if texto else '',
            )

        try:
            payload = emitir_carta_correcao_nfe_saida(nf, texto_correcao=texto, usuario=request.user)
        except NFeCartaCorrecaoError as exc:
            payload = _payload_erro(str(exc))
            etapa = getattr(exc, 'etapa', '')
            if etapa in ('CERTIFICADO', 'EMITENTE'):
                return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
            if etapa == 'VALIDACAO':
                return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return response.Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except CertificadoA1Error as exc:
            return response.Response(_payload_erro(str(exc)), status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            log.exception('Erro técnico CC-e nfe_id=%s', pk)
            return response.Response(
                _payload_erro('Erro técnico ao transmitir Carta de Correção. Tente novamente ou contate o suporte.'),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        code = status.HTTP_200_OK if payload.get('ok') else status.HTTP_422_UNPROCESSABLE_ENTITY
        return response.Response(payload, status=code)

    @action(detail=True, methods=['post'], url_path='reprocessar-retorno-sefaz')
    def reprocessar_retorno_sefaz(self, request, pk=None):
        """Reinterpreta xml_retorno salvo (lote 104 + infProt) sem retransmitir."""
        from apps.fiscal.nfe_emissao.resposta import montar_resposta_emissao_homologacao
        from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError, reprocessar_retorno_nfe_homologacao

        nf = self.get_object()
        try:
            payload = reprocessar_retorno_nfe_homologacao(nf, usuario=request.user)
        except NFeEmissaoHomologacaoError as exc:
            nf.refresh_from_db()
            payload = montar_resposta_emissao_homologacao(nf, ok=False, mensagem=str(exc), erros=[str(exc)])
            return response.Response(payload, status=status.HTTP_400_BAD_REQUEST)
        code = status.HTTP_200_OK if payload.get('ok') else status.HTTP_422_UNPROCESSABLE_ENTITY
        return response.Response(payload, status=code)

    @action(detail=True, methods=['get'], url_path='xml-nfe')
    def download_xml_nfe(self, request, pk=None):
        from django.http import HttpResponse

        nf = self.get_object()
        xml = (nf.xml_nfe_gerado or '').strip()
        if not xml:
            from apps.fiscal.nfe_emissao.xml_oficial import gerar_xml_oficial_emissao

            try:
                xml = gerar_xml_oficial_emissao(nf).decode('utf-8')
            except Exception as exc:
                return response.Response({'mensagem': str(exc)}, status=404)
        return HttpResponse(
            xml,
            content_type='application/xml; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename="nfe-{nf.pk}-nfe.xml"'},
        )

    @action(detail=True, methods=['get'], url_path='xml-assinado')
    def download_xml_assinado(self, request, pk=None):
        from django.http import HttpResponse

        nf = self.get_object()
        xml = (nf.xml_assinado or '').strip()
        if not xml:
            return response.Response({'mensagem': 'XML assinado indisponível.'}, status=404)
        return HttpResponse(
            xml,
            content_type='application/xml; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename="nfe-{nf.pk}-assinado.xml"'},
        )

    @action(detail=True, methods=['get'], url_path='xml-lote-enviado')
    def download_xml_lote_enviado(self, request, pk=None):
        from django.http import HttpResponse

        nf = self.get_object()
        xml = (nf.xml_envio_lote or nf.xml_envio or '').strip()
        if not xml:
            return response.Response({'mensagem': 'XML do lote enviNFe indisponível.'}, status=404)
        return HttpResponse(
            xml,
            content_type='application/xml; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename="nfe-{nf.pk}-enviNFe.xml"'},
        )

    @action(detail=True, methods=['get'], url_path='xml-retorno-sefaz')
    def download_xml_retorno_sefaz(self, request, pk=None):
        from django.http import HttpResponse

        nf = self.get_object()
        xml = (nf.xml_retorno_lote or nf.xml_retorno or '').strip()
        if not xml:
            return response.Response({'mensagem': 'XML de retorno SEFAZ indisponível.'}, status=404)
        return HttpResponse(
            xml,
            content_type='application/xml; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename="nfe-{nf.pk}-retorno-sefaz.xml"'},
        )

    @action(detail=True, methods=['post'], url_path='validar-xml-schema')
    def validar_xml_schema(self, request, pk=None):
        from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError, validar_xml_nfe_saida_schema

        nf = self.get_object()
        try:
            payload = validar_xml_nfe_saida_schema(nf, usuario=request.user)
        except NFeEmissaoHomologacaoError as exc:
            return response.Response({'ok': False, 'mensagem': str(exc), 'erros': [str(exc)]}, status=400)
        code = status.HTTP_200_OK if payload.get('ok') else status.HTTP_422_UNPROCESSABLE_ENTITY
        return response.Response(payload, status=code)

    @action(detail=True, methods=['get'], url_path='xml-autorizado')
    def download_xml_autorizado(self, request, pk=None):
        from django.http import HttpResponse

        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import DanfeBfrError
        from apps.fiscal.nfe_integracao.danfe_xml_autorizado import resolver_xml_autorizado_danfe
        from apps.fiscal.nfe_saida_arquivo_autorizado import (
            content_disposition_attachment,
            nome_arquivo_xml_autorizado,
        )

        nf = self.get_object()
        try:
            xml = resolver_xml_autorizado_danfe(nf)
        except DanfeBfrError as exc:
            return response.Response({'mensagem': str(exc)}, status=404)
        if not (xml or '').strip():
            return response.Response({'mensagem': 'XML autorizado indisponível.'}, status=404)
        filename = nome_arquivo_xml_autorizado(nf)
        return HttpResponse(
            xml,
            content_type='application/xml; charset=utf-8',
            headers={'Content-Disposition': content_disposition_attachment(filename)},
        )

    @action(detail=True, methods=['get'], url_path='danfe-homologacao')
    def danfe_homologacao(self, request, pk=None):
        """Alias legado — delega para danfe-autorizado."""
        return self.danfe_autorizado(request, pk=pk)

    @action(detail=True, methods=['get'], url_path='danfe-autorizado')
    def danfe_autorizado(self, request, pk=None):
        from django.http import HttpResponse

        from apps.fiscal.danfe_render import DanfeBfrRenderError
        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import DanfeBfrError
        from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao, nf_autorizada_producao
        from apps.fiscal.nfe_saida_danfe_autorizado import gerar_danfe_autorizado_nfe_saida

        nf = self.get_object()
        if not (nf_autorizada_producao(nf) or nf_autorizada_homologacao(nf)):
            return response.Response(
                {'mensagem': 'DANFE autorizado disponível apenas após autorização SEFAZ.'},
                status=status.HTTP_409_CONFLICT,
            )
        from apps.fiscal.nfe_saida_arquivo_autorizado import (
            content_disposition_attachment,
            nome_arquivo_danfe_autorizado,
        )

        try:
            pdf, meta = gerar_danfe_autorizado_nfe_saida(nf)
        except (DanfeBfrRenderError, DanfeBfrError) as exc:
            payload = {
                'detail': str(exc),
                'mensagens': [str(exc)],
                'bloqueado': True,
                'render_engine': 'brazil_fiscal_report_erro',
                'renderer_oficial': 'BFR',
                'trace_id': getattr(exc, 'trace_id', None),
                'nfe_saida_id': nf.pk,
                'numero': nf.numero,
            }
            return response.Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not pdf:
            return response.Response(
                {'mensagem': 'Não foi possível gerar o DANFE autorizado.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        filename = nome_arquivo_danfe_autorizado(nf)
        headers = {
            'Content-Disposition': content_disposition_attachment(filename),
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
            'X-Danfe-Renderer-Oficial': 'BFR',
            'X-Danfe-Origem': str(meta.get('danfe_origem', '')),
            'X-Danfe-Renderer-Label': str(meta.get('danfe_renderer_label', '')),
        }
        if meta.get('render_engine'):
            headers['X-Danfe-Renderer'] = str(meta.get('render_engine'))
        return HttpResponse(pdf, content_type='application/pdf', headers=headers)

    @action(detail=True, methods=['get'], url_path='financeiro/preview-contas-receber')
    def preview_contas_receber(self, request, pk=None):
        """ERP 4.0.14.3 — preview de contas a receber (sem persistir)."""
        from apps.fiscal.nfe_saida_financeiro import preview_contas_receber_de_nfe

        nf = self.get_object()
        try:
            payload = preview_contas_receber_de_nfe(nf)
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='financeiro/gerar-contas-receber')
    def gerar_contas_receber(self, request, pk=None):
        """ERP 4.0.14.3 — gera contas a receber após confirmação explícita."""
        from apps.financeiro.serializers import TituloFinanceiroSerializer
        from apps.fiscal.nfe_saida_financeiro import gerar_contas_receber_de_nfe_autorizada, montar_flags_financeiro_nfe
        from apps.fiscal.serializers import NFeGerarContasReceberSerializer

        nf = self.get_object()
        ser = NFeGerarContasReceberSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        parcelas = [
            {
                'numero_parcela': p.get('numero_parcela'),
                'vencimento': p['vencimento'].isoformat(),
                'valor': str(p['valor']),
                'observacoes': p.get('observacoes') or '',
            }
            for p in data['parcelas']
        ]
        try:
            titulo = gerar_contas_receber_de_nfe_autorizada(
                nf,
                parcelas=parcelas,
                categoria_id=data.get('categoria'),
                centro_custo_id=data.get('centro_custo'),
                forma_pagamento_prevista_codigo=data.get('forma_pagamento_prevista_codigo') or '',
                conta_financeira_prevista_id=data.get('conta_financeira_prevista'),
                observacoes=data.get('observacoes') or '',
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        flags = montar_flags_financeiro_nfe(nf)
        return response.Response(
            {
                'mensagem': 'Contas a receber geradas com sucesso.',
                'titulo': TituloFinanceiroSerializer(titulo, context={'request': request, 'detail': True}).data,
                **flags,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='financeiro/contas-receber')
    def contas_receber_vinculadas(self, request, pk=None):
        """ERP 4.0.14.3 — títulos financeiros vinculados à NF-e."""
        from apps.financeiro.models import TituloFinanceiro
        from apps.financeiro.serializers import TituloFinanceiroSerializer
        from apps.fiscal.nfe_saida_financeiro import montar_flags_financeiro_nfe, titulos_vinculados_nfe

        nf = self.get_object()
        qs = titulos_vinculados_nfe(nf).select_related('cliente', 'categoria', 'centro_custo')
        flags = montar_flags_financeiro_nfe(nf)
        return response.Response(
            {
                **flags,
                'contas_receber': TituloFinanceiroSerializer(qs, many=True, context={'request': request}).data,
            },
        )

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

        from apps.fiscal.danfe_render import DanfeBfrRenderError
        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import DanfeBfrError
        from apps.fiscal.nfe_perf import medir_nfe_perf

        nf = self.get_object()
        try:
            with medir_nfe_perf('preview_danfe', nfe_id=nf.pk) as perf:
                pdf, meta = gerar_preview_danfe_nfe_saida(nf)
                perf.marcar('pdf_gerado')
        except (DanfeBfrRenderError, DanfeBfrError) as exc:
            payload = {
                'detail': str(exc),
                'mensagens': [str(exc)],
                'bloqueado': True,
                'render_engine': 'brazil_fiscal_report_erro',
                'renderer_oficial': 'BFR',
                'trace_id': getattr(exc, 'trace_id', None),
                'nfe_saida_id': nf.pk,
                'numero': nf.numero,
            }
            return response.Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if meta.get('bloqueado'):
            return response.Response(meta, status=status.HTTP_409_CONFLICT)
        headers = {
            'Content-Disposition': f'inline; filename="{meta["filename"]}"',
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
        }
        if meta.get('render_engine'):
            headers['X-Danfe-Renderer'] = str(meta.get('render_engine'))
        headers['X-Danfe-Renderer-Oficial'] = 'BFR'
        if meta.get('danfe_origem'):
            headers['X-Danfe-Origem'] = str(meta.get('danfe_origem'))
        if meta.get('danfe_renderer_label'):
            headers['X-Danfe-Renderer-Label'] = str(meta.get('danfe_renderer_label'))
        if settings.DEBUG and meta.get('pdf_page_count') is not None:
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


class NFeEntradaHistoricaImportadaViewSet(AutocompleteOrPaginationMixin, viewsets.ReadOnlyModelViewSet):
    """NF-e de entrada importadas por XML (origem externa, base fiscal/gerencial)."""

    queryset = NFeEntradaHistoricaImportada.objects.select_related('empresa_destinataria', 'fornecedor_emitente').all()
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(chave_acesso__icontains=search)
                | Q(numero__icontains=search)
                | Q(fornecedor_emitente__razao_social__icontains=search),
            )
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
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'dh_emissao': 'dh_emissao', 'numero': 'numero', 'importado_em': 'importado_em'},
            '-importado_em',
        )

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
                Prefetch(
                    'agrupamentos',
                    queryset=NFeEntradaAgrupamentoConferencia.objects.select_related(
                        'produto_interno_resultante',
                        'item_pedido_compra',
                        'usuario_confirmacao',
                    ).prefetch_related('itens__item_nfe_conferencia__item_nfe_historico'),
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

    @action(detail=True, methods=['post'], url_path='conferencia/confirmar-equivalencia')
    @transaction.atomic
    def confirmar_equivalencia(self, request, pk=None):
        nf = self.get_queryset().get(pk=pk)
        conferencia = self._get_or_build_conferencia(nf)
        payload = request.data or {}
        from apps.produtos.equivalencia_servico import (
            EquivalenciaOperacionalError,
            confirmar_agrupamento_equivalencia,
        )

        try:
            agr = confirmar_agrupamento_equivalencia(
                conferencia,
                produto_interno_id=int(payload['produto_interno_id']),
                item_pedido_compra_id=payload.get('item_pedido_compra_id'),
                itens_nfe_conferencia_ids=[int(x) for x in payload.get('itens_nfe_conferencia_ids') or []],
                tipo_agrupamento=payload.get('tipo_agrupamento') or 'equivalencia_composta',
                quantidade_equivalente=payload.get('quantidade_equivalente') or '0',
                confianca=int(payload.get('confianca') or 0),
                motivo_confirmacao=str(payload.get('motivo_confirmacao') or ''),
                salvar_regra_fornecedor=bool(payload.get('salvar_regra_fornecedor')),
                usuario=request.user,
            )
        except (EquivalenciaOperacionalError, KeyError, ValueError, TypeError) as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        conferencia = self._conferencia_com_relacionamentos(conferencia.id) or conferencia
        return response.Response(
            {
                'agrupamento_id': agr.id,
                'conferencia': NFeEntradaConferenciaSerializer(conferencia).data,
                'mensagem': 'Equivalência confirmada para conferência. Estoque não foi movimentado.',
            },
        )

    @action(detail=True, methods=['post'], url_path='conferencia/rejeitar-equivalencia')
    @transaction.atomic
    def rejeitar_equivalencia(self, request, pk=None):
        nf = self.get_queryset().get(pk=pk)
        conferencia = self._get_or_build_conferencia(nf)
        payload = request.data or {}
        from apps.produtos.equivalencia_servico import rejeitar_sugestao_equivalencia

        agr = rejeitar_sugestao_equivalencia(
            conferencia,
            produto_interno_id=int(payload['produto_interno_id']),
            itens_nfe_conferencia_ids=[int(x) for x in payload.get('itens_nfe_conferencia_ids') or []],
            motivo=str(payload.get('motivo') or ''),
            usuario=request.user,
        )
        conferencia = self._conferencia_com_relacionamentos(conferencia.id) or conferencia
        return response.Response(
            {
                'agrupamento_id': agr.id,
                'conferencia': NFeEntradaConferenciaSerializer(conferencia).data,
            },
        )

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

    @action(detail=True, methods=['get'], url_path='financeiro/preview-contas-pagar')
    def preview_contas_pagar(self, request, pk=None):
        """ERP 4.0.14.4 — preview de contas a pagar (sem persistir)."""
        from apps.fiscal.nfe_entrada_financeiro import preview_contas_pagar_de_nfe_entrada

        nf = self.get_object()
        try:
            payload = preview_contas_pagar_de_nfe_entrada(nf)
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(payload)

    @action(detail=True, methods=['post'], url_path='financeiro/gerar-contas-pagar')
    def gerar_contas_pagar(self, request, pk=None):
        """ERP 4.0.14.4 — gera contas a pagar após confirmação explícita."""
        from apps.financeiro.serializers import TituloFinanceiroSerializer
        from apps.fiscal.nfe_entrada_financeiro import gerar_contas_pagar_de_nfe_entrada, montar_flags_financeiro_nfe_entrada
        from apps.fiscal.serializers import NFeGerarContasPagarSerializer

        nf = self.get_object()
        ser = NFeGerarContasPagarSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        parcelas = [
            {
                'numero_parcela': p.get('numero_parcela'),
                'vencimento': p['vencimento'].isoformat(),
                'valor': str(p['valor']),
                'observacoes': p.get('observacoes') or '',
            }
            for p in data['parcelas']
        ]
        try:
            titulo = gerar_contas_pagar_de_nfe_entrada(
                nf,
                parcelas=parcelas,
                categoria_id=data.get('categoria'),
                centro_custo_id=data.get('centro_custo'),
                forma_pagamento_prevista_codigo=data.get('forma_pagamento_prevista_codigo') or '',
                conta_financeira_prevista_id=data.get('conta_financeira_prevista'),
                observacoes=data.get('observacoes') or '',
                confirmar_pendencias_operacionais=bool(data.get('confirmar_pendencias_operacionais')),
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        flags = montar_flags_financeiro_nfe_entrada(nf)
        return response.Response(
            {
                'mensagem': 'Contas a pagar geradas com sucesso.',
                'titulo': TituloFinanceiroSerializer(titulo, context={'request': request, 'detail': True}).data,
                **flags,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='financeiro/contas-pagar')
    def contas_pagar_vinculadas(self, request, pk=None):
        """ERP 4.0.14.4 — títulos financeiros vinculados à NF-e Entrada."""
        from apps.financeiro.serializers import TituloFinanceiroSerializer
        from apps.fiscal.nfe_entrada_financeiro import montar_flags_financeiro_nfe_entrada, titulos_vinculados_nfe_entrada

        nf = self.get_object()
        qs = titulos_vinculados_nfe_entrada(nf).select_related('fornecedor', 'categoria', 'centro_custo')
        flags = montar_flags_financeiro_nfe_entrada(nf)
        return response.Response(
            {
                **flags,
                'contas_pagar': TituloFinanceiroSerializer(qs, many=True, context={'request': request}).data,
            },
        )


class CTeEntradaViewSet(AutocompleteOrPaginationMixin, viewsets.ReadOnlyModelViewSet):
    """Lista CT-es conferidos na base importada (sem efeito financeiro/expedição automático)."""

    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination
    serializer_class = CTeEntradaOperacionalSerializer

    def get_queryset(self):
        from .cte_historico_conferencia import queryset_cte_entrada_operacional

        qs = queryset_cte_entrada_operacional()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(chave_acesso__icontains=search)
                | Q(transportadora__razao_social__icontains=search)
                | Q(empresa_tomadora__razao_social__icontains=search),
            )
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'data': 'dh_emissao', 'numero': 'numero', 'valor_frete': 'valor_total_servico'},
            '-dh_emissao',
        )


class CTeHistoricoImportadoViewSet(AutocompleteOrPaginationMixin, viewsets.ReadOnlyModelViewSet):
    """CT-e importados por XML (origem externa, base fiscal/logística/gerencial)."""

    queryset = CTeHistoricoImportado.objects.select_related(
        'transportadora',
        'empresa_tomadora',
        'conferido_por',
    ).all()
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        incluir_cancelados = str(self.request.query_params.get('incluir_cancelados', '')).lower() in {'1', 'true', 'sim'}
        if not incluir_cancelados:
            qs = qs.filter(cancelado=False)
        if self.action == 'retrieve':
            return qs.prefetch_related('eventos')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(chave_acesso__icontains=search)
                | Q(numero__icontains=search)
                | Q(transportadora__razao_social__icontains=search),
            )
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
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'dh_emissao': 'dh_emissao', 'numero': 'numero', 'valor_total_nf': 'valor_total_nf'},
            '-dh_emissao',
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return CTeHistoricoImportadoListSerializer
        return CTeHistoricoImportadoSerializer

    @action(detail=True, methods=['post'], url_path='conferir')
    def conferir(self, request, pk=None):
        from .cte_historico_conferencia import ConferenciaCteErro, conferir_cte_importado, serializar_resposta_conferencia

        cte = self.get_object()
        try:
            cte = conferir_cte_importado(cte, request.user, request.data or {})
        except ConferenciaCteErro as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(serializar_resposta_conferencia(cte))

    @action(detail=True, methods=['post'], url_path='marcar-divergente')
    def marcar_divergente(self, request, pk=None):
        from .cte_historico_conferencia import ConferenciaCteErro, marcar_cte_importado_divergente, serializar_resposta_conferencia

        cte = self.get_object()
        try:
            cte = marcar_cte_importado_divergente(
                cte,
                request.user,
                motivo=str((request.data or {}).get('motivo') or ''),
                observacao=str((request.data or {}).get('observacao') or ''),
            )
        except ConferenciaCteErro as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(serializar_resposta_conferencia(cte))

    @action(detail=True, methods=['post'], url_path='ignorar-operacional')
    def ignorar_operacional(self, request, pk=None):
        from .cte_historico_conferencia import (
            ConferenciaCteErro,
            ignorar_cte_importado_operacionalmente,
            serializar_resposta_conferencia,
        )

        cte = self.get_object()
        try:
            cte = ignorar_cte_importado_operacionalmente(
                cte,
                request.user,
                motivo=str((request.data or {}).get('motivo') or ''),
                observacao=str((request.data or {}).get('observacao') or ''),
            )
        except ConferenciaCteErro as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(serializar_resposta_conferencia(cte))

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
        search = (request.query_params.get('search') or '').strip()
        if search:
            s = search.lower()
            payload = [
                row for row in payload
                if s in (row.get('codigo') or '').lower()
                or s in (row.get('descricao') or '').lower()
            ]
        if (request.query_params.get('page') or '').strip() or (
            request.query_params.get('page_size') or ''
        ).strip():
            from nexus_erp.pagination import paginate_sequence
            return paginate_sequence(request, payload)
        return response.Response(payload)


class AtendimentoEstoqueViewSet(AutocompleteOrPaginationMixin, viewsets.ReadOnlyModelViewSet):
    """Compromissos de atendimento de estoque."""

    serializer_class = AtendimentoEstoqueListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = queryset_atendimentos_estoque()
        try:
            qs = filtrar_atendimentos_estoque(qs, self.request.query_params)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'detail': 'Parâmetro de filtro inválido.'}) from exc
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(produto__codigo_completo__icontains=search)
                | Q(produto__descricao__icontains=search)
                | Q(nf_saida__numero__icontains=search)
                | Q(nf_saida__cliente__razao_social__icontains=search)
                | Q(nf_saida__pedido_venda__numero__icontains=search),
            )
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'criado_em': 'criado_em', 'status': 'status'},
            '-criado_em',
        )

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


class AlocacaoAtendimentoViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    """ERP 4.0.12 — gestão de intenção operacional por item (sem estoque/financeiro)."""

    serializer_class = AlocacaoAtendimentoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        from apps.comercial.services.alocacao_atendimento_service import filtrar_alocacoes

        params: dict = {}
        p = self.request.query_params
        int_keys = {
            'pedido_venda',
            'pedido_venda_item',
            'faturamento',
            'nfe_saida',
            'produto',
            'fornecedor',
        }
        for key in (*int_keys, 'tipo_atendimento', 'status_entrada_fiscal', 'origem_fisica', 'destino_fisico'):
            val = (p.get(key) or '').strip()
            if not val:
                continue
            if key in int_keys:
                try:
                    params[key] = int(val)
                except ValueError:
                    continue
            else:
                params[key] = val
        qs = filtrar_alocacoes(params)
        search = (p.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(produto__codigo_completo__icontains=search)
                | Q(produto__descricao__icontains=search)
                | Q(observacao_operacional__icontains=search),
            )
        return aplicar_ordering(
            qs,
            p.get('ordering'),
            {'criado_em': 'criado_em', 'quantidade_necessaria': 'quantidade_necessaria'},
            '-criado_em',
        )

    def destroy(self, request, *args, **kwargs):
        from apps.comercial.services.alocacao_atendimento_service import (
            AlocacaoAtendimentoErro,
            excluir_alocacao_atendimento,
        )

        instance = self.get_object()
        try:
            excluir_alocacao_atendimento(instance)
        except AlocacaoAtendimentoErro as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(status=status.HTTP_204_NO_CONTENT)

    def _opcoes_params(self, request) -> dict:
        return {k: v for k, v in request.query_params.items()}

    @action(detail=False, methods=['get'], url_path='opcoes/fornecedores')
    def opcoes_fornecedores(self, request):
        from apps.comercial.services.alocacao_atendimento_busca import buscar_fornecedores_opcoes

        return response.Response(buscar_fornecedores_opcoes(self._opcoes_params(request)))

    @action(detail=False, methods=['get'], url_path='opcoes/pedidos-compra')
    def opcoes_pedidos_compra(self, request):
        from apps.comercial.services.alocacao_atendimento_busca import buscar_pedidos_compra_opcoes

        return response.Response(buscar_pedidos_compra_opcoes(self._opcoes_params(request)))

    @action(detail=False, methods=['get'], url_path='opcoes/pedidos-compra-itens')
    def opcoes_pedidos_compra_itens(self, request):
        from apps.comercial.services.alocacao_atendimento_busca import buscar_pedidos_compra_itens_opcoes

        return response.Response(buscar_pedidos_compra_itens_opcoes(self._opcoes_params(request)))

    @action(detail=False, methods=['get'], url_path='opcoes/nfe-entrada-importada')
    def opcoes_nfe_entrada_importada(self, request):
        from apps.comercial.services.alocacao_atendimento_busca import buscar_nfe_entrada_importada_opcoes

        return response.Response(buscar_nfe_entrada_importada_opcoes(self._opcoes_params(request)))

    @action(detail=False, methods=['get'], url_path='opcoes/nfe-entrada-importada-itens')
    def opcoes_nfe_entrada_importada_itens(self, request):
        from apps.comercial.services.alocacao_atendimento_busca import buscar_nfe_entrada_importada_itens_opcoes

        return response.Response(buscar_nfe_entrada_importada_itens_opcoes(self._opcoes_params(request)))

    @action(detail=False, methods=['get'], url_path='opcoes/cte-importado-conferido')
    def opcoes_cte_importado_conferido(self, request):
        from apps.comercial.services.alocacao_atendimento_busca import buscar_cte_conferido_opcoes

        return response.Response(buscar_cte_conferido_opcoes(self._opcoes_params(request)))


class AtendimentosOperacionaisViewSet(AutocompleteOrPaginationMixin, viewsets.GenericViewSet):
    """ERP 4.0.13.1 — visão consolidada de AlocacaoAtendimento (sem estoque/financeiro)."""

    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        from apps.comercial.services.atendimentos_operacionais_service import (
            filtrar_atendimentos_operacionais,
            parse_filtros_query_params,
        )

        params = parse_filtros_query_params(self.request.query_params)
        qs = filtrar_atendimentos_operacionais(params)
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {
                'criado_em': 'criado_em',
                'quantidade_pendente': 'quantidade_pendente',
                'quantidade_necessaria': 'quantidade_necessaria',
            },
            '-criado_em',
        )

    def list(self, request, *args, **kwargs):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_kpis_atendimentos_operacionais,
            filtrar_atendimentos_operacionais,
            parse_filtros_query_params,
            serializar_atendimento_operacional,
        )

        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            results = [serializar_atendimento_operacional(obj) for obj in page]
            resp = self.get_paginated_response(results)
            if (request.query_params.get('incluir_kpis') or '').strip().lower() in ('1', 'true', 'yes'):
                filtros = parse_filtros_query_params(request.query_params)
                resp.data['kpis'] = calcular_kpis_atendimentos_operacionais(
                    filtrar_atendimentos_operacionais(filtros),
                )
            return resp

        results = [serializar_atendimento_operacional(obj) for obj in qs]
        payload: dict = {
            'count': len(results),
            'page': 1,
            'page_size': len(results) or 20,
            'total_pages': 1 if results else 0,
            'next': None,
            'previous': None,
            'results': results,
        }
        if (request.query_params.get('incluir_kpis') or '').strip().lower() in ('1', 'true', 'yes'):
            filtros = parse_filtros_query_params(request.query_params)
            payload['kpis'] = calcular_kpis_atendimentos_operacionais(
                filtrar_atendimentos_operacionais(filtros),
            )
        return response.Response(payload)

    def retrieve(self, request, pk=None):
        from apps.comercial.services.atendimentos_operacionais_service import serializar_atendimento_operacional

        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return response.Response({'detail': 'Não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return response.Response(serializar_atendimento_operacional(obj))

    @action(detail=False, methods=['get'], url_path='kpis')
    def kpis(self, request):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_kpis_atendimentos_operacionais,
            filtrar_atendimentos_operacionais,
            parse_filtros_query_params,
        )

        params = parse_filtros_query_params(request.query_params)
        return response.Response(calcular_kpis_atendimentos_operacionais(filtrar_atendimentos_operacionais(params)))


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


class NFeNumeracaoConfiguracaoViewSet(viewsets.ModelViewSet):
    """NF-e 4.0.2 — numeração fiscal por empresa e ambiente."""

    serializer_class = NFeNumeracaoConfiguracaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from apps.fiscal.models import NFeNumeracaoConfiguracao

        qs = NFeNumeracaoConfiguracao.objects.select_related('empresa').order_by(
            'empresa_id',
            'ambiente',
            'serie',
        )
        empresa_id = self.request.query_params.get('empresa_id') or self.request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        return qs
