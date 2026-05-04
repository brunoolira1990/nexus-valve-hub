import logging
import re

from django.db import models
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.produtos.snapshot import build_produto_snapshot
from apps.fiscal.models import (
    EstoqueCorrida,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    ItemNFeSaidaHistoricaImportada,
    NFeEntrada,
    NFeEntradaHistoricaImportada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)
from .certificado_pdf import gerar_certificado_qualidade_pdf
from .models import Certificado, CertificadoFornecedorEntrada, CertificadoQualidade, ItemCertificadoFornecedorEntrada
from .serializers import CertificadoFornecedorEntradaSerializer, CertificadoQualidadeSerializer, CertificadoSerializer

logger = logging.getLogger(__name__)


def _bucket_key_corrida_lote(corrida: str, lote: str) -> str:
    c = (corrida or '').strip().upper()
    l = (lote or '').strip().upper()
    if not c and l:
        c, l = l, ''
    if not c:
        return ''
    return f'{c}\x1f{l}'


def _normalize_search_token(value: str) -> str:
    txt = (value or '').strip().upper()
    txt = re.sub(r'[\s\./-]+', '', txt)
    return txt


def _contains_normalized(base: str, target: str) -> bool:
    if not base or not target:
        return False
    return target in base or base in target


def _tokenize(value: str) -> set[str]:
    raw = re.sub(r'[^A-Z0-9 ]+', ' ', (value or '').upper())
    return {t for t in raw.split() if len(t) > 1}


def _descricao_relacionada(a: str, b: str) -> bool:
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return False
    inter = ta.intersection(tb)
    return len(inter) >= 2


class CertificadoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Certificado.objects.select_related('nf_saida').all()
    serializer_class = CertificadoSerializer


