import logging
import re

from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination

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
from .corridas_disponiveis import listar_corridas_disponiveis_produto
from .conferencia_bridge import get_or_build_conferencia_for_nf_historica, map_itens_conferencia_por_n_item
from .models import Certificado, CertificadoFornecedorEntrada, CertificadoQualidade, ItemCertificadoFornecedorEntrada
from .serializers import (
    CertificadoFornecedorEntradaSerializer,
    CertificadoQualidadeSerializer,
    CertificadoSerializer,
    _origem_pedido_compra_de_item_cf,
)

logger = logging.getLogger(__name__)


def _corrida_lote_e_corridas_adicionais_de_conferencia(
    ic: ItemNFeEntradaConferencia | None,
) -> tuple[str, str, list[dict]]:
    """Corrida principal + corridas adicionais a partir dos splits da conferência."""
    if not ic:
        return '', '', []

    splits = list(ic.corridas_split.order_by('ordem', 'id'))
    if splits:
        primeiro = splits[0]
        corrida = (primeiro.corrida or '').strip()
        lote = (primeiro.lote or '').strip()
        adicionais: list[dict] = []
        for idx, split_row in enumerate(splits[1:], start=1):
            corrida_split = (split_row.corrida or '').strip()
            lote_split = (split_row.lote or '').strip()
            if not corrida_split and not lote_split:
                continue
            adicionais.append(
                {
                    'ordem': idx,
                    'corrida': corrida_split,
                    'lote': lote_split,
                    'quantidade': split_row.quantidade,
                },
            )
        return corrida, lote, adicionais

    return (ic.corrida or '').strip(), (ic.lote or '').strip(), []


# --- Fase E.3: permissões mínimas (Django model permissions + IsAuthenticated) ---
#
# Decisões em relação à matriz em docs/qualidade-certificados.md (secção 8):
# - PDF, corridas-disponiveis e preencher-por-nfe: a matriz prevê condicionantes de
#   negócio (ex.: PDF só emitido para consulta). Aqui só há controlo por codename;
#   regras por status permanecem nos serializers / fluxo existente.
# - corridas-disponiveis e preencher-por-nfe (CQ) e buscar-dados-tecnicos /
#   preencher-por-nfe-entrada (CF): exige change_* (não basta view_*), alinhado ao
#   perfil Operador na matriz e aos testes de “ações auxiliares” com permissão de
#   alteração.


class CertificadoLegacyPermissions(BasePermission):
    """Legado `Certificado`: leitura com view_certificado (superuser ignora)."""

    def has_permission(self, request, view):
        u = request.user
        if not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        return u.has_perm('qualidade.view_certificado')


class CertificadoQualidadePermissions(BasePermission):
    """CQ: view/add/change/delete por ação; auxiliares sensíveis exigem change."""

    def has_permission(self, request, view):
        u = request.user
        if not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        action = getattr(view, 'action', None) or ''
        if action in ('list', 'retrieve'):
            return u.has_perm('qualidade.view_certificadoqualidade')
        if action == 'create':
            return u.has_perm('qualidade.add_certificadoqualidade')
        if action in ('update', 'partial_update'):
            return u.has_perm('qualidade.change_certificadoqualidade')
        if action == 'destroy':
            return u.has_perm('qualidade.delete_certificadoqualidade')
        if action == 'pdf':
            return u.has_perm('qualidade.view_certificadoqualidade') or u.has_perm(
                'qualidade.change_certificadoqualidade'
            )
        if action in ('corridas_disponiveis', 'preencher_por_nfe'):
            return u.has_perm('qualidade.change_certificadoqualidade')
        return False


class CertificadoFornecedorEntradaPermissions(BasePermission):
    """CF entrada: view/add/change/delete; buscas/preencher NF exigem change."""

    def has_permission(self, request, view):
        u = request.user
        if not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        action = getattr(view, 'action', None) or ''
        if action in ('list', 'retrieve'):
            return u.has_perm('qualidade.view_certificadofornecedorentrada')
        if action == 'create':
            return u.has_perm('qualidade.add_certificadofornecedorentrada')
        if action in ('update', 'partial_update'):
            return u.has_perm('qualidade.change_certificadofornecedorentrada')
        if action == 'destroy':
            return u.has_perm('qualidade.delete_certificadofornecedorentrada')
        if action in ('buscar_dados_tecnicos', 'preencher_por_nfe_entrada'):
            return u.has_perm('qualidade.change_certificadofornecedorentrada')
        return False


