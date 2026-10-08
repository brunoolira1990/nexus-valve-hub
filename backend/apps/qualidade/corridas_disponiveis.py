"""Corridas/lotes disponíveis por produto (estoque + conferência + certificado fornecedor)."""

from __future__ import annotations

from apps.fiscal.models import EstoqueCorrida, ItemNFeEntradaConferencia
from apps.qualidade.models import CertificadoFornecedorEntrada, ItemCertificadoFornecedorEntrada


def _cf_status_canonical(status: str | None) -> str:
    return str(status or '').strip().lower()


def _cf_status_is_registrado(status: str | None) -> bool:
    return _cf_status_canonical(status) == CertificadoFornecedorEntrada.Status.REGISTRADO


def _bucket_key_corrida_lote(corrida: str, lote: str) -> str:
    c = (corrida or '').strip().upper()
    l = (lote or '').strip().upper()
    if not c and l:
        c, l = l, ''
    if not c:
        return ''
    return f'{c}\x1f{l}'


def _aplicar_ids_origem_cf(
    row: dict,
    *,
    certificado_fornecedor_id: int | None,
    item_certificado_fornecedor_id: int | None,
) -> dict:
    row['certificado_fornecedor_id'] = certificado_fornecedor_id
    row['item_certificado_fornecedor_id'] = item_certificado_fornecedor_id
    row['certificado_fornecedor_origem_id'] = certificado_fornecedor_id
    row['item_certificado_fornecedor_origem_id'] = item_certificado_fornecedor_id
    return row


def _linhas_corrida_cert_item(cert_item: ItemCertificadoFornecedorEntrada) -> list[tuple[str, str]]:
    linhas: list[tuple[str, str]] = []
    corrida_principal = (cert_item.corrida or '').strip()
    lote_principal = (cert_item.lote or '').strip()
    if corrida_principal or lote_principal:
        linhas.append((corrida_principal, lote_principal))
    for ca in cert_item.corridas_adicionais.all():
        corrida_extra = (ca.corrida or '').strip()
        lote_extra = (ca.lote or '').strip()
        if corrida_extra or lote_extra:
            linhas.append((corrida_extra, lote_extra))
    return linhas


def listar_corridas_disponiveis_produto(produto_id: int) -> list[dict]:
    """Mesma carga útil de GET /api/certificados-qualidade/corridas-disponiveis/."""
    estoque_rows = (
        EstoqueCorrida.objects
        .select_related('corrida')
        .filter(produto_id=produto_id)
        .order_by('-saldo', '-id')
    )
    conf_rows = (
        ItemNFeEntradaConferencia.objects
        .select_related('conferencia__nf_entrada_historica', 'conferencia__nf_entrada_historica__fornecedor_emitente')
        .prefetch_related('corridas_split')
        .filter(produto_id=produto_id)
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .order_by('-id')
    )
    cert_rows = (
        ItemCertificadoFornecedorEntrada.objects
        .select_related('certificado_fornecedor', 'certificado_fornecedor__fornecedor')
        .prefetch_related('corridas_adicionais')
        .filter(produto_id=produto_id, ativo=True)
        .order_by('-id')
    )

    resultados: dict[str, dict] = {}
    for est in estoque_rows:
        key = _bucket_key_corrida_lote(est.corrida.numero or '', '')
        if not key:
            continue
        resultados[key] = _aplicar_ids_origem_cf(
            {
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
            },
            certificado_fornecedor_id=None,
            item_certificado_fornecedor_id=None,
        )

    for conf in conf_rows:
        linhas_corrida: list[tuple[str, str]] = []
        splits = list(conf.corridas_split.all())
        if splits:
            for split_row in splits:
                corrida_split = (split_row.corrida or '').strip()
                lote_split = (split_row.lote or '').strip()
                if corrida_split or lote_split:
                    linhas_corrida.append((corrida_split, lote_split))
        else:
            corrida_conf = (conf.corrida or '').strip()
            if corrida_conf:
                linhas_corrida.append((corrida_conf, conf.lote or ''))

        for corrida_conf, lote_conf in linhas_corrida:
            if not corrida_conf:
                continue
            key = _bucket_key_corrida_lote(corrida_conf, lote_conf)
            if not key:
                continue
            item = resultados.get(key) or _aplicar_ids_origem_cf(
                {
                    'corrida': corrida_conf,
                    'lote': lote_conf,
                    'saldo': '0.000',
                    'unidade': conf.unidade_estoque_calculada or conf.unidade_nf or '',
                    'fornecedor': '',
                    'nf_entrada': conf.conferencia.nf_entrada_historica.numero if conf.conferencia_id else '',
                    'certificado_fornecedor': '',
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
                },
                certificado_fornecedor_id=None,
                item_certificado_fornecedor_id=None,
            )
            if lote_conf and not item.get('lote'):
                item['lote'] = lote_conf
            if conf.conferencia_id and not item.get('nf_entrada'):
                item['nf_entrada'] = conf.conferencia.nf_entrada_historica.numero
            resultados[key] = item

    for cert_item in cert_rows:
        cert = cert_item.certificado_fornecedor
        for corrida_raw, lote_raw in _linhas_corrida_cert_item(cert_item):
            if not corrida_raw and not lote_raw:
                continue
            if not corrida_raw and lote_raw:
                corrida_raw, lote_raw = lote_raw, ''
            if not corrida_raw:
                continue
            key = _bucket_key_corrida_lote(corrida_raw, lote_raw)
            if not key:
                continue
            item = resultados.get(key) or _aplicar_ids_origem_cf(
                {
                    'corrida': corrida_raw,
                    'lote': lote_raw,
                    'saldo': '0.000',
                    'unidade': cert_item.unidade or '',
                    'fornecedor': cert.fornecedor_nome_snapshot or '',
                    'nf_entrada': cert.numero_nf_entrada or '',
                    'certificado_fornecedor': cert_item.numero_certificado_fornecedor_item or cert.numero_certificado_fornecedor or '',
                    'status_certificado_fornecedor': cert.status,
                    'status_origem_tecnica': (
                        'certificado_fornecedor_registrado'
                        if _cf_status_is_registrado(cert.status)
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
                },
                certificado_fornecedor_id=cert.id,
                item_certificado_fornecedor_id=cert_item.id,
            )
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
            _aplicar_ids_origem_cf(
                item,
                certificado_fornecedor_id=cert.id,
                item_certificado_fornecedor_id=cert_item.id,
            )
            item['status_certificado_fornecedor'] = cert.status
            item['status_origem_tecnica'] = (
                'certificado_fornecedor_registrado'
                if _cf_status_is_registrado(cert.status)
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
            if _cf_status_canonical(cert.status) == CertificadoFornecedorEntrada.Status.RASCUNHO:
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

    return sorted(
        resultados.values(),
        key=lambda r: (
            0 if r.get('origem') == 'certificado_fornecedor' else 1,
            -float(r.get('saldo') or 0),
            (r.get('corrida') or ''),
        ),
    )
