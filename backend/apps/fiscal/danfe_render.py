"""NF-e 3.5.4.4 — renderização DANFE Conferência (HTML/WeasyPrint + fallback ReportLab).

POC 3.5.4.6: renderer opcional BrazilFiscalReport via ``FISCAL_DANFE_RENDERER`` (default html).
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.fiscal.models import NFeSaida

logger = logging.getLogger(__name__)

RENDERER_HTML = 'html'
RENDERER_BFR = 'brazil_fiscal_report'
RENDERER_REPORTLAB = 'reportlab_fallback'

# Diagnóstico 3.5.4.4 (registrado também no roadmap):
# - nfelib: bindings XML NF-e 4.00; sem gerador DANFE/PDF no pacote instalado.
# - PyNFe: comunicação SEFAZ; sem gerador DANFE/PDF.
# - xhtml2pdf: depende de cadeia cairo/svg difícil no python:3.12-slim sem libs.
# - WeasyPrint: viável com libcairo/pango no Docker → escolhido para template HTML/CSS.
# - ReportLab Canvas (3.5.4.x): mantido como fallback offline.


def _renderer_configurado() -> str:
    val = (getattr(settings, 'FISCAL_DANFE_RENDERER', None) or RENDERER_HTML).strip().lower()
    if val in (RENDERER_HTML, RENDERER_BFR, RENDERER_REPORTLAB):
        return val
    return RENDERER_HTML


def _render_brazil_fiscal_report(
    dados: dict[str, Any],
    *,
    nfe_saida_id: int | None,
) -> tuple[bytes, dict[str, Any]] | None:
    """Retorna PDF/meta ou None para cair no fluxo HTML/ReportLab."""
    pk = dados.get('nfe_saida_id') or nfe_saida_id
    if not pk:
        return None
    try:
        nf = NFeSaida.objects.get(pk=pk)
    except NFeSaida.DoesNotExist:
        return None

    try:
        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
            gerar_danfe_bfr_de_nfe_saida_preview,
        )

        pdf, meta = gerar_danfe_bfr_de_nfe_saida_preview(nf)
        if meta.get('bloqueado'):
            return pdf, meta
        meta.setdefault('filename', dados.get('filename', meta.get('filename')))
        meta['conferencia'] = True
        meta['preview'] = True
        return pdf, meta
    except Exception as exc:
        logger.warning(
            'BrazilFiscalReport falhou para NF-e %s (%s); fallback HTML.',
            pk,
            exc,
        )
        return None


def _render_reportlab_fallback(
    dados: dict[str, Any],
    meta: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    from apps.fiscal.danfe_modelo55_conferencia import DanfeMocA4RetratoRenderer

    pdf = DanfeMocA4RetratoRenderer(dados).build()
    meta['render_engine'] = 'reportlab_canvas_fallback'
    meta['moc'] = '7.0-anexo-ii-3.8.1-canvas'
    meta.setdefault('mensagens', []).append(
        'Renderização via fallback ReportLab (FISCAL_DANFE_RENDERER=reportlab_fallback).',
    )
    return pdf, meta


def render_danfe_conferencia_pdf(
    dados: dict[str, Any],
    *,
    nfe_saida_id: int | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Gera PDF DANFE conferência; preferência WeasyPrint + template fiscal."""
    if dados.get('bloqueado'):
        return b'', dados

    renderer = _renderer_configurado()
    if renderer == RENDERER_BFR:
        bfr = _render_brazil_fiscal_report(dados, nfe_saida_id=nfe_saida_id)
        if bfr is not None:
            pdf, meta = bfr
            if pdf or meta.get('bloqueado'):
                return pdf, meta
    elif renderer == RENDERER_REPORTLAB:
        meta = {
            'nfe_saida_id': dados.get('nfe_saida_id') or nfe_saida_id,
            'numero': dados.get('numero'),
            'status': dados.get('status'),
            'preview': True,
            'bloqueado': False,
            'conferencia': True,
            'modelo': '55',
            'content_type': 'application/pdf',
            'filename': dados.get('filename', 'danfe-conferencia.pdf'),
            'mensagens': list(dados.get('mensagens') or []),
        }
        return _render_reportlab_fallback(dados, meta)

    meta = {
        'nfe_saida_id': dados.get('nfe_saida_id') or nfe_saida_id,
        'numero': dados.get('numero'),
        'status': dados.get('status'),
        'preview': True,
        'bloqueado': False,
        'conferencia': True,
        'modelo': '55',
        'content_type': 'application/pdf',
        'filename': dados.get('filename', 'danfe-conferencia.pdf'),
        'mensagens': list(dados.get('mensagens') or []),
    }

    try:
        from apps.fiscal.danfe_modelo55_html import gerar_pdf_weasyprint

        pdf, meta_html = gerar_pdf_weasyprint(dados)
        meta.update(meta_html)
        meta['render_engine'] = 'weasyprint_html'
        meta['renderer_config'] = renderer
        if settings.DEBUG:
            logger.info(
                'DANFE conferência renderer=%s engine=%s pages=%s bytes=%s template=%s',
                renderer,
                meta.get('render_engine'),
                meta.get('pdf_page_count'),
                meta.get('pdf_bytes', len(pdf)),
                meta.get('template'),
            )
        return pdf, meta
    except Exception as exc:
        logger.warning('DANFE HTML/WeasyPrint indisponível (%s); fallback ReportLab.', exc)

    from apps.fiscal.danfe_modelo55_conferencia import DanfeMocA4RetratoRenderer

    pdf = DanfeMocA4RetratoRenderer(dados).build()
    meta['render_engine'] = 'reportlab_canvas_fallback'
    meta['moc'] = '7.0-anexo-ii-3.8.1-canvas'
    meta.setdefault(
        'mensagens',
        [],
    ).append('Renderização via fallback ReportLab (template HTML indisponível).')
    return pdf, meta


def gerar_danfe_modelo55_conferencia_pdf(nfe_saida: NFeSaida) -> tuple[bytes, dict[str, Any]]:
    from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia

    dados = montar_dados_danfe_conferencia(nfe_saida)
    dados['nfe_saida_id'] = nfe_saida.pk
    return render_danfe_conferencia_pdf(dados, nfe_saida_id=nfe_saida.pk)