def _cf_status_canonical(status: str | None) -> str:
    return str(status or '').strip().lower()


def _cf_status_is_registrado(status: str | None) -> bool:
    return _cf_status_canonical(status) == CertificadoFornecedorEntrada.Status.REGISTRADO


def _filter_cf_items_por_status_certificado(qs, *, status_param: str, include_rascunho: bool):
    """Filtro por status do certificado fornecedor (case-insensitive; legado ex.: REGISTRADO)."""
    if status_param in {
        CertificadoFornecedorEntrada.Status.RASCUNHO,
        CertificadoFornecedorEntrada.Status.REGISTRADO,
        CertificadoFornecedorEntrada.Status.CANCELADO,
    }:
        return qs.filter(certificado_fornecedor__status__iexact=status_param)
    if include_rascunho:
        return qs.filter(
            models.Q(certificado_fornecedor__status__iexact=CertificadoFornecedorEntrada.Status.RASCUNHO)
            | models.Q(certificado_fornecedor__status__iexact=CertificadoFornecedorEntrada.Status.REGISTRADO)
        )
    return qs.filter(certificado_fornecedor__status__iexact=CertificadoFornecedorEntrada.Status.REGISTRADO)


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


def _effective_corrida_lote_norms_cf_item(item: ItemCertificadoFornecedorEntrada) -> tuple[str, str]:
    item_corrida_norm = _normalize_search_token(item.corrida)
    item_lote_norm = _normalize_search_token(item.lote)
    if not item_corrida_norm and not item_lote_norm:
        for c in item.componentes.all():
            cn = _normalize_search_token(getattr(c, 'corrida', '') or '')
            ln = _normalize_search_token(getattr(c, 'lote', '') or '')
            if cn:
                item_corrida_norm = cn
            if ln:
                item_lote_norm = ln
            if item_corrida_norm or item_lote_norm:
                break
    return item_corrida_norm, item_lote_norm


def _display_corrida_lote_cf_item(item: ItemCertificadoFornecedorEntrada) -> tuple[str, str]:
    """Corrida/lote para exibição e CQ: campos do item; completam-se pelos componentes se faltar um dos dois."""
    corrida = (item.corrida or '').strip()
    lote = (item.lote or '').strip()
    if corrida and lote:
        return corrida, lote
    for c in item.componentes.all():
        if not corrida:
            corrida = (getattr(c, 'corrida', '') or '').strip() or corrida
        if not lote:
            lote = (getattr(c, 'lote', '') or '').strip() or lote
        if corrida and lote:
            break
    return corrida, lote


def _corrida_busca_match_cf_item(item: ItemCertificadoFornecedorEntrada, corrida_norm: str) -> bool:
    if not corrida_norm:
        return True
    ic, il = _effective_corrida_lote_norms_cf_item(item)
    if _contains_normalized(ic, corrida_norm) or _contains_normalized(il, corrida_norm):
        return True
    for c in item.componentes.all():
        cn = _normalize_search_token(getattr(c, 'corrida', '') or '')
        ln = _normalize_search_token(getattr(c, 'lote', '') or '')
        if _contains_normalized(cn, corrida_norm) or _contains_normalized(ln, corrida_norm):
            return True
    return False


def _passes_corrida_lote_cf_item(item: ItemCertificadoFornecedorEntrada, corrida_norm: str, lote_norm: str) -> bool:
    ic, il = _effective_corrida_lote_norms_cf_item(item)
    if corrida_norm:
        if _contains_normalized(ic, corrida_norm) or _contains_normalized(il, corrida_norm):
            pass
        else:
            comp_hit = False
            for c in item.componentes.all():
                cn = _normalize_search_token(getattr(c, 'corrida', '') or '')
                ln = _normalize_search_token(getattr(c, 'lote', '') or '')
                if _contains_normalized(cn, corrida_norm) or _contains_normalized(ln, corrida_norm):
                    comp_hit = True
                    break
            if not comp_hit:
                return False
    if lote_norm:
        if _contains_normalized(il, lote_norm) or _contains_normalized(ic, lote_norm):
            pass
        elif corrida_norm and il:
            return False
    return True