class CertificadoQualidadeViewSet(viewsets.ModelViewSet):
    queryset = (
        CertificadoQualidade.objects.select_related('cliente', 'nota_fiscal', 'nota_fiscal_historica')
        .prefetch_related('itens')
        .all()
    )
    serializer_class = CertificadoQualidadeSerializer

    @staticmethod
    def _sugerir_tipo_item(codigo: str, descricao: str, ncm: str) -> str:
        txt = f'{codigo} {descricao}'.upper()
        n = (ncm or '').replace('.', '')
        if 'VALVULA' in txt or n.startswith('8481'):
            return 'VALVULA_COMPONENTES'
        return 'PADRAO_ITEM'

    @staticmethod
    def _status_vinculo_item(produto_id: int | None) -> str:
        return 'VINCULADO' if produto_id else 'NAO_VINCULADO'

    @action(detail=False, methods=['post'], url_path='preencher-por-nfe')
    def preencher_por_nfe(self, request):
        nf_saida_id = request.data.get('nf_saida_id')
        nf_saida_historica_id = request.data.get('nf_saida_historica_id')
        if not nf_saida_id and not nf_saida_historica_id:
            return Response(
                {'detail': 'Informe nf_saida_id ou nf_saida_historica_id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if nf_saida_id:
            try:
                nf = NFeSaida.objects.select_related('cliente', 'pedido_venda').prefetch_related('itens__produto').get(pk=nf_saida_id)
            except NFeSaida.DoesNotExist:
                return Response({'detail': 'NF-e de saída não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
            itens = [
                {
                    'ordem': idx + 1,
                    'produto': it.produto_id,
                    'codigo_produto': ((it.snapshot_produto or {}).get('codigo_completo') or it.produto.codigo_completo),
                    'descricao_material': ((it.snapshot_produto or {}).get('descricao') or it.produto.descricao),
                    'quantidade': float(it.quantidade),
                    'unidade': (
                        (it.snapshot_produto or {}).get('unidade_efetiva')
                        or (it.snapshot_produto or {}).get('unidade')
                        or it.produto.unidade
                        or it.produto.unidade_especifica
                        or ''
                    ),
                    'norma': ((it.snapshot_produto or {}).get('norma') or it.produto.norma or ''),
                    'corrida': it.corrida.numero if it.corrida_id else '',
                    'lote': '',
                    'ncm': ((it.snapshot_produto or {}).get('ncm') or it.produto.ncm or ''),
                    'tipo_dados_tecnicos': self._sugerir_tipo_item(it.produto.codigo_completo, it.produto.descricao, it.produto.ncm or ''),
                    'status_vinculo_produto': self._status_vinculo_item(it.produto_id),
                    'produto_codigo': it.produto.codigo_completo,
                    'produto_descricao': it.produto.descricao,
                    'produto_ncm_efetivo': it.produto.get_ncm_efetivo_codigo() if it.produto_id else '',
                    'produto_snapshot': it.snapshot_produto or build_produto_snapshot(it.produto),
                    'origem_rastreabilidade_tipo': 'NF_SAIDA_OPERACIONAL',
                    'origem_status_tecnico': 'SEM_DADOS_TECNICOS',
                    'incluir_no_certificado': True,
                    'motivo_nao_inclusao': '',
                    'observacao_nao_inclusao': '',
                    'observacoes_item': '',
                    'composicao_json': {},
                    'ensaio_tracao_json': {},
                    'ensaio_impacto_json': {},
                    'componentes': [],
                }
                for idx, it in enumerate(nf.itens.all())
            ]
            mensagens = []
            if any(not (it.get('corrida') and it.get('norma')) for it in itens):
                mensagens.append('Item sem dados técnicos vinculados.')
            payload = {
                'cliente': nf.cliente_id,
                'cliente_nome_snapshot': nf.cliente.razao_social,
                'cliente_cnpj_snapshot': nf.cliente.cnpj,
                'pedido_cliente': (str(nf.pedido_venda_id) if nf.pedido_venda_id else ''),
                'nota_fiscal_numero': nf.numero,
                'nota_fiscal': nf.id,
                'data_emissao': nf.data.isoformat(),
                'itens': itens,
                'mensagens': mensagens,
            }
            return Response(payload)

        try:
            nf_hist = NFeSaidaHistoricaImportada.objects.select_related('cliente').get(pk=nf_saida_historica_id)
        except NFeSaidaHistoricaImportada.DoesNotExist:
            return Response({'detail': 'NF-e de saída histórica não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        itens_hist = []
        for idx, it in enumerate(ItemNFeSaidaHistoricaImportada.objects.filter(nf_id=nf_hist.id).order_by('n_item')):
            prod = it.prod_json or {}
            itens_hist.append(
                {
                    'ordem': idx + 1,
                    'produto': None,
                    'codigo_produto': str(prod.get('cProd') or ''),
                    'descricao_material': str(prod.get('xProd') or ''),
                    'quantidade': float(prod.get('qCom') or 0),
                    'unidade': str(prod.get('uCom') or ''),
                    'norma': '',
                    'corrida': '',
                    'lote': '',
                    'ncm': str(prod.get('NCM') or ''),
                    'tipo_dados_tecnicos': self._sugerir_tipo_item(str(prod.get('cProd') or ''), str(prod.get('xProd') or ''), str(prod.get('NCM') or '')),
                    'status_vinculo_produto': self._status_vinculo_item(None),
                    'produto_codigo': '',
                    'produto_descricao': '',
                    'produto_ncm_efetivo': '',
                    'produto_snapshot': {},
                    'origem_rastreabilidade_tipo': 'NF_SAIDA_HISTORICA',
                    'origem_status_tecnico': 'SEM_DADOS_TECNICOS',
                    'incluir_no_certificado': True,
                    'motivo_nao_inclusao': '',
                    'observacao_nao_inclusao': '',
                    'observacoes_item': '',
                    'composicao_json': {},
                    'ensaio_tracao_json': {},
                    'ensaio_impacto_json': {},
                    'componentes': [],
                },
            )
        dest = nf_hist.dest_json or {}
        payload = {
            'cliente': nf_hist.cliente_id,
            'cliente_nome_snapshot': nf_hist.cliente.razao_social if nf_hist.cliente_id else str(dest.get('xNome') or ''),
            'cliente_cnpj_snapshot': str(dest.get('CNPJ') or ''),
            'pedido_cliente': '',
            'nota_fiscal_numero': nf_hist.numero,
            'nota_fiscal_historica': nf_hist.id,
            'data_emissao': nf_hist.dh_emissao.date().isoformat(),
            'itens': itens_hist,
            'mensagens': [
                'NF-e histórica carregada. Complete manualmente norma, corrida e dados técnicos.',
                'Item sem dados técnicos vinculados.',
            ],
        }
        return Response(payload)

    @action(detail=False, methods=['get'], url_path='corridas-disponiveis')
    def corridas_disponiveis(self, request):
        produto_id = request.query_params.get('produto_id')
        if not produto_id:
            return Response({'detail': 'Informe produto_id.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            produto_id_int = int(produto_id)
        except ValueError:
            return Response({'detail': 'produto_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        estoque_rows = (
            EstoqueCorrida.objects
            .select_related('corrida')
            .filter(produto_id=produto_id_int)
            .order_by('-saldo', '-id')
        )
        conf_rows = (
            ItemNFeEntradaConferencia.objects
            .select_related('conferencia__nf_entrada_historica', 'conferencia__nf_entrada_historica__fornecedor_emitente')
            .filter(produto_id=produto_id_int)
            .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
            .order_by('-id')
        )
        cert_rows = (
            ItemCertificadoFornecedorEntrada.objects
            .select_related('certificado_fornecedor', 'certificado_fornecedor__fornecedor')
            .filter(produto_id=produto_id_int, ativo=True)
            .order_by('-id')
        )

        resultados = {}
        for est in estoque_rows:
            key = _bucket_key_corrida_lote(est.corrida.numero or '', '')
            if not key:
                continue
            resultados[key] = {
                'corrida': est.corrida.numero,
                'lote': '',
                'saldo': f'{est.saldo:.3f}',
                'unidade': (
                    est.produto.get_unidade_estoque_efetiva()
                    or est.produto.unidade
                    or est.produto.unidade_especifica
                    or ''
                ),
                'fornecedor': '',
                'nf_entrada': '',
                'certificado_fornecedor': '',
                'certificado_fornecedor_id': None,
                'item_certificado_fornecedor_id': None,
                'status_certificado_fornecedor': '',
                'status_origem_tecnica': 'somente_estoque',
                'tem_dados_tecnicos': False,
                'norma': '',
                'ncm': est.produto.get_ncm_efetivo_codigo() or est.produto.ncm or '',
                'origem': 'estoque',
                'alertas': [],
                'composicao_json': {},
                'ensaio_tracao_json': {},
                'ensaio_impacto_json': {},
                'numero_certificado_fornecedor_item': '',
                'observacoes_origem': '',
            }

        for conf in conf_rows:
            corrida_conf = (conf.corrida or '').strip()
            if not corrida_conf:
                continue
            key = _bucket_key_corrida_lote(corrida_conf, conf.lote or '')
            if not key:
                continue
            item = resultados.get(key) or {
                'corrida': corrida_conf,
                'lote': conf.lote or '',
                'saldo': '0.000',
                'unidade': conf.unidade_estoque_calculada or conf.unidade_nf or '',
                'fornecedor': '',
                'nf_entrada': conf.conferencia.nf_entrada_historica.numero if conf.conferencia_id else '',
                'certificado_fornecedor': '',
                'certificado_fornecedor_id': None,
                'item_certificado_fornecedor_id': None,
                'status_certificado_fornecedor': '',
                'status_origem_tecnica': 'somente_conferencia_entrada',
                'tem_dados_tecnicos': False,
                'norma': '',
                'ncm': str((conf.item_nfe_historico.prod_json or {}).get('NCM') or ''),
                'origem': 'conferencia_entrada',
                'alertas': [],
                'composicao_json': {},
                'ensaio_tracao_json': {},
                'ensaio_impacto_json': {},
                'numero_certificado_fornecedor_item': '',
                'observacoes_origem': conf.rastreabilidade_observacao or '',
            }
            if conf.lote and not item.get('lote'):
                item['lote'] = conf.lote
            if conf.conferencia_id and not item.get('nf_entrada'):
                item['nf_entrada'] = conf.conferencia.nf_entrada_historica.numero
            resultados[key] = item

        for cert_item in cert_rows:
            corrida_raw = (cert_item.corrida or '').strip()
            lote_raw = (cert_item.lote or '').strip()
            if not corrida_raw and lote_raw:
                corrida_raw, lote_raw = lote_raw, ''
            if not corrida_raw:
                continue
            key = _bucket_key_corrida_lote(corrida_raw, lote_raw)
            if not key:
                continue
            cert = cert_item.certificado_fornecedor
            item = resultados.get(key) or {
                'corrida': corrida_raw,
                'lote': lote_raw,
                'saldo': '0.000',
                'unidade': cert_item.unidade or '',
                'fornecedor': cert.fornecedor_nome_snapshot or '',
                'nf_entrada': cert.numero_nf_entrada or '',
                'certificado_fornecedor': cert_item.numero_certificado_fornecedor_item or cert.numero_certificado_fornecedor or '',
                'certificado_fornecedor_id': cert.id,
                'item_certificado_fornecedor_id': cert_item.id,
                'status_certificado_fornecedor': cert.status,
                'status_origem_tecnica': (
                    'certificado_fornecedor_registrado'
                    if cert.status == CertificadoFornecedorEntrada.Status.REGISTRADO
                    else 'certificado_fornecedor_rascunho'
                ),
                'tem_dados_tecnicos': bool(cert_item.composicao_json or cert_item.ensaio_tracao_json or cert_item.ensaio_impacto_json),
                'norma': cert_item.norma or '',
                'ncm': cert_item.ncm or '',
                'origem': 'certificado_fornecedor',
                'alertas': [],
                'composicao_json': cert_item.composicao_json or {},
                'ensaio_tracao_json': cert_item.ensaio_tracao_json or {},
                'ensaio_impacto_json': cert_item.ensaio_impacto_json or {},
                'numero_certificado_fornecedor_item': cert_item.numero_certificado_fornecedor_item or '',
                'observacoes_origem': cert_item.observacao_origem_certificado or '',
            }
            item['corrida'] = corrida_raw or item.get('corrida') or ''
            item['lote'] = lote_raw or item.get('lote') or ''
            item['fornecedor'] = item.get('fornecedor') or cert.fornecedor_nome_snapshot or ''
            item['nf_entrada'] = item.get('nf_entrada') or cert.numero_nf_entrada or ''
            item['certificado_fornecedor'] = (
                cert_item.numero_certificado_fornecedor_item
                or cert.numero_certificado_fornecedor
                or item.get('certificado_fornecedor')
                or ''
            )
            item['certificado_fornecedor_id'] = cert.id
            item['item_certificado_fornecedor_id'] = cert_item.id
            item['status_certificado_fornecedor'] = cert.status
            item['status_origem_tecnica'] = (
                'certificado_fornecedor_registrado'
                if cert.status == CertificadoFornecedorEntrada.Status.REGISTRADO
                else 'certificado_fornecedor_rascunho'
            )
            item['norma'] = cert_item.norma or item.get('norma') or ''
            item['ncm'] = cert_item.ncm or item.get('ncm') or ''
            item['composicao_json'] = cert_item.composicao_json or {}
            item['ensaio_tracao_json'] = cert_item.ensaio_tracao_json or {}
            item['ensaio_impacto_json'] = cert_item.ensaio_impacto_json or {}
            item['numero_certificado_fornecedor_item'] = cert_item.numero_certificado_fornecedor_item or ''
            item['tem_dados_tecnicos'] = bool(item['composicao_json'] or item['ensaio_tracao_json'] or item['ensaio_impacto_json'])
            item['origem'] = 'certificado_fornecedor'
            if cert.status == CertificadoFornecedorEntrada.Status.RASCUNHO:
                item['alertas'] = list(dict.fromkeys([
                    *item.get('alertas', []),
                    'Dados técnicos encontrados em certificado fornecedor em rascunho. Confirme antes de usar.',
                ]))
            resultados[key] = item

        for row in resultados.values():
            if not row.get('tem_dados_tecnicos'):
                alertas = list(row.get('alertas') or [])
                msg = 'Corrida encontrada, porém sem dados técnicos vinculados.'
                if msg not in alertas:
                    alertas.append(msg)
                row['alertas'] = alertas
            c_disp = (row.get('corrida') or '').strip()
            l_disp = (row.get('lote') or '').strip()
            row['valor_selecao'] = f'{c_disp}||{l_disp}'

        payload = sorted(
            resultados.values(),
            key=lambda r: (
                0 if r.get('origem') == 'certificado_fornecedor' else 1,
                -float(r.get('saldo') or 0),
                (r.get('corrida') or ''),
            ),
        )
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        cert = self.get_object()
        preview = str(request.query_params.get('preview', '')).lower() in {'1', 'true', 'sim'}
        pdf = gerar_certificado_qualidade_pdf(cert, preview=preview)
        filename = f'certificado_qualidade_{cert.numero_formatado.replace("/", "-")}.pdf'
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'inline; filename="{filename}"'
        return resp


class CertificadoFornecedorEntradaViewSet(viewsets.ModelViewSet):
    queryset = (
        CertificadoFornecedorEntrada.objects.select_related(
            'fornecedor',
            'nf_entrada_historica',
            'nf_entrada_operacional',
            'empresa_destinataria',
        )
        .prefetch_related('itens__componentes')
        .all()
    )
    serializer_class = CertificadoFornecedorEntradaSerializer

    @staticmethod
    def _sugerir_tipo_item(codigo: str, descricao: str, ncm: str) -> str:
        txt = f'{codigo} {descricao}'.upper()
        n = (ncm or '').replace('.', '')
        if 'VALVULA' in txt or n.startswith('8481'):
            return ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.VALVULA_COMPONENTES
        return ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.PADRAO_ITEM

    @action(detail=False, methods=['post'], url_path='preencher-por-nfe-entrada')
    def preencher_por_nfe_entrada(self, request):
        nf_hist_id = request.data.get('nf_entrada_historica_id')
        nf_op_id = request.data.get('nf_entrada_operacional_id')
        if not nf_hist_id and not nf_op_id:
            return Response(
                {'detail': 'Selecione uma NF-e de entrada para carregar os itens.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if nf_op_id:
            try:
                nf = NFeEntrada.objects.select_related('fornecedor').prefetch_related('itens__produto').get(pk=nf_op_id)
            except NFeEntrada.DoesNotExist:
                return Response({'detail': 'NF-e de entrada operacional não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                {
                    'fornecedor': nf.fornecedor_id,
                    'fornecedor_nome_snapshot': nf.fornecedor.razao_social,
                    'fornecedor_cnpj_snapshot': nf.fornecedor.cnpj,
                    'nf_entrada_operacional': nf.id,
                    'numero_nf_entrada': nf.numero,
                    'data_nf_entrada': nf.data.isoformat(),
                    'itens': [
                        {
                            'ordem': idx + 1,
                            'produto': it.produto_id,
                            'codigo_produto': it.produto.codigo_completo,
                            'descricao_material': it.produto.descricao,
                            'quantidade': float(it.quantidade),
                            'unidade': it.produto.unidade or it.produto.unidade_especifica or '',
                            'ncm': it.produto.ncm or '',
                            'norma': it.produto.norma or '',
                            'corrida': it.corrida.numero if it.corrida_id else '',
                            'lote': '',
                            'numero_certificado_fornecedor_item': '',
                            'data_certificado_fornecedor_item': None,
                            'pagina_certificado_fornecedor': '',
                            'observacao_origem_certificado': '',
                            'tipo_dados_tecnicos': self._sugerir_tipo_item(it.produto.codigo_completo, it.produto.descricao, it.produto.ncm or ''),
                            'composicao_json': {},
                            'ensaio_tracao_json': {},
                            'ensaio_impacto_json': {},
                            'observacoes_item': '',
                            'componentes': [],
                        }
                        for idx, it in enumerate(nf.itens.all())
                    ],
                }
            )

        try:
            nf_hist = NFeEntradaHistoricaImportada.objects.select_related('fornecedor_emitente', 'empresa_destinataria').get(pk=nf_hist_id)
        except NFeEntradaHistoricaImportada.DoesNotExist:
            return Response({'detail': 'NF-e de entrada histórica não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        emit = nf_hist.emit_json or {}
        return Response(
            {
                'fornecedor': nf_hist.fornecedor_emitente_id,
                'fornecedor_nome_snapshot': nf_hist.fornecedor_emitente.razao_social if nf_hist.fornecedor_emitente_id else str(emit.get('xNome') or ''),
                'fornecedor_cnpj_snapshot': str(emit.get('CNPJ') or ''),
                'nf_entrada_historica': nf_hist.id,
                'empresa_destinataria': nf_hist.empresa_destinataria_id,
                'numero_nf_entrada': nf_hist.numero,
                'serie_nf_entrada': nf_hist.serie,
                'data_nf_entrada': nf_hist.dh_emissao.date().isoformat(),
                'itens': [
                    {
                        'ordem': idx + 1,
                        'produto': None,
                        'codigo_produto': str((it.prod_json or {}).get('cProd') or ''),
                        'descricao_material': str((it.prod_json or {}).get('xProd') or ''),
                        'quantidade': float((it.prod_json or {}).get('qCom') or 0),
                        'unidade': str((it.prod_json or {}).get('uCom') or ''),
                        'ncm': str((it.prod_json or {}).get('NCM') or ''),
                        'norma': '',
                        'corrida': '',
                        'lote': '',
                            'numero_certificado_fornecedor_item': '',
                            'data_certificado_fornecedor_item': None,
                            'pagina_certificado_fornecedor': '',
                            'observacao_origem_certificado': '',
                        'tipo_dados_tecnicos': self._sugerir_tipo_item(
                            str((it.prod_json or {}).get('cProd') or ''),
                            str((it.prod_json or {}).get('xProd') or ''),
                            str((it.prod_json or {}).get('NCM') or ''),
                        ),
                        'composicao_json': {},
                        'ensaio_tracao_json': {},
                        'ensaio_impacto_json': {},
                        'observacoes_item': '',
                        'componentes': [],
                    }
                    for idx, it in enumerate(ItemNFeEntradaHistoricaImportada.objects.filter(nf_id=nf_hist.id).order_by('n_item'))
                ],
                'mensagens': ['NF-e de entrada histórica carregada. Complete manualmente corrida/lote e dados técnicos.'],
            }
        )

    @action(detail=False, methods=['get'], url_path='buscar-dados-tecnicos')
    def buscar_dados_tecnicos(self, request):
        corrida = (request.query_params.get('corrida') or '').strip()
        lote = (request.query_params.get('lote') or '').strip()
        produto = request.query_params.get('produto')
        codigo = (request.query_params.get('codigo_produto') or '').strip()
        descricao = (request.query_params.get('descricao') or '').strip()
        fornecedor = request.query_params.get('fornecedor')
        nf_entrada = (request.query_params.get('nf_entrada') or '').strip()
        certificado_numero = (request.query_params.get('certificado_fornecedor') or '').strip()
        status_param = (request.query_params.get('status') or '').strip().lower()
        include_rascunho = str(request.query_params.get('include_rascunho', '')).lower() in {'1', 'true', 'sim'}
        qs = ItemCertificadoFornecedorEntrada.objects.select_related('certificado_fornecedor', 'produto', 'certificado_fornecedor__fornecedor').prefetch_related('componentes').filter(
            ativo=True,
        )
        if status_param in {
            CertificadoFornecedorEntrada.Status.RASCUNHO,
            CertificadoFornecedorEntrada.Status.REGISTRADO,
            CertificadoFornecedorEntrada.Status.CANCELADO,
        }:
            qs = qs.filter(certificado_fornecedor__status=status_param)
        elif include_rascunho:
            qs = qs.filter(
                certificado_fornecedor__status__in=[
                    CertificadoFornecedorEntrada.Status.RASCUNHO,
                    CertificadoFornecedorEntrada.Status.REGISTRADO,
                ]
            )
        else:
            qs = qs.filter(certificado_fornecedor__status=CertificadoFornecedorEntrada.Status.REGISTRADO)

        if fornecedor:
            qs = qs.filter(certificado_fornecedor__fornecedor_id=fornecedor)
        if nf_entrada:
            qs = qs.filter(certificado_fornecedor__numero_nf_entrada__icontains=nf_entrada)
        if certificado_numero:
            qs = qs.filter(
                models.Q(certificado_fornecedor__numero_certificado_fornecedor__icontains=certificado_numero)
                | models.Q(numero_certificado_fornecedor_item__icontains=certificado_numero)
            )

        if not any([corrida, lote, produto, codigo, descricao, fornecedor, nf_entrada, certificado_numero]):
            return Response([], status=status.HTTP_200_OK)

        corrida_norm = _normalize_search_token(corrida)
        lote_norm = _normalize_search_token(lote)
        codigo_norm = _normalize_search_token(codigo)
        descricao_norm = (descricao or '').strip().lower()
        norma_ref = (request.query_params.get('norma') or '').strip().upper()
        tipo_tecnico_ref = (request.query_params.get('tipo_dados_tecnicos') or '').strip()
        filtered_items = []
        for item in qs.order_by('-id')[:300]:
            score = 0
            item_corrida_norm = _normalize_search_token(item.corrida)
            item_lote_norm = _normalize_search_token(item.lote)
            if corrida_norm:
                if _contains_normalized(item_corrida_norm, corrida_norm):
                    score += 100
                elif _contains_normalized(item_lote_norm, corrida_norm):
                    score += 70
                else:
                    continue
            if lote_norm:
                if _contains_normalized(item_lote_norm, lote_norm):
                    score += 80
                elif _contains_normalized(item_corrida_norm, lote_norm):
                    score += 50
                elif corrida_norm:
                    continue
            if produto and item.produto_id and str(item.produto_id) == str(produto):
                score += 15
            if codigo_norm and _contains_normalized(_normalize_search_token(item.codigo_produto), codigo_norm):
                score += 10
            if descricao_norm and descricao_norm in (item.descricao_material or '').lower():
                score += 8
            norma_item = (item.norma or '').strip().upper()
            if norma_ref:
                if norma_item and norma_item == norma_ref:
                    score += 40
                elif norma_item and (norma_item in norma_ref or norma_ref in norma_item):
                    score += 30
                else:
                    score -= 15
            if tipo_tecnico_ref and item.tipo_dados_tecnicos == tipo_tecnico_ref:
                score += 8
            filtered_items.append((score, item))

        if not filtered_items:
            if corrida_norm or lote_norm:
                logger.info(
                    'buscar_dados_tecnicos_sem_resultado corrida=%s corrida_norm=%s lote=%s lote_norm=%s certificados_registrados=%s',
                    corrida,
                    corrida_norm,
                    lote,
                    lote_norm,
                    CertificadoFornecedorEntrada.objects.filter(status=CertificadoFornecedorEntrada.Status.REGISTRADO).count(),
                )
            return Response([], status=status.HTTP_200_OK)

        filtered_items.sort(key=lambda x: (x[0], x[1].id), reverse=True)
        resultados = []
        corrida_bucket: dict[tuple[str, str], list[ItemCertificadoFornecedorEntrada]] = {}
        for _, item in filtered_items:
            key = (
                str(item.certificado_fornecedor.fornecedor_id or ''),
                _normalize_search_token(item.corrida or item.lote or ''),
            )
            corrida_bucket.setdefault(key, []).append(item)

        def _fingerprint(it: ItemCertificadoFornecedorEntrada) -> str:
            return '|'.join(
                [
                    str(it.norma or '').strip(),
                    str(it.tipo_dados_tecnicos or '').strip(),
                    str(it.composicao_json or {}),
                    str(it.ensaio_tracao_json or {}),
                    str(it.ensaio_impacto_json or {}),
                    str(list(it.componentes.values('nome_componente', 'norma', 'corrida')) if hasattr(it, 'componentes') else []),
                ]
            )

        for score, item in filtered_items[:100]:
            cert = item.certificado_fornecedor
            codigo_divergente = bool(codigo_norm and _normalize_search_token(item.codigo_produto) != codigo_norm)
            desc_divergente = bool(descricao_norm and descricao_norm not in (item.descricao_material or '').lower())
            produto_relacionado = _descricao_relacionada(item.descricao_material or '', descricao or '')
            norma_item = (item.norma or '').strip().upper()
            norma_compativel = False
            if norma_ref and norma_item:
                norma_compativel = norma_item == norma_ref or norma_item in norma_ref or norma_ref in norma_item
            elif norma_ref and not norma_item:
                norma_compativel = False
            elif not norma_ref:
                norma_compativel = True

            if score >= 145 and not (codigo_divergente or desc_divergente):
                confianca = 'ALTA'
                tipo_correspondencia = 'Mesmo produto'
            elif norma_compativel and (produto_relacionado or not (codigo_divergente and desc_divergente)):
                confianca = 'ALTA' if score >= 110 else 'MEDIA_ALTA'
                tipo_correspondencia = 'Mesma corrida/material em produto relacionado'
            elif norma_compativel:
                confianca = 'MEDIA'
                tipo_correspondencia = 'Produto diferente — conferir'
            else:
                confianca = 'BAIXA'
                tipo_correspondencia = 'Norma/material divergente'

            if tipo_correspondencia == 'Mesmo produto':
                mensagem_contexto = 'Dados técnicos encontrados para este produto e corrida.'
            elif tipo_correspondencia == 'Mesma corrida/material em produto relacionado':
                mensagem_contexto = (
                    'Dados técnicos encontrados para a mesma corrida/material em outro produto. '
                    'Pode ser matéria-prima relacionada. Confira antes de aplicar.'
                )
            elif tipo_correspondencia == 'Produto diferente — conferir':
                mensagem_contexto = (
                    'Corrida encontrada para outro produto deste fornecedor. '
                    'Verifique se é a mesma matéria-prima antes de reutilizar.'
                )
            else:
                mensagem_contexto = (
                    'Corrida encontrada, mas a norma/material é diferente. '
                    'Reutilize somente se tiver certeza.'
                )
            key = (
                str(cert.fornecedor_id or ''),
                _normalize_search_token(item.corrida or item.lote or ''),
            )
            siblings = corrida_bucket.get(key, [])
            siblings_fp = {_fingerprint(s) for s in siblings}
            divergencia_dados = len(siblings_fp) > 1
            resultados.append(
                {
                    'id': item.id,
                    'certificado_fornecedor_id': cert.id,
                    'fornecedor': cert.fornecedor_id,
                    'fornecedor_nome': cert.fornecedor_nome_snapshot or (cert.fornecedor.razao_social if cert.fornecedor_id else ''),
                    'numero_nf_entrada': cert.numero_nf_entrada,
                    'data_nf_entrada': cert.data_nf_entrada.isoformat() if cert.data_nf_entrada else '',
                    'numero_certificado_fornecedor': (
                        item.numero_certificado_fornecedor_item or cert.numero_certificado_fornecedor
                    ),
                    'numero_certificado_fornecedor_item': item.numero_certificado_fornecedor_item,
                    'status_certificado_fornecedor': cert.status,
                    'produto': item.produto_id,
                    'codigo_produto': item.codigo_produto,
                    'descricao_material': item.descricao_material,
                    'norma': item.norma,
                    'corrida': item.corrida,
                    'lote': item.lote,
                    'tipo_dados_tecnicos': item.tipo_dados_tecnicos,
                    'confianca_correspondencia': confianca,
                    'tipo_correspondencia': tipo_correspondencia,
                    'mensagem_contexto': mensagem_contexto,
                    'norma_compativel': norma_compativel,
                    'produto_relacionado': produto_relacionado,
                    'score': score,
                    'aviso_divergencia_codigo': (
                        'Corrida encontrada, mas o código do fornecedor é diferente do código do item de saída. Confira antes de aplicar.'
                        if codigo_divergente else ''
                    ),
                    'aviso_divergencia_item': (
                        'Corrida encontrada para o mesmo fornecedor, mas o código/descrição do item é diferente. Confira antes de aplicar.'
                        if (codigo_divergente or desc_divergente) else ''
                    ),
                    'aviso_divergencia_dados_tecnicos': (
                        'Já existem dados técnicos diferentes cadastrados para esta corrida. Verifique se é revisão, lote diferente ou erro de digitação.'
                        if divergencia_dados else ''
                    ),
                    'aviso_certificado_rascunho': (
                        'Este dado técnico vem de um certificado ainda em rascunho.'
                        if cert.status == CertificadoFornecedorEntrada.Status.RASCUNHO else ''
                    ),
                    'composicao_json': item.composicao_json,
                    'ensaio_tracao_json': item.ensaio_tracao_json,
                    'ensaio_impacto_json': item.ensaio_impacto_json,
                    'componentes': [
                        {
                            'ordem': c.ordem,
                            'nome_componente': c.nome_componente,
                            'descricao_componente': c.descricao_componente,
                            'norma': c.norma,
                            'corrida': c.corrida,
                            'lote': c.lote,
                            'revisao_corrida': c.revisao_corrida,
                            'numero_certificado_fornecedor_componente': (
                                c.numero_certificado_fornecedor_componente
                                or item.numero_certificado_fornecedor_item
                                or cert.numero_certificado_fornecedor
                            ),
                            'quantidade': float(c.quantidade) if c.quantidade is not None else None,
                            'composicao_json': c.composicao_json,
                            'ensaio_tracao_json': c.ensaio_tracao_json,
                            'ensaio_impacto_json': c.ensaio_impacto_json,
                            'observacoes': c.observacoes,
                            'ativo': c.ativo,
                        }
                        for c in item.componentes.all()
                    ],
                }
            )
        return Response(resultados, status=status.HTTP_200_OK)
