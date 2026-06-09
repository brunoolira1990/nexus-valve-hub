"""
Renderização PDF de relatórios operacionais (ReportLab + Platypus).

O motor de relatórios PDF é independente do motor fiscal/DANFE.
Não utiliza WeasyPrint, BrazilFiscalReport nem templates fiscais.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from io import BytesIO
from typing import Any

from django.utils import timezone
from xml.sax.saxutils import escape
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.pdf.base import NEXUS_PDF_MARGIN_X, draw_nexus_footer
from apps.core.pdf.styles import C_BORDER, C_MUTED, C_PRIMARY, C_TABLE_HEADER_BG, SPACE_SM, SPACE_XS
from apps.relatorios.definitions import ReportDefinition

logger = logging.getLogger(__name__)

OPERATIONAL_DISCLAIMER = (
    'Relatório operacional. Não substitui documento fiscal ou contábil oficial.'
)


def _page_size(defn: ReportDefinition):
    return landscape(A4) if defn.orientation == 'landscape' else A4


def _content_width(defn: ReportDefinition, doc: SimpleDocTemplate) -> float:
    ps = _page_size(defn)
    return ps[0] - doc.leftMargin - doc.rightMargin


def _footer_callback(canvas, doc, *, total_pages: int | None):
    draw_nexus_footer(
        canvas,
        doc,
        document_kind_title='Relatório operacional',
        usage_tag=OPERATIONAL_DISCLAIMER,
        total_pages=total_pages,
    )


def _styles():
    return {
        'title': ParagraphStyle(
            'ReportTitle',
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=C_PRIMARY,
            spaceAfter=2,
        ),
        'subtitle': ParagraphStyle(
            'ReportSubtitle',
            fontName='Helvetica',
            fontSize=9,
            textColor=C_MUTED,
            spaceAfter=4,
        ),
        'meta': ParagraphStyle(
            'ReportMeta',
            fontName='Helvetica',
            fontSize=8,
            textColor=C_MUTED,
            leading=10,
        ),
        'section': ParagraphStyle(
            'ReportSection',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=C_PRIMARY,
            spaceBefore=6,
            spaceAfter=4,
        ),
        'cell': ParagraphStyle(
            'ReportCell',
            fontName='Helvetica',
            fontSize=7.5,
            textColor=colors.HexColor('#0f172a'),
            leading=9,
        ),
        'cell_hdr': ParagraphStyle(
            'ReportCellHdr',
            fontName='Helvetica-Bold',
            fontSize=7.5,
            textColor=colors.HexColor('#0f172a'),
            leading=9,
        ),
        'note': ParagraphStyle(
            'ReportNote',
            fontName='Helvetica-Oblique',
            fontSize=8,
            textColor=colors.HexColor('#b45309'),
            leading=10,
            spaceBefore=4,
            spaceAfter=4,
        ),
    }


class ReportPdfRenderer:
    """Converte ReportDefinition em bytes PDF."""

    def render(self, definition: ReportDefinition) -> bytes:
        return build_report_pdf_bytes(definition=definition)


def build_report_pdf_bytes(*, definition: ReportDefinition) -> bytes:
    st = _styles()

    def story_builder() -> list[Any]:
        story: list[Any] = []
        if definition.company_name:
            story.append(Paragraph(definition.company_name, st['subtitle']))
        if definition.environment_label:
            story.append(Paragraph(definition.environment_label, st['meta']))
        story.append(Paragraph(definition.title, st['title']))
        if definition.description:
            story.append(Paragraph(definition.description, st['subtitle']))
        if definition.period_label:
            story.append(Paragraph(f'Período: {definition.period_label}', st['meta']))
        ts = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
        gen = definition.generated_by or '—'
        story.append(Paragraph(f'Gerado em {ts} · Usuário: {gen}', st['meta']))
        story.append(Spacer(1, SPACE_XS))

        story.append(Paragraph('Filtros aplicados', st['section']))
        if definition.filters:
            for fl in definition.filters:
                story.append(Paragraph(f'• {fl.label}: {fl.value}', st['meta']))
        else:
            story.append(Paragraph('• Padrão do relatório', st['meta']))
        story.append(Spacer(1, SPACE_SM))

        for note in definition.notes:
            story.append(Paragraph(note, st['note']))
        if definition.aviso_historico:
            story.append(Paragraph(definition.aviso_historico, st['note']))

        if definition.metrics:
            story.append(Paragraph('Resumo', st['section']))
            story.extend(_metrics_table(definition, st))

        if definition.columns and definition.data.rows:
            story.append(Paragraph('Detalhamento', st['section']))
            story.extend(_data_table(definition, st))

        if definition.data.totals and definition.columns:
            story.append(Spacer(1, SPACE_XS))
            story.extend(_totals_table(definition, st))

        return story

    meta_title = definition.title[:120]
    return _build_pdf_two_pass(
        meta_title=meta_title,
        meta_subject=f'{definition.module}/{definition.report_id}',
        story_builder=story_builder,
        page_size_fn=lambda: _page_size(definition),
    )


def _build_pdf_two_pass(
    *,
    meta_title: str,
    meta_subject: str,
    story_builder: Callable[[], list[Any]],
    page_size_fn: Callable[[], tuple[float, float]],
) -> bytes:
    buf1 = BytesIO()
    pagesize = page_size_fn()
    doc1 = SimpleDocTemplate(
        buf1,
        pagesize=pagesize,
        leftMargin=NEXUS_PDF_MARGIN_X,
        rightMargin=NEXUS_PDF_MARGIN_X,
        topMargin=5.5 * mm,
        bottomMargin=15 * mm,
        title=meta_title,
        author='NEXUS APP',
        subject=meta_subject,
    )
    foot1 = partial(_footer_callback, total_pages=None)
    try:
        doc1.build(story_builder(), onFirstPage=foot1, onLaterPages=foot1)
        buf1.seek(0)
        total_pages = max(1, len(PdfReader(buf1).pages))
    except Exception:
        logger.exception('NEXUS relatório PDF: primeira passagem falhou')
        raise

    buf2 = BytesIO()
    doc2 = SimpleDocTemplate(
        buf2,
        pagesize=page_size_fn(),
        leftMargin=NEXUS_PDF_MARGIN_X,
        rightMargin=NEXUS_PDF_MARGIN_X,
        topMargin=5.5 * mm,
        bottomMargin=15 * mm,
        title=meta_title,
        author='NEXUS APP',
        subject=meta_subject,
    )
    foot2 = partial(_footer_callback, total_pages=total_pages)
    doc2.build(story_builder(), onFirstPage=foot2, onLaterPages=foot2)
    pdf = buf2.getvalue()
    buf1.close()
    buf2.close()
    return pdf


def _metrics_table(defn: ReportDefinition, st: dict) -> list[Any]:
    cells = [[Paragraph(m.label, st['cell_hdr']), Paragraph(m.value, st['cell'])] for m in defn.metrics]
    if not cells:
        return []
    col_w = (_page_size(defn)[0] - 2 * NEXUS_PDF_MARGIN_X) / 2
    tbl = Table(cells, colWidths=[col_w * 0.45, col_w * 0.55])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('BOX', (0, 0), (-1, -1), 0.4, C_BORDER),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, C_BORDER),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ],
        ),
    )
    return [tbl, Spacer(1, SPACE_SM)]


def _col_widths(defn: ReportDefinition, doc_w: float) -> list[float]:
    fixed = [c.width_mm * mm for c in defn.columns if c.width_mm]
    if len(fixed) == len(defn.columns):
        return fixed
    n = len(defn.columns) or 1
    return [doc_w / n] * n


def _align_para(text: str, style: ParagraphStyle, align: str) -> Paragraph:
    s = ParagraphStyle(
        f'{style.name}_{align}',
        parent=style,
        alignment={'right': TA_RIGHT, 'center': TA_CENTER}.get(align, TA_LEFT),
    )
    safe = escape(str(text or '—'))
    return Paragraph(safe, s)


def _data_table(defn: ReportDefinition, st: dict) -> list[Any]:
    doc_w = _page_size(defn)[0] - 2 * NEXUS_PDF_MARGIN_X
    widths = _col_widths(defn, doc_w)
    header = [
        _align_para(c.title, st['cell_hdr'], c.align) for c in defn.columns
    ]
    body = []
    for row in defn.data.rows:
        body.append(
            [_align_para(str(row.get(c.key, '—')), st['cell'], c.align) for c in defn.columns],
        )
    data = [header, *body]
    tbl = Table(data, colWidths=widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), C_TABLE_HEADER_BG),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7.5),
                ('BOX', (0, 0), (-1, -1), 0.4, C_BORDER),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, C_BORDER),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ],
        ),
    )
    return [tbl, Spacer(1, SPACE_SM)]


def _totals_table(defn: ReportDefinition, st: dict) -> list[Any]:
    totals = defn.data.totals or {}
    labels = []
    values = []
    for col in defn.columns:
        val = totals.get(col.key)
        if val:
            labels.append(col.title)
            values.append(val)
    if not labels:
        return []
    row = [
        Paragraph('<b>Totais</b>', st['cell_hdr']),
        *[Paragraph('', st['cell']) for _ in range(max(0, len(defn.columns) - 2))],
    ]
    if len(defn.columns) >= 2:
        parts = [f'{labels[i]}: {values[i]}' for i in range(len(labels))]
        row[-1] = Paragraph(' · '.join(parts), st['cell'])
    tbl = Table([row], colWidths=_col_widths(defn, _page_size(defn)[0] - 2 * NEXUS_PDF_MARGIN_X))
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e2e8f0')),
                ('BOX', (0, 0), (-1, -1), 0.5, C_BORDER),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ],
        ),
    )
    return [tbl]
