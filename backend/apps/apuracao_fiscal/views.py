import csv
from datetime import datetime
from io import StringIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fiscal.services.apuracao_fiscal import build_apuracao_fiscal
from apps.fiscal.services.sped_efd_icms_ipi_txt import gerar_sped_efd_icms_ipi_txt, nome_arquivo_sped

from .models import ApuracaoFiscal, ApuracaoItem
from .serializers import (
    ApuracaoAjusteManualSerializer,
    ApuracaoFiscalListSerializer,
    ApuracaoFiscalSerializer,
    ApuracaoItemSerializer,
    ApuracaoReformaSerializer,
    CriarAjusteManualSerializer,
    CriarRascunhoSerializer,
    ReabrirSerializer,
)
from .services.ajustes import adicionar_ajuste, listar_ajustes, remover_ajuste, resumo_ajustes
from .services.fechamento import (
    ApuracaoFiscalError,
    criar_rascunho,
    fechar_periodo,
    periodo_fiscal_fechado,
    reabrir_periodo,
    usuario_pode_reabrir,
)


def _csv_response(rows: list[list[str]], filename: str) -> HttpResponse:
    buf = StringIO()
    w = csv.writer(buf)
    for row in rows:
        w.writerow(row)
    resp = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


class ApuracaoView(APIView):
    """
    Apuração fiscal gerencial + base futura SPED / reforma tributária.

    GET query params: empresa_id, data_inicio, data_fim, tipo (ENTRADA|SAIDA|AMBOS),
    status, cliente_id, fornecedor_id, cfop, ncm, modelo_documento, incluir_canceladas,
    formato (json|csv_apuracao|csv_alertas). Compat: mes, ano (quando datas omitidas).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        formato = (request.query_params.get('formato') or 'json').strip().lower()
        payload = build_apuracao_fiscal(dict(request.query_params))
        if formato == 'csv_apuracao':
            return self._csv_apuracao(payload)
        if formato == 'csv_alertas':
            return self._csv_alertas(payload)
        return Response(payload)

    def _csv_apuracao(self, payload: dict) -> HttpResponse:
        r_ent = payload.get('resumo', {}).get('entrada', {})
        r_sai = payload.get('resumo', {}).get('saida', {})
        saldo = payload.get('resumo', {}).get('saldo_gerencial_saida_menos_entrada', {})
        cards = payload.get('cards', {})
        rows: list[list[str]] = [
            ['secao', 'campo', 'valor'],
            ['filtros', 'data_inicio', str(payload.get('filtros', {}).get('data_inicio', ''))],
            ['filtros', 'data_fim', str(payload.get('filtros', {}).get('data_fim', ''))],
            ['filtros', 'tipo', str(payload.get('filtros', {}).get('tipo', ''))],
            ['cards', 'notas_entrada', str(cards.get('notas_entrada', ''))],
            ['cards', 'notas_saida', str(cards.get('notas_saida', ''))],
            ['cards', 'valor_entradas', str(cards.get('valor_entradas', ''))],
            ['cards', 'valor_saidas', str(cards.get('valor_saidas', ''))],
            ['cards', 'icms_entrada', str(cards.get('icms_entrada', ''))],
            ['cards', 'icms_saida', str(cards.get('icms_saida', ''))],
            ['cards', 'icms_st_debito_entrada', str(cards.get('icms_st_debito_entrada', ''))],
            ['cards', 'icms_st_debito_saida', str(cards.get('icms_st_debito_saida', ''))],
            ['cards', 'fcp_st_entrada', str(cards.get('fcp_st_entrada', ''))],
            ['cards', 'fcp_st_saida', str(cards.get('fcp_st_saida', ''))],
            ['cards', 'difal_icms_uf_dest', str(cards.get('difal_icms_uf_dest', ''))],
            ['cards', 'ipi_entrada', str(cards.get('ipi_entrada', ''))],
            ['cards', 'ipi_saida', str(cards.get('ipi_saida', ''))],
            ['cards', 'pis_entrada', str(cards.get('pis_entrada', ''))],
            ['cards', 'pis_saida', str(cards.get('pis_saida', ''))],
            ['cards', 'pis_credito', str(cards.get('pis_credito', ''))],
            ['cards', 'pis_debito', str(cards.get('pis_debito', ''))],
            ['cards', 'cofins_entrada', str(cards.get('cofins_entrada', ''))],
            ['cards', 'cofins_saida', str(cards.get('cofins_saida', ''))],
            ['cards', 'cofins_credito', str(cards.get('cofins_credito', ''))],
            ['cards', 'cofins_debito', str(cards.get('cofins_debito', ''))],
            ['cards', 'credito_pis_cofins_bloqueado_regime_itens', str(cards.get('credito_pis_cofins_bloqueado_regime_itens', ''))],
            ['cards', 'cbs', str(cards.get('cbs', ''))],
            ['cards', 'ibs', str(cards.get('ibs', ''))],
            ['cards', 'is', str(cards.get('is', ''))],
            ['cards', 'alertas', str(cards.get('alertas', ''))],
            ['regime', 'raw', str((payload.get('regime_tributario') or {}).get('raw', ''))],
            ['regime', 'classificado', str((payload.get('regime_tributario') or {}).get('classificado', ''))],
            [
                'regime',
                'permite_credito_pis_cofins',
                str((payload.get('regime_tributario') or {}).get('permite_credito_pis_cofins', '')),
            ],
        ]
        for label, block in (('entrada', r_ent), ('saida', r_sai)):
            for k, v in block.items():
                rows.append(['resumo', f'{label}_{k}', str(v)])
        for k, v in saldo.items():
            rows.append(['saldo', k, str(v)])
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return _csv_response(rows, f'apuracao_fiscal_{ts}.csv')

    def _csv_alertas(self, payload: dict) -> HttpResponse:
        rows: list[list[str]] = [
            ['codigo', 'severidade', 'mensagem', 'documento_tipo', 'documento_id', 'item_id', 'acao_sugerida'],
        ]
        for a in payload.get('alertas', []) or []:
            rows.append(
                [
                    str(a.get('codigo', '')),
                    str(a.get('severidade', '')),
                    str(a.get('mensagem', '')),
                    str(a.get('documento_tipo', '')),
                    str(a.get('documento_id', '')),
                    str(a.get('item_id', '')),
                    str(a.get('acao_sugerida', '')),
                ]
            )
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return _csv_response(rows, f'apuracao_fiscal_alertas_{ts}.csv')


def _erro_apuracao(exc: ApuracaoFiscalError) -> Response:
    if exc.codigo in {'SEM_PERMISSAO_REABRIR', 'APURACAO_FECHADA_AJUSTE', 'APURACAO_NAO_FECHADA_SPED'}:
        http = status.HTTP_403_FORBIDDEN
    else:
        http = status.HTTP_400_BAD_REQUEST
    return Response({'detail': exc.message, 'codigo': exc.codigo}, status=http)


class ApuracaoFiscalPersistidaViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Apurações persistidas (F1).

    GET/POST /api/fiscal/apuracoes/
    GET /api/fiscal/apuracoes/{id}/
    POST /api/fiscal/apuracoes/{id}/fechar/
    POST /api/fiscal/apuracoes/{id}/reabrir/  (admin)
    GET /api/fiscal/apuracoes/{id}/itens/
    GET|POST /api/fiscal/apuracoes/{id}/ajustes/
    DELETE /api/fiscal/apuracoes/{id}/ajustes/{ajuste_id}/
    GET /api/fiscal/apuracoes/periodo/?empresa_id=&data_inicio=&data_fim=
    """

    permission_classes = [IsAuthenticated]
    queryset = ApuracaoFiscal.objects.select_related(
        'empresa', 'criado_por', 'fechado_por'
    ).prefetch_related('logs_auditoria', 'logs_auditoria__usuario')

    def get_serializer_class(self):
        if self.action == 'list':
            return ApuracaoFiscalListSerializer
        return ApuracaoFiscalSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        emp = self.request.query_params.get('empresa_id')
        if emp:
            qs = qs.filter(empresa_id=emp)
        st = (self.request.query_params.get('status') or '').strip().upper()
        if st in {ApuracaoFiscal.Status.RASCUNHO, ApuracaoFiscal.Status.FECHADO}:
            qs = qs.filter(status=st)
        di = self.request.query_params.get('data_inicio')
        df = self.request.query_params.get('data_fim')
        if di:
            qs = qs.filter(data_inicio=di)
        if df:
            qs = qs.filter(data_fim=df)
        return qs

    def create(self, request, *args, **kwargs):
        """Cria ou atualiza rascunho a partir do cálculo on-demand."""
        ser = CriarRascunhoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            apuracao = criar_rascunho(ser.validated_data, usuario=request.user)
        except ApuracaoFiscalError as exc:
            return _erro_apuracao(exc)
        out = ApuracaoFiscalSerializer(apuracao, context={'request': request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='fechar')
    def fechar(self, request, pk=None):
        try:
            apuracao = fechar_periodo(int(pk), usuario=request.user)
        except ApuracaoFiscal.DoesNotExist:
            return Response({'detail': 'Apuração não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except ApuracaoFiscalError as exc:
            return _erro_apuracao(exc)
        return Response(ApuracaoFiscalSerializer(apuracao).data)

    @action(detail=True, methods=['post'], url_path='reabrir')
    def reabrir(self, request, pk=None):
        ser = ReabrirSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            apuracao = reabrir_periodo(
                int(pk),
                usuario=request.user,
                motivo=ser.validated_data['motivo'],
            )
        except ApuracaoFiscal.DoesNotExist:
            return Response({'detail': 'Apuração não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except ApuracaoFiscalError as exc:
            return _erro_apuracao(exc)
        return Response(ApuracaoFiscalSerializer(apuracao).data)

    @action(detail=True, methods=['get'], url_path='itens')
    def itens(self, request, pk=None):
        apuracao = get_object_or_404(ApuracaoFiscal, pk=pk)
        qs = ApuracaoItem.objects.filter(apuracao=apuracao).order_by('id')
        return Response(ApuracaoItemSerializer(qs, many=True).data)

    @action(detail=True, methods=['get', 'post'], url_path='ajustes')
    def ajustes(self, request, pk=None):
        apuracao = get_object_or_404(ApuracaoFiscal, pk=pk)
        if request.method == 'GET':
            qs = listar_ajustes(apuracao.id)
            resumo = resumo_ajustes(apuracao)
            return Response(
                {
                    'ajustes': ApuracaoAjusteManualSerializer(qs, many=True).data,
                    'ajustes_liquido': float(resumo['ajustes_liquido']),
                    'saldo_icms_snapshot': float(resumo['saldo_icms_snapshot']),
                    'saldo_final': float(resumo['saldo_final']),
                    'quantidade': resumo['quantidade'],
                }
            )
        ser = CriarAjusteManualSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            ajuste, liquido, final = adicionar_ajuste(
                apuracao.id,
                tipo=ser.validated_data['tipo'],
                valor=ser.validated_data['valor'],
                motivo=ser.validated_data['motivo'],
                usuario=request.user,
            )
        except ApuracaoFiscalError as exc:
            return _erro_apuracao(exc)
        return Response(
            {
                'ajuste': ApuracaoAjusteManualSerializer(ajuste).data,
                'ajustes_liquido': float(liquido),
                'saldo_icms_snapshot': float(apuracao.saldo_icms),
                'saldo_final': float(final),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['delete'],
        url_path=r'ajustes/(?P<ajuste_id>[^/.]+)',
    )
    def ajustes_delete(self, request, pk=None, ajuste_id=None):
        try:
            _, liquido, final = remover_ajuste(
                int(pk),
                int(ajuste_id),
                usuario=request.user,
            )
        except ApuracaoFiscal.DoesNotExist:
            return Response({'detail': 'Apuração não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except ApuracaoFiscalError as exc:
            if exc.codigo == 'AJUSTE_NAO_ENCONTRADO':
                return Response({'detail': exc.message, 'codigo': exc.codigo}, status=status.HTTP_404_NOT_FOUND)
            return _erro_apuracao(exc)
        apuracao = ApuracaoFiscal.objects.get(pk=pk)
        return Response(
            {
                'detail': 'Ajuste removido.',
                'ajuste_id': int(ajuste_id),
                'ajustes_liquido': float(liquido),
                'saldo_icms_snapshot': float(apuracao.saldo_icms),
                'saldo_final': float(final),
            }
        )

    @action(detail=True, methods=['get'], url_path='sped-efd-icms-ipi')
    def sped_efd_icms_ipi(self, request, pk=None):
        """Download TXT prévia EFD ICMS/IPI (somente apuração FECHADA)."""
        apuracao = get_object_or_404(
            ApuracaoFiscal.objects.select_related('empresa'),
            pk=pk,
        )
        try:
            txt = gerar_sped_efd_icms_ipi_txt(apuracao)
        except ApuracaoFiscalError as exc:
            return _erro_apuracao(exc)
        resp = HttpResponse(txt, content_type='text/plain; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{nome_arquivo_sped(apuracao)}"'
        return resp

    @action(detail=True, methods=['get'], url_path='reforma')
    def reforma(self, request, pk=None):
        apuracao = get_object_or_404(ApuracaoFiscal, pk=pk)
        ref = getattr(apuracao, 'reforma', None)
        if ref is None:
            return Response({'detail': 'Reforma ainda não persistida (feche o período).'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ApuracaoReformaSerializer(ref).data)

    @action(detail=False, methods=['get'], url_path='periodo')
    def periodo(self, request):
        """Status do período (rascunho/fechado) para a UI — não recalcula on-demand."""
        empresa_id = request.query_params.get('empresa_id')
        di = request.query_params.get('data_inicio')
        df = request.query_params.get('data_fim')
        if not empresa_id or not di or not df:
            return Response(
                {'detail': 'empresa_id, data_inicio e data_fim são obrigatórios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        apuracao = (
            ApuracaoFiscal.objects.select_related('empresa', 'fechado_por', 'criado_por')
            .prefetch_related('ajustes_manuais')
            .filter(empresa_id=empresa_id, data_inicio=di, data_fim=df)
            .first()
        )
        fechado = periodo_fiscal_fechado(int(empresa_id), di, df)
        return Response(
            {
                'empresa_id': int(empresa_id),
                'data_inicio': di,
                'data_fim': df,
                'periodo_fechado': fechado,
                'pode_reabrir': usuario_pode_reabrir(request.user),
                'apuracao': ApuracaoFiscalSerializer(apuracao).data if apuracao else None,
            }
        )