def _qs_items_cf_diag_base(*, fornecedor, nf_entrada, certificado_numero):
    q = (
        ItemCertificadoFornecedorEntrada.objects.filter(ativo=True)
        .select_related('certificado_fornecedor', 'produto', 'certificado_fornecedor__fornecedor')
        .prefetch_related('componentes')
    )
    if fornecedor:
        q = q.filter(certificado_fornecedor__fornecedor_id=fornecedor)
    if nf_entrada:
        q = q.filter(certificado_fornecedor__numero_nf_entrada__icontains=nf_entrada)
    if certificado_numero:
        q = q.filter(
            models.Q(certificado_fornecedor__numero_certificado_fornecedor__icontains=certificado_numero)
            | models.Q(numero_certificado_fornecedor_item__icontains=certificado_numero)
        )
    return q


def _build_dicas_busca_sem_resultado(
    *,
    produto_cq_id: int | None,
    corrida_norm: str,
    lote_norm: str,
    fornecedor,
    nf_entrada: str,
    certificado_numero: str,
) -> list[str]:
    """Códigos estáveis para o CQ mapear mensagens sem expor dados sensíveis."""
    if not corrida_norm and not lote_norm:
        return []
    dicas: list[str] = []
    seen: set[str] = set()
    base = _qs_items_cf_diag_base(
        fornecedor=fornecedor,
        nf_entrada=nf_entrada,
        certificado_numero=certificado_numero,
    ).order_by('-id')[:500]
    for item in base:
        if not _corrida_busca_match_cf_item(item, corrida_norm):
            continue
        cert = item.certificado_fornecedor
        if produto_cq_id is not None and item.produto_id is not None and item.produto_id != produto_cq_id:
            if 'PRODUTO_VINCULADO_DIFERENTE' not in seen:
                dicas.append('PRODUTO_VINCULADO_DIFERENTE')
                seen.add('PRODUTO_VINCULADO_DIFERENTE')
            continue
        if not _passes_corrida_lote_cf_item(item, corrida_norm, lote_norm):
            if lote_norm and 'LOTE_DIVERGENTE' not in seen:
                dicas.append('LOTE_DIVERGENTE')
                seen.add('LOTE_DIVERGENTE')
            continue
        if not _cf_status_is_registrado(cert.status):
            if 'CERTIFICADO_RASCUNHO' not in seen:
                dicas.append('CERTIFICADO_RASCUNHO')
                seen.add('CERTIFICADO_RASCUNHO')
    return dicas


def _build_diagnostico_superuser_busca(
    *,
    produto_cq_id: int | None,
    corrida_norm: str,
    lote_norm: str,
    fornecedor,
    nf_entrada: str,
    certificado_numero: str,
) -> dict:
    amostra: list[dict] = []
    base = _qs_items_cf_diag_base(
        fornecedor=fornecedor,
        nf_entrada=nf_entrada,
        certificado_numero=certificado_numero,
    ).order_by('-id')[:200]
    for item in base:
        if not _corrida_busca_match_cf_item(item, corrida_norm):
            continue
        cert = item.certificado_fornecedor
        motivos: list[str] = []
        if produto_cq_id is not None and item.produto_id is not None and item.produto_id != produto_cq_id:
            motivos.append('produto_diferente')
        if not _cf_status_is_registrado(cert.status):
            motivos.append(f'status_{cert.status}')
        if not _passes_corrida_lote_cf_item(item, corrida_norm, lote_norm):
            motivos.append('lote_ou_corrida_incompativel')
        if len(amostra) < 12:
            amostra.append(
                {
                    'item_id': item.id,
                    'certificado_id': cert.id,
                    'certificado_status': cert.status,
                    'produto_item_id': item.produto_id,
                    'corrida': (item.corrida or '')[:48],
                    'lote': (item.lote or '')[:48],
                    'motivos': motivos or ['sem_bloqueio_obvio_revisar_limite_ou_filtros'],
                }
            )
    return {'amostra': amostra, 'nota': 'Somente superuser + debug=1. Sem dados fiscais ou descrições completas.'}


