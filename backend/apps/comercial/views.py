import logging

from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .converter_proposta_pedido import (
    ACAO_CANCELAR,
    ACAO_MANTER_PENDENTE,
    converter_proposta_em_pedido_venda,
    gerar_pedido_venda_de_proposta,
    recuperar_proposta_comercial,
)
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento

from .faturamento_pedido_venda import (
    cancelar_faturamento_pedido,
    confirmar_faturamento_pedido,
    criar_faturamento_pedido,
    estornar_faturamento_pedido,
    montar_resumo_faturamento,
    reparar_vinculo_faturamento_nfe,
)
from .observed_metrics import (
    montar_apoio_gerencial,
    montar_referencia_comercial_custo_compra,
    montar_referencia_comercial_frete,
)
from .commercial_defaults import ultima_mensagem_comercial_vendedor
from .models import FaturamentoPedidoVenda, PedidoCompra, PedidoVenda, Proposta, Vendedor
from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.view_mixins import FriendlyDestroyMixin
from nexus_erp.pagination import NexusPageNumberPagination
from .comercial_pdf_shared import pdf_http_response
from .pedido_compra_pdf import gerar_pedido_compra_pdf_bytes
from .pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from .proposta_pdf import gerar_proposta_pdf_bytes
from .proposta_comercial_historico import listar_historico_comercial
from .homologacao_cenario_fiscal import (
    aprovar_homologacao_cenario_fiscal,
    iniciar_homologacao_cenario_fiscal,
    listar_historico_homologacao_fiscal,
    montar_homologacao_fiscal_proposta,
    recalcular_homologacao_cenario_fiscal,
    reprovar_homologacao_cenario_fiscal,
    voltar_legado_homologacao_cenario_fiscal,
)
from .serializers import PedidoCompraSerializer, PedidoVendaSerializer, PropostaSerializer

logger = logging.getLogger(__name__)


class PropostaViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = (
        Proposta.objects.select_related(
            'cliente', 'empresa_emitente', 'cenario_fiscal_saida', 'vendedor_ref',
        )
        .prefetch_related(
            'itens__produto',
            'itens__proposta__cenario_fiscal_saida',
            'itens__itens_pedido_venda__pedido',
            'itens__pedido_venda_gerado',
            'itens__item_pedido_venda_gerado__pedido',
            'pedidos_gerados',
        )
        .all()
    )
    serializer_class = PropostaSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(cliente__nome_fantasia__icontains=search)
                | Q(cliente_avulso_nome__icontains=search),
            )
        status_f = (self.request.query_params.get('status') or '').strip()
        if status_f:
            qs = qs.filter(status__icontains=status_f)
        cliente_id = self.request.query_params.get('cliente_id')
        if cliente_id:
            try:
                qs = qs.filter(cliente_id=int(cliente_id))
            except (TypeError, ValueError):
                pass
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'data': 'data', 'numero': 'numero', 'valor_total': 'valor_total', 'status': 'status'},
            '-id',
        )

    @action(detail=False, methods=['get'], url_path='sugestao-nova')
    def sugestao_nova(self, request):
        vendedor_ref = None
        raw_vid = (request.query_params.get('vendedor_id') or '').strip()
        if raw_vid:
            try:
                vendedor_ref = Vendedor.objects.filter(pk=int(raw_vid), ativo=True).first()
            except (TypeError, ValueError):
                pass
        return Response(
            {
                'mensagem_comercial': ultima_mensagem_comercial_vendedor(
                    vendedor_ref=vendedor_ref,
                    usuario=request.user,
                ),
            },
        )

    @action(detail=False, methods=['get'], url_path='apoio-gerencial')
    def apoio_gerencial(self, request):
        try:
            result = montar_apoio_gerencial(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=False, methods=['get'], url_path='referencia-comercial-frete')
    def referencia_comercial_frete(self, request):
        try:
            result = montar_referencia_comercial_frete(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=False, methods=['get'], url_path='referencia-comercial-custo-compra')
    def referencia_comercial_custo_compra(self, request):
        try:
            result = montar_referencia_comercial_custo_compra(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=True, methods=['post'], url_path='converter-pedido')
    def converter_pedido(self, request, pk=None):
        proposta = self.get_object()
        try:
            resultado = converter_proposta_em_pedido_venda(proposta)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='gerar-pedido')
    def gerar_pedido(self, request, pk=None):
        proposta = self.get_object()
        data = request.data if isinstance(request.data, dict) else {}
        itens = data.get('itens')
        acao = (data.get('acao_itens_nao_selecionados') or ACAO_MANTER_PENDENTE).strip().upper()
        if acao not in (ACAO_MANTER_PENDENTE, ACAO_CANCELAR):
            return Response(
                {'detail': 'acao_itens_nao_selecionados deve ser MANTER_PENDENTE ou CANCELAR.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = gerar_pedido_venda_de_proposta(
                proposta,
                itens_payload=itens if isinstance(itens, list) else None,
                acao_itens_nao_selecionados=acao,
                observacao=str(data.get('observacao') or ''),
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='recuperar')
    def recuperar(self, request, pk=None):
        proposta = self.get_object()
        data = request.data if isinstance(request.data, dict) else {}
        try:
            resultado = recuperar_proposta_comercial(
                proposta,
                motivo=str(data.get('motivo') or ''),
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='historico-comercial')
    def historico_comercial(self, request, pk=None):
        proposta = self.get_object()
        return Response(listar_historico_comercial(proposta))

    @action(detail=True, methods=['post'], url_path='homologar-cenario-fiscal/iniciar')
    def homologar_cenario_fiscal_iniciar(self, request, pk=None):
        proposta = self.get_object()
        try:
            payload = iniciar_homologacao_cenario_fiscal(
                proposta,
                cenario_fiscal_saida_id=request.data.get('cenario_fiscal_saida_id'),
                observacao=request.data.get('observacao') or '',
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        proposta.refresh_from_db()
        return Response(payload)

    @action(detail=True, methods=['get'], url_path='homologar-cenario-fiscal/resumo')
    def homologar_cenario_fiscal_resumo(self, request, pk=None):
        proposta = self.get_object()
        return Response(montar_homologacao_fiscal_proposta(proposta))

    @action(detail=True, methods=['get'], url_path='homologar-cenario-fiscal/historico')
    def homologar_cenario_fiscal_historico(self, request, pk=None):
        proposta = self.get_object()
        return Response(listar_historico_homologacao_fiscal(proposta))

    @action(detail=True, methods=['post'], url_path='homologar-cenario-fiscal/aprovar')
    def homologar_cenario_fiscal_aprovar(self, request, pk=None):
        proposta = self.get_object()
        try:
            payload = aprovar_homologacao_cenario_fiscal(
                proposta,
                observacao=request.data.get('observacao') or '',
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=True, methods=['post'], url_path='homologar-cenario-fiscal/reprovar')
    def homologar_cenario_fiscal_reprovar(self, request, pk=None):
        proposta = self.get_object()
        try:
            payload = reprovar_homologacao_cenario_fiscal(
                proposta,
                observacao=request.data.get('observacao') or '',
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=True, methods=['post'], url_path='homologar-cenario-fiscal/voltar-legado')
    def homologar_cenario_fiscal_voltar_legado(self, request, pk=None):
        proposta = self.get_object()
        try:
            payload = voltar_legado_homologacao_cenario_fiscal(
                proposta,
                observacao=request.data.get('observacao') or '',
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=True, methods=['post'], url_path='homologar-cenario-fiscal/recalcular')
    def homologar_cenario_fiscal_recalcular(self, request, pk=None):
        proposta = self.get_object()
        try:
            payload = recalcular_homologacao_cenario_fiscal(proposta, usuario=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        proposta = self.get_object()
        try:
            content = gerar_proposta_pdf_bytes(proposta)
        except Exception:
            logger.exception('Falha ao gerar PDF da proposta id=%s', pk)
            return Response(
                {'detail': 'Não foi possível gerar o PDF da proposta. Tente novamente ou contate o suporte.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        safe = (proposta.numero or str(proposta.pk)).replace('/', '-').replace('\\', '-')
        return pdf_http_response(content, filename=f'proposta-{safe}.pdf')


class PedidoVendaViewSet(FriendlyDestroyMixin, AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    destroy_entity_label = 'pedido de venda'
    queryset = (
        PedidoVenda.objects.select_related(
            'cliente', 'proposta', 'empresa_emitente', 'vendedor_ref',
        )
        .prefetch_related('itens__produto', 'itens__corrida')
        .all()
    )
    serializer_class = PedidoVendaSerializer
    pagination_class = NexusPageNumberPagination

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if getattr(self, 'action', None) == 'list':
            ctx['listagem'] = True
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, 'action', None) == 'list':
            from django.db.models import Prefetch
            from apps.fiscal.models import AlocacaoAtendimento

            qs = qs.prefetch_related(
                Prefetch(
                    'itens__alocacoes_atendimento',
                    queryset=AlocacaoAtendimento.objects.select_related(
                        'nf_entrada_item__nf',
                        'pedido_compra_item',
                    ),
                ),
            )
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(cliente__nome_fantasia__icontains=search)
            )
        cliente_id = self.request.query_params.get('cliente_id')
        if cliente_id:
            try:
                qs = qs.filter(cliente_id=int(cliente_id))
            except (TypeError, ValueError):
                pass
        status_f = (self.request.query_params.get('status') or '').strip()
        if status_f:
            qs = qs.filter(status__icontains=status_f)
        proposta_id = self.request.query_params.get('proposta_id')
        if proposta_id:
            try:
                qs = qs.filter(proposta_id=int(proposta_id))
            except (TypeError, ValueError):
                pass
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'data': 'data', 'numero': 'numero', 'valor_total': 'valor_total', 'status': 'status'},
            '-id',
        )

    @action(detail=False, methods=['get'], url_path='apoio-gerencial')
    def apoio_gerencial(self, request):
        try:
            result = montar_apoio_gerencial(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=False, methods=['get'], url_path='referencia-comercial-frete')
    def referencia_comercial_frete(self, request):
        try:
            result = montar_referencia_comercial_frete(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=False, methods=['get'], url_path='referencia-comercial-custo-compra')
    def referencia_comercial_custo_compra(self, request):
        try:
            result = montar_referencia_comercial_custo_compra(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=True, methods=['get'], url_path='resumo-faturamento')
    def resumo_faturamento(self, request, pk=None):
        pedido = self.get_object()
        return Response(montar_resumo_faturamento(pedido))

    @action(detail=True, methods=['post'], url_path='recalcular-totais')
    def recalcular_totais(self, request, pk=None):
        from apps.comercial.serializers import recalcular_pedido_venda

        pedido = self.get_object()
        recalcular_pedido_venda(pedido)
        pedido.refresh_from_db()
        return Response(montar_resumo_faturamento(pedido))

    @action(detail=True, methods=['get'], url_path='alocacoes-atendimento')
    def alocacoes_atendimento(self, request, pk=None):
        """ERP 4.0.12 — listagem de alocações do PV (opcional ?faturamento_id=)."""
        from apps.comercial.services.alocacao_atendimento_service import (
            filtrar_alocacoes,
            listar_alocacoes_por_pedido_venda,
        )
        from apps.comercial.services.resumo_atendimento_operacional import (
            obter_resumo_atendimento_operacional,
        )
        from apps.fiscal.serializers import AlocacaoAtendimentoSerializer

        pedido = self.get_object()
        fid = request.query_params.get('faturamento_id')
        if fid:
            try:
                qs = filtrar_alocacoes({'pedido_venda': pedido.pk, 'faturamento': int(fid)})
            except (TypeError, ValueError):
                return Response({'detail': 'faturamento_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            qs = listar_alocacoes_por_pedido_venda(pedido.pk)
        return Response(
            {
                'alocacoes': AlocacaoAtendimentoSerializer(qs, many=True).data,
                'count': qs.count(),
                'resumo_atendimento_operacional': obter_resumo_atendimento_operacional(
                    pedido,
                    contexto='pedido_venda',
                ),
            },
        )

    @action(detail=True, methods=['post'], url_path='faturamentos')
    def criar_faturamento(self, request, pk=None):
        pedido = self.get_object()
        try:
            resultado = criar_faturamento_pedido(pedido, request.data, usuario=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['post'],
        url_path=r'faturamentos/(?P<faturamento_id>[^/.]+)/confirmar',
    )
    def confirmar_faturamento(self, request, pk=None, faturamento_id=None):
        pedido = self.get_object()
        try:
            fid = int(faturamento_id)
        except (TypeError, ValueError):
            return Response({'detail': 'faturamento_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultado = confirmar_faturamento_pedido(pedido, fid)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)

    @action(
        detail=True,
        methods=['post'],
        url_path=r'faturamentos/(?P<faturamento_id>[^/.]+)/cancelar',
    )
    def cancelar_faturamento(self, request, pk=None, faturamento_id=None):
        pedido = self.get_object()
        try:
            fid = int(faturamento_id)
        except (TypeError, ValueError):
            return Response({'detail': 'faturamento_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultado = cancelar_faturamento_pedido(pedido, fid)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)

    @action(
        detail=True,
        methods=['post'],
        url_path=r'faturamentos/(?P<faturamento_id>[^/.]+)/estornar',
    )
    def estornar_faturamento(self, request, pk=None, faturamento_id=None):
        pedido = self.get_object()
        try:
            fid = int(faturamento_id)
        except (TypeError, ValueError):
            return Response({'detail': 'faturamento_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultado = estornar_faturamento_pedido(
                pedido,
                fid,
                motivo=(request.data.get('motivo') or '').strip(),
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)

    @action(
        detail=True,
        methods=['post'],
        url_path=r'faturamentos/(?P<faturamento_id>[^/.]+)/reparar-vinculo-nfe',
    )
    def reparar_vinculo_nfe_faturamento(self, request, pk=None, faturamento_id=None):
        pedido = self.get_object()
        try:
            fid = int(faturamento_id)
        except (TypeError, ValueError):
            return Response({'detail': 'faturamento_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultado = reparar_vinculo_faturamento_nfe(pedido, fid)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)

    @action(
        detail=True,
        methods=['post'],
        url_path=r'faturamentos/(?P<faturamento_id>[^/.]+)/gerar-nfe-saida',
    )
    def gerar_nfe_saida_faturamento(self, request, pk=None, faturamento_id=None):
        pedido = self.get_object()
        try:
            fid = int(faturamento_id)
        except (TypeError, ValueError):
            return Response({'detail': 'faturamento_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultado = gerar_nfe_saida_from_faturamento(
                pedido,
                fid,
                observacao=request.data.get('observacao') or '',
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        code = status.HTTP_200_OK if resultado['ja_existia'] else status.HTTP_201_CREATED
        return Response(resultado, status=code)

    @action(detail=True, methods=['post'], url_path='checklist-nfe-homologacao')
    def checklist_nfe_homologacao(self, request, pk=None):
        """ERP 4.0.13.5 — checklist fiscal pré-homologação do pedido (sem transmitir)."""
        from apps.fiscal.nfe_saida_checklist_homologacao import validar_prontidao_nfe_homologacao

        pedido = self.get_object()
        fid = request.data.get('faturamento_id')
        fat = None
        if fid:
            try:
                fat = FaturamentoPedidoVenda.objects.get(pk=int(fid), pedido_id=pedido.pk)
            except (FaturamentoPedidoVenda.DoesNotExist, TypeError, ValueError):
                return Response({'detail': 'faturamento_id inválido.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(validar_prontidao_nfe_homologacao(pedido_venda=pedido, faturamento=fat))

    @action(
        detail=True,
        methods=['post'],
        url_path=r'faturamentos/(?P<faturamento_id>[^/.]+)/checklist-nfe-homologacao',
    )
    def checklist_nfe_homologacao_faturamento(self, request, pk=None, faturamento_id=None):
        """ERP 4.0.13.5 — checklist fiscal pré-homologação do faturamento."""
        from apps.fiscal.nfe_saida_checklist_homologacao import validar_prontidao_nfe_homologacao

        pedido = self.get_object()
        try:
            fid = int(faturamento_id)
            fat = FaturamentoPedidoVenda.objects.get(pk=fid, pedido_id=pedido.pk)
        except (FaturamentoPedidoVenda.DoesNotExist, TypeError, ValueError):
            return Response({'detail': 'faturamento_id inválido.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(validar_prontidao_nfe_homologacao(pedido_venda=pedido, faturamento=fat))

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        pedido = self.get_object()
        try:
            content = gerar_pedido_venda_pdf_bytes(pedido)
        except Exception:
            logger.exception('Falha ao gerar PDF do pedido de venda id=%s', pk)
            return Response(
                {'detail': 'Não foi possível gerar o PDF do pedido de venda. Tente novamente ou contate o suporte.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        safe = (pedido.numero or str(pedido.pk)).replace('/', '-').replace('\\', '-')
        return pdf_http_response(content, filename=f'pedido-venda-{safe}.pdf')


class PedidoCompraViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = PedidoCompra.objects.select_related('fornecedor').prefetch_related('itens__produto').all()
    serializer_class = PedidoCompraSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(fornecedor__razao_social__icontains=search)
                | Q(fornecedor__nome_fantasia__icontains=search)
                | Q(fornecedor__cnpj__icontains=search),
            )
        status_f = (self.request.query_params.get('status') or '').strip()
        if status_f:
            qs = qs.filter(status__icontains=status_f)
        fornecedor_id = self.request.query_params.get('fornecedor_id')
        if fornecedor_id:
            try:
                qs = qs.filter(fornecedor_id=int(fornecedor_id))
            except (TypeError, ValueError):
                pass
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'data': 'data', 'numero': 'numero', 'valor_total': 'valor_total', 'status': 'status'},
            '-id',
        )

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        pedido = self.get_object()
        try:
            content = gerar_pedido_compra_pdf_bytes(pedido)
        except Exception:
            logger.exception('Falha ao gerar PDF do pedido de compra id=%s', pk)
            return Response(
                {'detail': 'Não foi possível gerar o PDF do pedido. Tente novamente ou contate o suporte.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        safe = (pedido.numero or str(pedido.pk)).replace('/', '-').replace('\\', '-')
        return pdf_http_response(content, filename=f'pedido-compra-{safe}.pdf')
