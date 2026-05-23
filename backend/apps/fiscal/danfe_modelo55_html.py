"""DANFE Conferência modelo 55 — template HTML/CSS + WeasyPrint."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

TEMPLATE_NAME = 'danfe/modelo55_conferencia.html'
CSS_REL = Path(__file__).resolve().parent / 'templates' / 'danfe' / 'modelo55_conferencia.css'


def _css_path() -> str:
    return str(CSS_REL)


def preparar_contexto_template(dados: dict[str, Any]) -> dict[str, Any]:
    """Normaliza dict para o template Jinja/Django."""
    itens = []
    for linha in dados.get('itens') or []:
        snap = linha.get('snapshot_fiscal') or {}
        from apps.fiscal.snapshot_fiscal_helpers import get_icms_snapshot, get_ipi_snapshot

        icms = get_icms_snapshot(snap)
        ipi = get_ipi_snapshot(snap)
        from apps.fiscal.danfe_conferencia import _money, _qty

        itens.append(
            {
                **linha,
                'cst_display': (icms.get('cst_icms') or icms.get('csosn') or '—'),
                'q_com_display': _qty(linha.get('q_com')),
                'v_un_com_display': _money(linha.get('v_un_com')),
                'v_prod_display': _money(linha.get('v_prod')),
                'bc_icms_display': _fmt_money(icms.get('base')),
                'v_icms_display': _fmt_money(icms.get('valor')),
                'aliq_icms_display': (icms.get('aliquota') or '0'),
                'v_ipi_display': _fmt_money(ipi.get('valor')),
                'aliq_ipi_display': (ipi.get('aliquota') or '0'),
            },
        )
    emit = dados.get('emitente_detalhe') or dados.get('emitente') or {}
    dest = dados.get('destinatario_detalhe') or dados.get('destinatario') or {}
    tot = dados.get('totais_imposto') or {}
    tr = dados.get('transporte_detalhe') or {}
    return {
        'd': dados,
        'emit': emit,
        'dest': dest,
        'tot': tot,
        'tr': tr,
        'itens': itens,
        'duplicatas': dados.get('duplicatas') or [],
        'inf_compl': (dados.get('informacoes_complementares') or '').strip(),
        'inf_fisco': (dados.get('informacoes_fisco') or '').strip(),
        'chave_display': dados.get('chave_display') or '',
        'protocolo_display': dados.get('protocolo_display') or '',
        'consulta_autenticidade': dados.get('consulta_autenticidade') or '',
        'barcode_msg': 'CÓDIGO DE BARRAS SERÁ GERADO APÓS AUTORIZAÇÃO SEFAZ',
        'reservada_hint': 'ÁREA RESERVADA',
        'sem_duplicatas': 'Sem duplicatas geradas',
        # Grade visual via CSS — linhas <tr> vazias quebravam paginação (1 item → 2 páginas).
        'linhas_vazias_produtos': [],
    }


def _fmt_money(v) -> str:
    from apps.core.pdf.formatters import format_currency_br

    return format_currency_br(v)


def _contar_paginas_pdf(pdf_bytes: bytes) -> int:
    from pypdf import PdfReader

    return len(PdfReader(BytesIO(pdf_bytes)).pages)


def _salvar_debug_html_pdf(html_string: str, pdf_bytes: bytes, dados: dict[str, Any]) -> None:
    if not settings.DEBUG:
        return
    try:
        media_root = Path(settings.MEDIA_ROOT)
        debug_dir = media_root / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)
        slug = (dados.get('numero_nf') or dados.get('numero') or dados.get('nfe_saida_id') or 'danfe')
        slug = ''.join(c if c.isalnum() or c in '-_' else '_' for c in str(slug))[:80]
        (debug_dir / f'danfe_html_{slug}.html').write_text(html_string, encoding='utf-8')
        (debug_dir / f'danfe_html_{slug}.pdf').write_bytes(pdf_bytes)
    except OSError as exc:
        logger.debug('DANFE debug save ignorado: %s', exc)


def gerar_pdf_weasyprint(dados: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    from weasyprint import CSS, HTML

    ctx = preparar_contexto_template(dados)
    html_string = render_to_string(TEMPLATE_NAME, ctx)
    base_url = str(CSS_REL.parent)
    pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf(
        stylesheets=[CSS(filename=_css_path())],
    )
    page_count = _contar_paginas_pdf(pdf_bytes)
    meta = {
        'moc': '7.0-anexo-ii-3.8.1-html-pagina-unica',
        'template': TEMPLATE_NAME,
        'template_path': str(CSS_REL.parent / 'modelo55_conferencia.html'),
        'pdf_page_count': page_count,
        'pdf_bytes': len(pdf_bytes),
        'gerado_em': datetime.now(timezone.utc).isoformat(),
    }
    if settings.DEBUG:
        logger.info(
            'DANFE WeasyPrint renderer=html template=%s pages=%s bytes=%s nf=%s',
            TEMPLATE_NAME,
            page_count,
            len(pdf_bytes),
            dados.get('nfe_saida_id') or dados.get('numero_nf'),
        )
        _salvar_debug_html_pdf(html_string, pdf_bytes, dados)
    return pdf_bytes, meta