class CertificadoViewSet(AutocompleteOrPaginationMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, CertificadoLegacyPermissions]
    queryset = Certificado.objects.select_related('nf_saida').all()
    serializer_class = CertificadoSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(nf_saida__numero__icontains=search)
                | Q(nf_saida__cliente__razao_social__icontains=search),
            )
        return aplicar_ordering(qs, self.request.query_params.get('ordering'), {'gerado_em': 'gerado_em'}, '-gerado_em')


class CertificadoQualidadeViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CertificadoQualidadePermissions]
    queryset = (
        CertificadoQualidade.objects.select_related('cliente', 'nota_fiscal', 'nota_fiscal_historica')
        .prefetch_related('itens__componentes')
        .all()
    )
    serializer_class = CertificadoQualidadeSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(cliente_nome_snapshot__icontains=search)
                | Q(nota_fiscal_numero__icontains=search)
                | Q(pedido_cliente__icontains=search),
            )
        status_f = (self.request.query_params.get('status') or '').strip()
        if status_f:
            qs = qs.filter(status__icontains=status_f)
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'numero': 'numero', 'data_emissao': 'data_emissao', 'criado_em': 'criado_em'},
            '-id',
        )

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

        payload = listar_corridas_disponiveis_produto(produto_id_int)
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


class CertificadoFornecedorEntradaViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CertificadoFornecedorEntradaPermissions]
    queryset = (
        CertificadoFornecedorEntrada.objects.select_related(
            'fornecedor',
            'nf_entrada_historica',
            'nf_entrada_operacional',
            'empresa_destinataria',
        )
        .prefetch_related(
            'itens__componentes',
            'itens__corridas_adicionais',
            'itens__item_conferencia__item_nfe_historico',
            'itens__item_conferencia__conferencia__nf_entrada_historica',
            'itens__item_conferencia__item_pedido_compra__pedido',
            'itens__item_conferencia__item_pedido_compra__produto',
            'itens__item_conferencia__produto',
        )
        .all()
    )
    serializer_class = CertificadoFornecedorEntradaSerializer
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero_certificado_fornecedor__icontains=search)
                | Q(fornecedor__razao_social__icontains=search)
                | Q(fornecedor_nome_snapshot__icontains=search)
                | Q(numero_nf_entrada__icontains=search),
            )
        status_f = (self.request.query_params.get('status') or '').strip()
        if status_f:
            qs = qs.filter(status__icontains=status_f)
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'numero_certificado_fornecedor': 'numero_certificado_fornecedor', 'criado_em': 'criado_em'},
            '-id',
        )

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
            nf_hist = (
                NFeEntradaHistoricaImportada.objects.select_related('fornecedor_emitente', 'empresa_destinataria')
                .prefetch_related('itens')
                .get(pk=nf_hist_id)
            )
        except NFeEntradaHistoricaImportada.DoesNotExist:
            return Response({'detail': 'NF-e de entrada histórica não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        emit = nf_hist.emit_json or {}
        conferencia = get_or_build_conferencia_for_nf_historica(nf_hist)
        conf_por_n_item = map_itens_conferencia_por_n_item(conferencia)
        itens_payload = []
        for idx, it in enumerate(nf_hist.itens.order_by('n_item')):
            prod = it.prod_json or {}
            ic = conf_por_n_item.get(it.n_item)
            corrida_conf, lote_conf, corridas_adicionais_conf = _corrida_lote_e_corridas_adicionais_de_conferencia(ic)
            row = {
                'ordem': idx + 1,
                'produto': ic.produto_id if ic and ic.produto_id else None,
                'codigo_produto': str(prod.get('cProd') or ''),
                'descricao_material': str(prod.get('xProd') or ''),
                'quantidade': float(prod.get('qCom') or 0),
                'unidade': str(prod.get('uCom') or ''),
                'ncm': str(prod.get('NCM') or ''),
                'norma': '',
                'corrida': corrida_conf,
                'lote': lote_conf,
                'corridas_adicionais': corridas_adicionais_conf,
                'numero_certificado_fornecedor_item': '',
                'data_certificado_fornecedor_item': None,
                'pagina_certificado_fornecedor': '',
                'observacao_origem_certificado': '',
                'tipo_dados_tecnicos': self._sugerir_tipo_item(
                    str(prod.get('cProd') or ''),
                    str(prod.get('xProd') or ''),
                    str(prod.get('NCM') or ''),
                ),
                'composicao_json': {},
                'ensaio_tracao_json': {},
                'ensaio_impacto_json': {},
                'observacoes_item': '',
                'componentes': [],
                'item_conferencia_id': ic.id if ic else None,
                'origem_nfe_item_numero': it.n_item if ic else None,
                'origem_nfe_numero': nf_hist.numero if ic else None,
                'origem_nfe_serie': nf_hist.serie if ic else None,
                'origem_display': (
                    f'NF {nf_hist.numero}/{nf_hist.serie} · item {it.n_item} · Conferência' if ic else ''
                ),
                'origem_conferencia_status': ic.status if ic else None,
                'origem_produto_vinculado': bool(ic.produto_id) if ic else False,
                'origem_rastreabilidade_completa': False,
            }
            if ic:
                pedido_ctx = _origem_pedido_compra_de_item_cf(ic)
                if pedido_ctx:
                    row.update(
                        {
                            'pedido_compra_id': pedido_ctx['pedido_compra_id'],
                            'pedido_compra_numero': pedido_ctx['pedido_compra_numero'],
                            'item_pedido_compra_id': pedido_ctx['item_pedido_compra_id'],
                            'item_pedido_resumo': pedido_ctx['item_pedido_resumo'],
                            'produto_pedido_codigo': pedido_ctx['produto_pedido_codigo'],
                            'produto_pedido_descricao': pedido_ctx['produto_pedido_descricao'],
                            'quantidade_pedido': pedido_ctx['quantidade_pedido'],
                            'unidade_pedido': pedido_ctx['unidade_pedido'],
                            'valor_unitario_pedido': pedido_ctx['valor_unitario_pedido'],
                            'origem_rastreabilidade_completa': True,
                        },
                    )
            itens_payload.append(row)
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
                'itens': itens_payload,
                'mensagens': [
                    'NF-e de entrada histórica carregada com vínculo à conferência quando disponível.',
                    'Complete corrida/lote e dados técnicos conforme o certificado do fornecedor.',
                ],
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
        debug_busca = str(request.query_params.get('debug') or '').strip() == '1' and bool(
            getattr(request.user, 'is_superuser', False)
        )
        status_param = (request.query_params.get('status') or '').strip().lower()
        include_rascunho = str(request.query_params.get('include_rascunho', '')).lower() in {'1', 'true', 'sim'}
        qs = ItemCertificadoFornecedorEntrada.objects.select_related('certificado_fornecedor', 'produto', 'certificado_fornecedor__fornecedor').prefetch_related('componentes').filter(
            ativo=True,
        )
        qs = _filter_cf_items_por_status_certificado(qs, status_param=status_param, include_rascunho=include_rascunho)

        if fornecedor:
            qs = qs.filter(certificado_fornecedor__fornecedor_id=fornecedor)
        if nf_entrada:
            qs = qs.filter(certificado_fornecedor__numero_nf_entrada__icontains=nf_entrada)
        if certificado_numero:
            qs = qs.filter(
                models.Q(certificado_fornecedor__numero_certificado_fornecedor__icontains=certificado_numero)
                | models.Q(numero_certificado_fornecedor_item__icontains=certificado_numero)
            )

        # Referência de produto no CQ: inclui itens do fornecedor com o mesmo produto OU
        # sem produto vinculado (entrada real); exclui outro produto_id para não misturar lotes.
        produto_cq_id = None
        if produto:
            try:
                produto_cq_id = int(str(produto).strip())
            except (TypeError, ValueError):
                produto_cq_id = None
        if produto_cq_id is not None:
            qs = qs.filter(models.Q(produto_id=produto_cq_id) | models.Q(produto__isnull=True))

        if not any([corrida, lote, produto, codigo, descricao, fornecedor, nf_entrada, certificado_numero]):
            return Response({'resultados': [], 'dicas_busca': []}, status=status.HTTP_200_OK)

        corrida_norm = _normalize_search_token(corrida)
        lote_norm = _normalize_search_token(lote)
        codigo_norm = _normalize_search_token(codigo)
        descricao_norm = (descricao or '').strip().lower()
        norma_ref = (request.query_params.get('norma') or '').strip().upper()
        tipo_tecnico_ref = (request.query_params.get('tipo_dados_tecnicos') or '').strip()
        filtered_items = []
        for item in qs.order_by('-id')[:300]:
            score = 0
            if not _passes_corrida_lote_cf_item(item, corrida_norm, lote_norm):
                continue
            item_corrida_norm, item_lote_norm = _effective_corrida_lote_norms_cf_item(item)
            if corrida_norm:
                if _contains_normalized(item_corrida_norm, corrida_norm):
                    score += 100
                elif _contains_normalized(item_lote_norm, corrida_norm):
                    score += 70
                else:
                    score += 95
            if lote_norm:
                if _contains_normalized(item_lote_norm, lote_norm):
                    score += 80
                elif _contains_normalized(item_corrida_norm, lote_norm):
                    score += 50
            if produto_cq_id is not None and item.produto_id == produto_cq_id:
                score += 25
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
            dicas = _build_dicas_busca_sem_resultado(
                produto_cq_id=produto_cq_id,
                corrida_norm=corrida_norm,
                lote_norm=lote_norm,
                fornecedor=fornecedor,
                nf_entrada=nf_entrada,
                certificado_numero=certificado_numero,
            )
            payload: dict = {'resultados': [], 'dicas_busca': dicas}
            if debug_busca:
                payload['diagnostico'] = _build_diagnostico_superuser_busca(
                    produto_cq_id=produto_cq_id,
                    corrida_norm=corrida_norm,
                    lote_norm=lote_norm,
                    fornecedor=fornecedor,
                    nf_entrada=nf_entrada,
                    certificado_numero=certificado_numero,
                )
            return Response(payload, status=status.HTTP_200_OK)

        filtered_items.sort(key=lambda x: (x[0], x[1].id), reverse=True)
        resultados = []
        corrida_bucket: dict[tuple[str, str], list[ItemCertificadoFornecedorEntrada]] = {}
        for _, item in filtered_items:
            dc, dl = _display_corrida_lote_cf_item(item)
            key = (
                str(item.certificado_fornecedor.fornecedor_id or ''),
                _normalize_search_token(dc or dl or ''),
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
            disp_corrida, disp_lote = _display_corrida_lote_cf_item(item)
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
                _normalize_search_token(disp_corrida or disp_lote or ''),
            )
            siblings = corrida_bucket.get(key, [])
            siblings_fp = {_fingerprint(s) for s in siblings}
            divergencia_dados = len(siblings_fp) > 1
            produto_vinculado_resp = item.produto_id is not None
            if produto_cq_id is not None:
                if item.produto_id == produto_cq_id:
                    produto_match_tipo = 'vinculado'
                    aviso_sem_vinculo_produto = ''
                elif item.produto_id is None:
                    produto_match_tipo = 'sem_vinculo'
                    aviso_sem_vinculo_produto = (
                        'Item do certificado fornecedor sem produto vinculado. Confira código, descrição e corrida antes de aplicar.'
                    )
                else:
                    produto_match_tipo = 'outro_produto'
                    aviso_sem_vinculo_produto = ''
            elif item.produto_id is None:
                produto_match_tipo = 'sem_vinculo'
                aviso_sem_vinculo_produto = (
                    'Item do certificado fornecedor sem produto vinculado. Confira código, descrição e corrida antes de aplicar.'
                )
            else:
                produto_match_tipo = None
                aviso_sem_vinculo_produto = ''
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
                    'status_certificado_fornecedor': _cf_status_canonical(cert.status),
                    'produto': item.produto_id,
                    'produto_vinculado': produto_vinculado_resp,
                    'produto_match_tipo': produto_match_tipo,
                    'aviso_sem_vinculo_produto': aviso_sem_vinculo_produto,
                    'codigo_produto': item.codigo_produto,
                    'descricao_material': item.descricao_material,
                    'norma': item.norma,
                    'corrida': disp_corrida,
                    'lote': disp_lote,
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
                        if _cf_status_canonical(cert.status) == CertificadoFornecedorEntrada.Status.RASCUNHO else ''
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
        out: dict = {'resultados': resultados, 'dicas_busca': []}
        if debug_busca:
            out['diagnostico'] = _build_diagnostico_superuser_busca(
                produto_cq_id=produto_cq_id,
                corrida_norm=corrida_norm,
                lote_norm=lote_norm,
                fornecedor=fornecedor,
                nf_entrada=nf_entrada,
                certificado_numero=certificado_numero,
            )
        return Response(out, status=status.HTTP_200_OK)
