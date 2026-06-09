"""PdfDocumentLayout: SimpleDocTemplate, margens, rodapé em canvas e dupla passagem (página X de Y)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from io import BytesIO
from typing import Any

from django.utils import timezone
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate

from apps.core.pdf.styles import C_MUTED

logger = logging.getLogger(__name__)

NEXUS_PDF_MARGIN_X = 8 * mm


def default_page_content_width() -> float:
    return A4[0] - 2 * NEXUS_PDF_MARGIN_X


def page_content_width(doc: SimpleDocTemplate) -> float:
    return A4[0] - doc.leftMargin - doc.rightMargin


def _truncate_canvas(canvas, text: str, max_w: float, font: str, size: float) -> str:
    canvas.setFont(font, size)
    t = text
    while t and canvas.stringWidth(t + '…', font, size) > max_w and len(t) > 8:
        t = t[:-1]
    if len(t) < len(text):
        t += '…'
    return t


def draw_nexus_footer(
    canvas,
    doc,
    *,
    document_kind_title: str,
    usage_tag: str = 'uso comercial',
    total_pages: int | None = None,
) -> None:
    """Rodapé em três linhas: geração, tipo de documento, numeração (evita sobreposição)."""
    canvas.saveState()
    w, _h = A4
    lm, rm = doc.leftMargin, doc.rightMargin
    usable = w - lm - rm

    y_rule = 14 * mm
    canvas.setStrokeColor(colors.HexColor('#cbd5e1'))
    canvas.setLineWidth(0.35)
    canvas.line(lm, y_rule, w - rm, y_rule)

    ts = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
    line1 = f'Documento gerado pelo NEXUS APP · {ts}'
    line2 = f'{document_kind_title} · {usage_tag}'
    if total_pages is not None and total_pages > 0:
        line3 = f'Página {doc.page} de {total_pages}'
    else:
        line3 = f'Página {doc.page}'

    font = 'Helvetica'
    canvas.setFillColor(C_MUTED)
    fs1, fs2, fs3 = 7.0, 6.85, 6.85
    y1, y2, y3 = 11.2 * mm, 8.1 * mm, 5.0 * mm

    t1 = _truncate_canvas(canvas, line1, usable, font, fs1)
    canvas.setFont(font, fs1)
    canvas.drawString(lm, y1, t1)
    t2 = _truncate_canvas(canvas, line2, usable, font, fs2)
    canvas.setFont(font, fs2)
    canvas.drawString(lm, y2, t2)
    canvas.setFont(font, fs3)
    canvas.drawRightString(w - rm, y3, line3)

    canvas.restoreState()


def footer_callback_factory(
    *,
    document_kind_title: str,
    usage_tag: str = 'uso comercial',
    total_pages: int | None,
):
    return partial(
        draw_nexus_footer,
        document_kind_title=document_kind_title,
        usage_tag=usage_tag,
        total_pages=total_pages,
    )


def _make_doc_template(
    buf,
    *,
    title: str,
    subject: str,
    author: str = 'NEXUS APP',
) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=NEXUS_PDF_MARGIN_X,
        rightMargin=NEXUS_PDF_MARGIN_X,
        topMargin=5.5 * mm,
        bottomMargin=15 * mm,
        title=title,
        author=author,
        subject=subject,
    )


def build_nexus_pdf_bytes(
    *,
    meta_title: str,
    meta_subject: str,
    story_builder: Callable[[], list[Any]],
    footer_document_kind: str,
    footer_usage_tag: str = 'uso comercial',
) -> bytes:
    """
    Platypus para o corpo; canvas só no rodapé.
    Dupla passagem + pypdf para total de páginas no rodapé.
    """
    buf1 = BytesIO()
    doc1 = _make_doc_template(buf1, title=meta_title, subject=meta_subject)
    story1 = story_builder()
    foot1 = footer_callback_factory(
        document_kind_title=footer_document_kind,
        usage_tag=footer_usage_tag,
        total_pages=None,
    )
    try:
        doc1.build(story1, onFirstPage=foot1, onLaterPages=foot1)
        buf1.seek(0)
        total_pages = max(1, len(PdfReader(buf1).pages))
    except Exception:
        logger.exception('NEXUS APP PDF: primeira passagem falhou')
        raise

    buf2 = BytesIO()
    doc2 = _make_doc_template(buf2, title=meta_title, subject=meta_subject)
    story2 = story_builder()
    foot2 = footer_callback_factory(
        document_kind_title=footer_document_kind,
        usage_tag=footer_usage_tag,
        total_pages=total_pages,
    )
    doc2.build(story2, onFirstPage=foot2, onLaterPages=foot2)
    pdf = buf2.getvalue()
    buf1.close()
    buf2.close()
    return pdf
