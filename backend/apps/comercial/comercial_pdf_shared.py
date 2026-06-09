"""Utilitários compartilhados para PDFs comerciais (proposta, pedido de venda, pedido de compra)."""

from __future__ import annotations

import logging
import os
import re

from django.http import HttpResponse

from apps.cadastros.models import Cliente, Empresa
from xml.sax.saxutils import escape

from apps.core.pdf.formatters import endereco_cadastro, fmt_date_br

logger = logging.getLogger(__name__)

NCM_NAO_INFORMADO = 'NCM não informado'


def prazo_entrega_exibicao(*, texto: str | None = None, data=None) -> str:
    """Prazo de entrega para PDF: texto comercial ou data legada."""
    t = (texto or '').strip()
    if t:
        return t
    if data:
        return fmt_date_br(data)
    return '—'


def prazo_entrega_exibicao_pedido(pedido) -> str:
    return prazo_entrega_exibicao(
        texto=getattr(pedido, 'prazo_entrega_texto', None),
        data=getattr(pedido, 'prazo_entrega', None),
    )


def prazo_entrega_exibicao_proposta(proposta) -> str:
    return prazo_entrega_exibicao(
        texto=getattr(proposta, 'prazo_entrega_texto', None),
        data=None,
    )


def _ncm_de_snapshot(snapshot: dict | None) -> str:
    if not isinstance(snapshot, dict):
        return ''
    for chave in ('ncm', 'ncm_efetivo', 'codigo_ncm', 'NCM'):
        val = snapshot.get(chave)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ''


def resolver_ncm_item_comercial(
    *,
    produto=None,
    snapshot_produto: dict | None = None,
    snapshot_fiscal: dict | None = None,
    ncm_avulso: str | None = None,
) -> str:
    """
    NCM para PDF comercial — somente dados já gravados (produto, snapshot ou avulso).
    Não consulta regra fiscal nem recalcula impostos.
    """
    if produto is not None:
        try:
            cod = (produto.get_ncm_efetivo_codigo() or '').strip()
            if cod:
                return cod
        except Exception:
            pass
    for snap in (snapshot_fiscal, snapshot_produto):
        cod = _ncm_de_snapshot(snap)
        if cod:
            return cod
    avulso = (ncm_avulso or '').strip()
    if avulso:
        return avulso
    return NCM_NAO_INFORMADO


def descricao_pdf_com_linha_ncm(descricao: str, ncm: str) -> str:
    """Descrição + linha secundária «NCM: …» (layout PDF, sem coluna extra)."""
    desc_safe = escape((descricao or '').strip() or '—')
    ncm_safe = escape((ncm or '').strip() or NCM_NAO_INFORMADO)
    return f'{desc_safe}<br/><font size="7" color="#64748b">NCM: {ncm_safe}</font>'


def logotipo_path_empresa(emp: Empresa | None) -> str | None:
    if not emp:
        return None
    try:
        if emp.logotipo and getattr(emp.logotipo, 'path', None):
            p = emp.logotipo.path
            if p and os.path.isfile(p):
                return p
    except Exception as exc:
        logger.debug('logo empresa id=%s: %s', getattr(emp, 'pk', None), exc)
    return None


def logotipo_path_fallback() -> str | None:
    try:
        for emp in Empresa.objects.exclude(logotipo='').only('logotipo')[:40]:
            p = logotipo_path_empresa(emp)
            if p:
                return p
    except Exception as exc:
        logger.debug('logo fallback: %s', exc)
    return None


def endereco_empresa(e: Empresa) -> str:
    return endereco_cadastro(
        e.logradouro or '',
        e.numero or '',
        e.complemento or '',
        e.bairro or '',
        e.cidade or '',
        e.uf or '',
        e.cep or '',
    )


def endereco_cliente(c: Cliente | None) -> str:
    if not c:
        return '—'
    return endereco_cadastro(
        c.logradouro or '',
        c.numero or '',
        c.complemento or '',
        c.bairro or '',
        c.cidade or '',
        c.uf or '',
        c.cep or '',
    )


def condicoes_pagamento_exibicao(*, condicao_texto: str, dias_parcelas: list) -> str:
    dias = list(dias_parcelas or [])
    if dias:
        return ','.join(str(int(d)) for d in dias)
    return (condicao_texto or '').strip() or '—'


def parcelas_exibicao(*, quantidade_parcelas: int, vencimentos_previstos: list, dias_parcelas: list) -> str:
    n = int(quantidade_parcelas or 0)
    if n > 0:
        return str(n)
    v = [x for x in (vencimentos_previstos or []) if x]
    if v:
        return str(len(v))
    dias = dias_parcelas or []
    if dias:
        return str(len(dias))
    return '—'


def vencimentos_exibicao(vencimentos_previstos: list) -> str:
    v = []
    try:
        for d in vencimentos_previstos or []:
            if d:
                v.append(fmt_date_br(d))
    except Exception:
        pass
    return ' · '.join(v) if v else '—'


def nome_vendedor(*, vendedor_ref, vendedor_texto: str) -> str:
    try:
        if vendedor_ref and (vendedor_ref.nome or '').strip():
            return (vendedor_ref.nome or '').strip()
    except Exception:
        pass
    return (vendedor_texto or '').strip() or '—'


def pdf_http_response(content: bytes, *, filename: str) -> HttpResponse:
    safe = re.sub(r'[/\\]+', '-', filename or 'documento').strip() or 'documento'
    if not safe.lower().endswith('.pdf'):
        safe = f'{safe}.pdf'
    resp = HttpResponse(content, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{safe}"'
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp['Pragma'] = 'no-cache'
    resp['Expires'] = '0'
    resp['Vary'] = 'Authorization, Cookie'
    return resp
