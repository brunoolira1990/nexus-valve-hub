"""
PdfHeader, PdfPartyBlock, PdfConditionBlock, PdfItemCard, PdfFinancialSummary,
PdfInfoGrid (resumo), PdfObservationsBlock, Instruções ao fornecedor — Platypus.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from apps.core.pdf.formatters import format_currency_br, money_nobr, nobr
from apps.core.pdf.styles import (
    C_BADGE_BG,
    C_BORDER,
    C_BRAND_ACCENT_ORANGE,
    C_BRAND_PRIMARY,
    C_CARD_BG,
    C_FRAME_LIGHT,
    C_HEADER_DEEP,
    C_MUTED,
    C_PRIMARY,
    C_SLATE_TEXT,
    C_TABLE_HEADER_BG,
    FONT_PDF_SECTION,
    SPACE_SM,
    SPACE_XS,
)

if TYPE_CHECKING:
    from reportlab.platypus import Flowable

logger = logging.getLogger(__name__)


def _color_html_hex(c: colors.Color) -> str:
    """Converte cor ReportLab para `#RRGGBB` (parágrafo / markup XML)."""
    h = c.hexval()
    if isinstance(h, str) and h.startswith('0x'):
        return '#' + h[2:].zfill(6).upper()
    if isinstance(h, str) and h.startswith('#'):
        return h.upper()
    return '#0F172A'


# Cabeçalho comercial: caixa máxima de desenho (proporção preservada; ~43 mm no intervalo 42–45 mm).
_HEADER_LOGO_MAX_DRAW_W = 43 * mm
_HEADER_LOGO_MAX_DRAW_H = 17.5 * mm
_HEADER_LOGO_PAD_X = 1.15 * mm
_HEADER_LOGO_PAD_Y = 0.65 * mm


def _read_logo_pixel_size(path: str) -> tuple[float, float]:
    """Lê dimensões em pixels do ficheiro; fallback 361×198 se leitura falhar."""
    try:
        ir = ImageReader(path)
        sz = ir.getSize()
        if sz and len(sz) >= 2 and sz[0] > 0 and sz[1] > 0:
            return float(sz[0]), float(sz[1])
    except Exception as exc:
        logger.debug('NEXUS APP PDF: logo getSize (%s)', exc)
    return 361.0, 198.0


def _logo_fit_proportional_box(
    pixel_w: float,
    pixel_h: float,
    *,
    max_draw_w: float,
    max_draw_h: float,
    pad_x: float,
    pad_y: float,
) -> tuple[float, float, float, float]:
    """
    (lw, lh, cw, rh) na mesma unidade que max_draw_* (pontos ao usar * mm).
    Escala pixel_w:pixel_h para caber em max_draw_w × max_draw_h sem distorção (tipo «contain»).
    """
    if pixel_w <= 0 or pixel_h <= 0:
        pixel_w, pixel_h = 361.0, 198.0
    ar = pixel_w / float(pixel_h)
    dw = max_draw_w
    dh = dw / ar
    if dh > max_draw_h:
        dh = max_draw_h
        dw = dh * ar
    return dw, dh, dw + 2 * pad_x, dh + 2 * pad_y


_DEFAULT_SUPPLIER_INSTRUCTIONS = (
    'Favor mencionar o número deste pedido na NF-e.',
    'Enviar XML e DANFE para o e-mail cadastrado.',
    'Enviar certificado de qualidade quando aplicável.',
    'Divergências de preço, prazo, quantidade ou impostos devem ser confirmadas antes do faturamento.',
)


def build_logo_cell(
    logo_path: str | None,
    *,
    ph_center: ParagraphStyle,
    compact: bool = False,
    header_spacious: bool = False,
    logo_w: float | None = None,
    logo_h: float | None = None,
) -> Flowable:
    if header_spacious:
        if logo_path and os.path.isfile(logo_path):
            iw, ih = _read_logo_pixel_size(logo_path)
        else:
            iw, ih = 361.0, 198.0
        lw, lh, cw, rh = _logo_fit_proportional_box(
            iw,
            ih,
            max_draw_w=_HEADER_LOGO_MAX_DRAW_W,
            max_draw_h=_HEADER_LOGO_MAX_DRAW_H,
            pad_x=_HEADER_LOGO_PAD_X,
            pad_y=_HEADER_LOGO_PAD_Y,
        )
    elif compact:
        # Área um pouco maior que antes: lettering fino em PNG costuma degradar se forçado demais.
        lw, lh, cw, rh = 36 * mm, 11.5 * mm, 38 * mm, 13 * mm
    else:
        lw, lh = (logo_w or 52 * mm), (logo_h or 18 * mm)
        cw, rh = 56 * mm, 20 * mm
    logo_cell = None
    if logo_path and os.path.isfile(logo_path):
        try:
            logo_inner = Table(
                [[Image(logo_path, width=lw, height=lh, mask='auto')]],
                colWidths=[cw],
                rowHeights=[rh],
            )
            if header_spacious:
                logo_inner.setStyle(
                    TableStyle(
                        [
                            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 1.15 * mm),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 1.35 * mm),
                            ('TOPPADDING', (0, 0), (-1, -1), 0.65 * mm),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.65 * mm),
                        ]
                    )
                )
            else:
                logo_inner.setStyle(
                    TableStyle(
                        [
                            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            (
                                'BOX',
                                (0, 0),
                                (-1, -1),
                                0.3,
                                colors.HexColor('#e2e8f0'),
                            ),
                        ]
                    )
                )
            logo_cell = logo_inner
        except Exception as exc:
            logger.info('NEXUS APP PDF: logo ignorada (%s)', exc)

    if logo_cell is None:
        nv_inner = Paragraph(
            f'<font size="20" color="{_color_html_hex(C_BRAND_PRIMARY)}"><b>NV</b></font><br/>'
            f'<font size="5.5" color="#64748b">{escape("NEXUS APP")}</font>',
            ph_center,
        )
        logo_cell = Table([[nv_inner]], colWidths=[cw], rowHeights=[rh])
        if header_spacious:
            logo_cell.setStyle(
                TableStyle(
                    [
                        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]
                )
            )
        else:
            logo_cell.setStyle(
                TableStyle(
                    [
                        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                        (
                            'BOX',
                            (0, 0),
                            (-1, -1),
                            0.3,
                            C_BORDER,
                        ),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]
                )
            )
    return logo_cell


def build_nexus_header_band(
    *,
    logo_path: str | None,
    marca_display: str,
    razao_social: str,
    document_title_html: str,
    page_width: float,
    ph_white: ParagraphStyle,
    ph_center: ParagraphStyle,
) -> Table:
    """PdfHeader legado com faixa azul escura; não usado no pedido de compra (ver `build_commercial_order_header`)."""
    logo_cell = build_logo_cell(logo_path, ph_center=ph_center)
    marca = escape(marca_display)
    razao = escape(razao_social)
    head_right = Paragraph(
        f'<font size="13" color="white"><b>{marca}</b></font><br/>'
        f'<font size="8" color="#cbd5e1">{razao}</font><br/>'
        f'<font size="3"><br/></font>'
        f'{document_title_html}',
        ph_white,
    )
    lw = 56 * mm
    band = Table([[logo_cell, head_right]], colWidths=[lw, page_width - lw])
    band.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0f2847')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]
        )
    )
    return band


def build_commercial_order_header(
    *,
    logo_path: str | None,
    emitente_razao_social: str | None,
    emitente_cnpj: str | None,
    emitente_ie: str | None,
    emitente_endereco: str | None,
    emitente_telefone: str | None,
    emitente_email: str | None,
    emitente_site: str | None,
    document_kind_upper: str,
    numero_nobr_html: str,
    meta_line_html: str,
    page_width: float,
    ph_small: ParagraphStyle,
    ph_center: ParagraphStyle,
    compact: bool = False,
) -> Table:
    """
    Cabeçalho em três colunas: logo (proporcional, sem borda), dados compactos do emitente, documento (tipo, nº, meta).
    Linhas do emitente omitidas quando vazias. CNPJ e IE na mesma linha quando ambos existirem.
    `numero_nobr_html` e `meta_line_html` com markup seguro.
    """
    logo_cell = build_logo_cell(logo_path, ph_center=ph_center, header_spacious=True)

    if logo_path and os.path.isfile(logo_path):
        iw, ih = _read_logo_pixel_size(logo_path)
    else:
        iw, ih = 361.0, 198.0
    logo_max_h = (13.2 * mm) if compact else _HEADER_LOGO_MAX_DRAW_H
    logo_max_w = (38.0 * mm) if compact else _HEADER_LOGO_MAX_DRAW_W
    _lw, _lh, cw_logo, _rh = _logo_fit_proportional_box(
        iw,
        ih,
        max_draw_w=logo_max_w,
        max_draw_h=logo_max_h,
        pad_x=_HEADER_LOGO_PAD_X,
        pad_y=_HEADER_LOGO_PAD_Y,
    )

    p_em_rz = ParagraphStyle(
        'HdrEmRz',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=7.35,
        leading=9.0,
        textColor=C_PRIMARY,
        alignment=TA_LEFT,
        spaceAfter=1.0,
    )
    p_em_ln = ParagraphStyle(
        'HdrEmLn',
        parent=ph_small,
        fontName='Helvetica',
        fontSize=6.05,
        leading=7.45,
        textColor=C_MUTED,
        alignment=TA_LEFT,
        spaceAfter=0.85,
    )
    p_em_muted = ParagraphStyle(
        'HdrEmMu',
        parent=ph_small,
        fontName='Helvetica',
        fontSize=5.95,
        leading=7.25,
        textColor=C_MUTED,
        alignment=TA_LEFT,
    )

    mid_rows: list[list] = []
    rz = (emitente_razao_social or '').strip()
    if rz:
        mid_rows.append([Paragraph(escape(rz), p_em_rz)])
    cj = (emitente_cnpj or '').strip()
    ie_s = (emitente_ie or '').strip()
    doc_id_bits: list[str] = []
    if cj:
        doc_id_bits.append(escape(cj))
    if ie_s:
        doc_id_bits.append(f'IE {escape(ie_s)}')
    if doc_id_bits:
        mid_rows.append([Paragraph(' · '.join(doc_id_bits), p_em_ln)])
    en = (emitente_endereco or '').strip()
    if en:
        mid_rows.append([Paragraph(escape(en), p_em_ln)])
    tel = (emitente_telefone or '').strip()
    em = (emitente_email or '').strip()
    st = (emitente_site or '').strip().replace('https://', '').replace('http://', '')
    contact_bits = []
    if tel:
        contact_bits.append(escape(tel))
    if em:
        contact_bits.append(escape(em))
    if st:
        contact_bits.append(escape(st))
    if contact_bits:
        mid_rows.append([Paragraph(' · '.join(contact_bits), p_em_muted)])

    if not mid_rows:
        mid_rows.append([Paragraph('Emitente não cadastrado.', p_em_muted)])

    cpad = 4 * mm
    # Respiro horizontal: maior entre logo e emitente; um pouco menor até o bloco do documento.
    g_logo_emit = 4.6 * mm
    g_emit_doc = 2.85 * mm
    w_doc = max(66 * mm, min(88 * mm, page_width * 0.292))
    w_log = cw_logo
    w_mid = page_width - w_log - w_doc
    if w_mid < 38 * mm:
        w_doc = max(60 * mm, page_width - w_log - 38 * mm)
        w_mid = page_width - w_log - w_doc

    mid_stack = Table(mid_rows, colWidths=[w_mid])
    mid_stack.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 0.35 * mm),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 0.35 * mm),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )

    p_kind = ParagraphStyle(
        'HdrK',
        parent=ph_small,
        fontName='Helvetica',
        fontSize=6.95,
        leading=9.35,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_RIGHT,
    )
    p_num = ParagraphStyle(
        'HdrN',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=11.2 if compact else 13.2,
        leading=14.0 if compact else 16.2,
        textColor=C_BRAND_PRIMARY,
        alignment=TA_RIGHT,
    )
    p_meta = ParagraphStyle(
        'HdrM',
        parent=ph_small,
        fontName='Helvetica',
        fontSize=6.85 if compact else 7.25,
        leading=9.2 if compact else 10.55,
        textColor=colors.HexColor('#475569'),
        alignment=TA_RIGHT,
    )
    row_kind = Paragraph(escape(document_kind_upper), p_kind)
    row_num = Paragraph(f'Nº {numero_nobr_html}', p_num)
    row_meta = Paragraph(meta_line_html, p_meta)

    right_stack = Table([[row_kind], [row_num], [row_meta]], colWidths=[w_doc])
    right_stack.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (0, 0), 3.2),
                ('TOPPADDING', (0, 1), (0, 1), 1.2),
                ('BOTTOMPADDING', (0, 1), (0, 1), 4.0),
                ('TOPPADDING', (0, 2), (0, 2), 0),
                ('BOTTOMPADDING', (0, 2), (-1, -1), 0),
            ]
        )
    )

    band = Table([[logo_cell, mid_stack, right_stack]], colWidths=[w_log, w_mid, w_doc])
    band.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 0.38, C_FRAME_LIGHT),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 5.0 * mm),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5.0 * mm),
                ('LEFTPADDING', (0, 0), (0, 0), cpad),
                ('RIGHTPADDING', (0, 0), (0, 0), g_logo_emit / 2),
                ('LEFTPADDING', (1, 0), (1, 0), g_logo_emit / 2),
                ('RIGHTPADDING', (1, 0), (1, 0), g_emit_doc / 2),
                ('LEFTPADDING', (2, 0), (2, 0), g_emit_doc / 2),
                ('RIGHTPADDING', (2, 0), (2, 0), cpad),
            ]
        )
    )
    return band


def party_block_table(
    title: str,
    razao: str,
    nome_fantasia: str | None,
    cnpj: str,
    endereco: str,
    telefone: str,
    email: str | None,
    site: str | None,
    col_w: float,
    *,
    p_title: ParagraphStyle,
    p_bold: ParagraphStyle,
    p_norm: ParagraphStyle,
    compact: bool = False,
) -> Table:
    """PdfPartyBlock: cartão leve; `compact` reduz padding e borda para caber 2 colunas no A4."""
    pt = 3.2 if compact else 7
    pl = 5 if compact else 10
    box_w = 0.35 if compact else 0.55
    rows: list[list] = [[Paragraph(f'<b>{escape(title)}</b>', p_title)]]
    rows.append([Paragraph(f'<b>{escape(razao or "—")}</b>', p_bold)])
    nf = (nome_fantasia or '').strip()
    rz = (razao or '').strip()
    if nf and nf.upper() != rz.upper():
        rows.append([Paragraph(f'<i>{escape(nf)}</i>', p_norm)])
    rows.append([Paragraph(escape(cnpj or '—'), p_norm)])
    rows.append([Paragraph(escape(endereco or '—'), p_norm)])
    tel = (telefone or '').strip()
    if tel:
        rows.append([Paragraph(escape(tel), p_norm)])
    em = (email or '').strip()
    if em:
        rows.append([Paragraph(escape(em), p_norm)])
    st = (site or '').strip().replace('https://', '').replace('http://', '')
    if st:
        rows.append([Paragraph(escape(st), p_norm)])
    tbl = Table(rows, colWidths=[col_w])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), box_w, C_FRAME_LIGHT),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), pl),
                ('RIGHTPADDING', (0, 0), (-1, -1), pl),
                ('TOPPADDING', (0, 0), (-1, -1), pt),
                ('BOTTOMPADDING', (0, 0), (-1, -1), pt),
                ('BACKGROUND', (0, 0), (-1, 0), C_TABLE_HEADER_BG),
                ('LINEBELOW', (0, 0), (-1, 0), 0.35, C_BORDER),
            ]
        )
    )
    return tbl


def two_party_row(em_tbl: Table, fo_tbl: Table, page_w: float, gap_mm: float = 3) -> Table:
    gap = gap_mm * mm
    half = (page_w - gap) / 2
    spacer_col = Table([['']], colWidths=[gap])
    parties = Table([[em_tbl, spacer_col, fo_tbl]], colWidths=[half, gap, half])
    parties.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    return parties


def build_section_title(
    text: str, *, ph_small: ParagraphStyle, compact: bool = False, page_w: float | None = None
) -> Paragraph | Table:
    """
    Título de secção. Com `page_w`, usa faixa clara alinhada ao certificado (fundo #E8EEF5 + linha inferior).
    Sem `page_w`, mantém parágrafo simples (compatível com chamadas antigas).
    """
    fs = FONT_PDF_SECTION if compact else 10
    lead = 11 if compact else 12
    st = ParagraphStyle(
        'NxSec',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=fs,
        leading=lead,
        textColor=C_PRIMARY,
        spaceAfter=0,
    )
    para = Paragraph(f'<b>{escape(text)}</b>', st)
    if page_w is None:
        return para
    rh = 6.0 * mm if compact else 6.6 * mm
    band = Table([[para]], colWidths=[page_w], rowHeights=[rh])
    band.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), C_TABLE_HEADER_BG),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2.8 * mm),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2.8 * mm),
                ('LINEBELOW', (0, 0), (-1, -1), 0.35, C_BORDER),
            ]
        )
    )
    return band


def build_conditions_section(
    section_title: str,
    field_rows: list[tuple[str, str]],
    *,
    page_w: float,
    ph_small: ParagraphStyle,
) -> list:
    """PdfConditionBlock: bloco comercial com linhas alternadas suaves."""
    p_line = ParagraphStyle('NxCond', parent=ph_small, fontSize=9, leading=12, textColor=C_SLATE_TEXT)
    inner: list = []
    for label, value in field_rows:
        inner.append(Paragraph(f'<b>{escape(label)}</b> {escape(value)}', p_line))
    inner_tbl = Table([[p] for p in inner], colWidths=[page_w - 2 * mm])
    inner_tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]
        )
    )
    return [build_section_title(section_title, ph_small=ph_small, page_w=page_w), Spacer(1, 2 * mm), inner_tbl]


def paragraph_grid_value(val: str, style: ParagraphStyle) -> Paragraph:
    """
    Valor em grelha de condições: texto simples com escape.
    Markup legado (<nobr>, <font>, etc.) só quando já veio formatado para Paragraph.
    """
    s = (val or '').strip() or '—'
    if '<' in s and '>' in s and ('</' in s or '/>' in s):
        return Paragraph(s, style)
    return Paragraph(escape(s), style)


def build_conditions_commercial_grid(
    section_title: str,
    field_rows: list[tuple[str, str]],
    *,
    page_w: float,
    ph_small: ParagraphStyle,
    pairs_per_row: int = 3,
    label_width_frac: float = 0.34,
    tight: bool = False,
) -> list:
    """Condições em grelha densa (até `pairs_per_row` pares por linha): menos altura que 2×2."""
    slots = max(1, min(3, int(pairs_per_row)))
    lf = max(0.26, min(0.44, float(label_width_frac)))
    lbl_fs = 6.55 if tight else 6.85
    val_fs = 6.75 if tight else 7.05
    p_lbl = ParagraphStyle(
        'NxCgL',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=lbl_fs,
        leading=8.0 if tight else 8.35,
        textColor=C_PRIMARY,
    )
    p_val = ParagraphStyle(
        'NxCgV',
        parent=ph_small,
        fontSize=val_fs,
        leading=8.1 if tight else 8.45,
        textColor=C_SLATE_TEXT,
    )
    gutter = 1.1 * mm if tight else 1.35 * mm
    w_pair = (page_w - (slots - 1) * gutter) / float(slots)
    w_lab = w_pair * lf
    w_val = w_pair * (1.0 - lf)
    col6: list[float] = []
    for _ in range(slots):
        col6.extend([w_lab, w_val])

    grid_rows: list[list] = []
    i = 0
    n = len(field_rows)
    while i < n:
        batch = field_rows[i : i + slots]
        row_cells: list = []
        for lab, val in batch:
            row_cells.append(Paragraph(escape(lab), p_lbl))
            row_cells.append(paragraph_grid_value(val, p_val))
        while len(row_cells) < slots * 2:
            row_cells.append(Paragraph('', p_lbl))
            row_cells.append(Paragraph('', p_val))
        grid_rows.append(row_cells)
        i += slots

    inner_tbl = Table(grid_rows, colWidths=col6)
    pad_cell = 2.0 if tight else 3.0
    line_cmds = [
        ('BOX', (0, 0), (-1, -1), 0.32, C_FRAME_LIGHT),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), pad_cell),
        ('BOTTOMPADDING', (0, 0), (-1, -1), pad_cell),
        ('LEFTPADDING', (0, 0), (-1, -1), 3.8 if tight else 4.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3.8 if tight else 4.5),
    ]
    for s in range(slots - 1):
        col_after = 2 * s + 1
        line_cmds.append(
            ('LINEAFTER', (col_after, 0), (col_after, -1), 0.2, colors.HexColor('#e2e8f0'))
        )
    inner_tbl.setStyle(TableStyle(line_cmds))
    sp_title = 0.55 * mm if tight else 0.85 * mm
    return [
        build_section_title(section_title, ph_small=ph_small, compact=True, page_w=page_w),
        Spacer(1, sp_title),
        inner_tbl,
    ]


def build_pedido_resumo_card(
    *,
    page_w: float,
    numero: str,
    data_emissao: str,
    status: str,
    valor_total,
    ph_small: ParagraphStyle,
) -> Table:
    """PdfInfoGrid: resumo em faixa horizontal com destaque no valor total e badge de status."""
    p_mix = ParagraphStyle('ResM', parent=ph_small, alignment=TA_CENTER, fontName='Helvetica', fontSize=9, leading=12)
    p_lbl = ParagraphStyle(
        'ResL',
        parent=ph_small,
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_CENTER,
    )
    p_val_big = ParagraphStyle(
        'ResVB',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=C_HEADER_DEEP,
        alignment=TA_CENTER,
    )

    c1 = Paragraph(
        f'<font size="7.5" color="#64748b">Pedido nº</font><br/><font size="11" color="#0a1628"><b>{nobr(numero)}</b></font>',
        p_mix,
    )
    c2 = Paragraph(
        f'<font size="7.5" color="#64748b">Data de emissão</font><br/><font size="11" color="#0a1628"><b>{nobr(data_emissao)}</b></font>',
        p_mix,
    )
    st_inner = Paragraph(f'<b><font color="#1e40af">{escape(status)}</font></b>', p_mix)
    badge = Table([[st_inner]], colWidths=[page_w * 0.22])
    badge.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), C_BADGE_BG),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]
        )
    )
    lbl_tot = Paragraph('<font size="7.5" color="#64748b">Valor total</font>', p_lbl)
    val_tot = Paragraph(format_currency_br(valor_total), p_val_big)
    c4_inner = Table([[lbl_tot], [val_tot]], colWidths=[page_w * 0.32])
    c4_inner.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))

    lbl_st = Paragraph('<font size="7.5" color="#64748b">Status</font>', p_lbl)
    c3_inner = Table([[lbl_st], [badge]], colWidths=[page_w * 0.22])
    c3_inner.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))

    w1 = page_w * 0.24
    w2 = page_w * 0.22
    w3 = page_w * 0.22
    w4 = page_w - w1 - w2 - w3
    row = Table([[c1, c2, c3_inner, c4_inner]], colWidths=[w1, w2, w3, w4])
    row.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('LINEAFTER', (0, 0), (0, 0), 0.35, C_BORDER),
                ('LINEAFTER', (1, 0), (1, 0), 0.35, C_BORDER),
                ('LINEAFTER', (2, 0), (2, 0), 0.35, C_BORDER),
            ]
        )
    )
    outer = Table([[row]], colWidths=[page_w])
    outer.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.55, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0, 0), (-1, -1), C_CARD_BG),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]
        )
    )
    return outer


def build_item_line_table(
    *,
    codigo: str,
    descricao: str,
    unidade: str,
    qtd_txt: str,
    valor_unit,
    valor_produtos,
    desconto,
    ipi,
    icms_st,
    total,
    page_w: float,
    ph_small: ParagraphStyle,
    descricao_markup: bool = False,
    nota_rodape: str | None = None,
    dense: bool = False,
) -> Table:
    """Item em formato tabela compacta: descrição em destaque, código secundário, métricas densas."""
    p_cod = ParagraphStyle(
        'NxLnC',
        parent=ph_small,
        fontName='Helvetica',
        fontSize=6.9,
        leading=8.2,
        textColor=C_MUTED,
        alignment=TA_RIGHT,
    )
    p_desc = ParagraphStyle(
        'NxLnD',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=9.1,
        leading=10.8,
        textColor=C_HEADER_DEEP,
        alignment=TA_LEFT,
    )
    p_h = ParagraphStyle(
        'NxLnH',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=6.2,
        leading=7.4,
        textColor=C_MUTED,
        alignment=TA_CENTER,
    )
    p_hr = ParagraphStyle('NxLnHR', parent=p_h, alignment=TA_RIGHT)
    p_cell = ParagraphStyle(
        'NxLnN', parent=ph_small, fontSize=7.0, leading=8.2, textColor=C_SLATE_TEXT, alignment=TA_CENTER
    )
    p_cell_r = ParagraphStyle('NxLnNR', parent=p_cell, alignment=TA_RIGHT)
    p_tot = ParagraphStyle(
        'NxLnT',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=8.5,
        textColor=C_HEADER_DEEP,
        alignment=TA_RIGHT,
    )

    top = Table(
        [
            [
                Paragraph(
                    descricao if descricao_markup else escape(descricao),
                    p_desc,
                ),
                Paragraph(f'Cód. {escape(codigo)}', p_cod),
            ]
        ],
        colWidths=[page_w * 0.78, page_w * 0.22],
    )
    top.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]
        )
    )

    cw = [page_w / 8] * 8
    head = [
        Paragraph('<b>Un.</b>', p_h),
        Paragraph('<b>Qtd.</b>', p_h),
        Paragraph('<b>Unitário</b>', p_hr),
        Paragraph('<b>Produtos</b>', p_hr),
        Paragraph('<b>Desc.</b>', p_hr),
        Paragraph('<b>IPI</b>', p_hr),
        Paragraph('<b>ICMS ST</b>', p_hr),
        Paragraph('<b>Total</b>', p_hr),
    ]
    data = [
        Paragraph(nobr(unidade), p_cell),
        Paragraph(nobr(qtd_txt), p_cell),
        Paragraph(format_currency_br(valor_unit), p_cell_r),
        Paragraph(format_currency_br(valor_produtos), p_cell_r),
        Paragraph(format_currency_br(desconto), p_cell_r),
        Paragraph(format_currency_br(ipi), p_cell_r),
        Paragraph(format_currency_br(icms_st), p_cell_r),
        Paragraph(format_currency_br(total), p_tot),
    ]
    pad_cell = 1 if dense else 2
    metrics = Table([head, data], colWidths=cw)
    metrics.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), pad_cell),
                ('BOTTOMPADDING', (0, 0), (-1, -1), pad_cell),
                ('LINEABOVE', (0, 0), (-1, 0), 0.3, colors.HexColor('#e2e8f0')),
                ('LINEBELOW', (0, 0), (-1, 0), 0.2, colors.HexColor('#e2e8f0')),
                ('BACKGROUND', (0, 0), (-1, 0), C_TABLE_HEADER_BG),
            ]
        )
    )

    card_rows: list = [[top], [metrics]]
    if nota_rodape:
        p_note = ParagraphStyle(
            'NxLnNote',
            parent=ph_small,
            fontSize=6.4,
            leading=7.6,
            textColor=C_MUTED,
            alignment=TA_LEFT,
        )
        card_rows.append([Paragraph(escape(nota_rodape), p_note)])

    pad_box = 2.2 if dense else 3.5
    card = Table(card_rows, colWidths=[page_w], hAlign='LEFT')
    card.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.32, C_FRAME_LIGHT),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('TOPPADDING', (0, 0), (-1, -1), pad_box),
                ('BOTTOMPADDING', (0, 0), (-1, -1), pad_box),
                ('LEFTPADDING', (0, 0), (-1, -1), 4 if dense else 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4 if dense else 5),
            ]
        )
    )
    return card


# Larguras proporcionais da tabela de itens do pedido de venda (soma = 1.0).
# Total e colunas monetárias mais largas; descrição ocupa linha inteira acima.
_RAW_PV_BATCH_COL_FRACS = (0.060, 0.070, 0.120, 0.130, 0.100, 0.090, 0.090, 0.190)


def _normalize_width_fracs(fracs: tuple[float, ...]) -> tuple[float, ...]:
    total = sum(fracs)
    if not fracs or total <= 0:
        raise ValueError('fracs must have positive sum')
    if abs(total - 1.0) < 1e-6:
        return fracs
    return tuple(f / total for f in fracs)


_PV_BATCH_COL_FRACS = _normalize_width_fracs(_RAW_PV_BATCH_COL_FRACS)


def pedido_venda_items_batch_col_fracs() -> tuple[float, ...]:
    """Frações de largura das colunas da tabela de itens (soma 1.0)."""
    return _PV_BATCH_COL_FRACS


def wrap_plate_full_width(block: Table, page_w: float) -> Table:
    """Envolve bloco para ocupar a largura útil do frame, alinhado à esquerda."""
    outer = Table([[block]], colWidths=[page_w], hAlign='LEFT')
    outer.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    return outer


def build_pedido_venda_items_batch_table(
    *,
    page_w: float,
    ph_small: ParagraphStyle,
    linhas: list[dict],
    ultra_compact: bool = False,
    nota_na_descricao: bool = False,
    readable_compact: bool = False,
    descricao_largura_total: bool = False,
) -> Table:
    """
    Tabela única de itens do pedido de venda — cabeçalho compartilhado, menos altura que cards individuais.
    Cada linha em `linhas` deve conter: codigo, descricao, descricao_markup, unidade, qtd_txt,
    valor_unit, valor_produtos, desconto, ipi, icms_st, total, nota_rodape.
    `readable_compact` prioriza legibilidade mantendo densidade para até ~10 itens por página.
    """
    compact = readable_compact or ultra_compact
    inline_nota = nota_na_descricao or descricao_largura_total
    p_desc = ParagraphStyle(
        'PvBtD',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=8.0 if readable_compact else (7.6 if ultra_compact else 8.4),
        leading=9.6 if readable_compact else (9.0 if ultra_compact else 10.0),
        textColor=C_HEADER_DEEP,
        alignment=TA_LEFT,
    )
    p_cod = ParagraphStyle(
        'PvBtC',
        parent=ph_small,
        fontName='Helvetica',
        fontSize=6.75 if readable_compact else (6.4 if ultra_compact else 6.8),
        leading=8.0 if readable_compact else (7.6 if ultra_compact else 8.0),
        textColor=C_MUTED,
        alignment=TA_RIGHT,
    )
    p_h = ParagraphStyle(
        'PvBtH',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=6.35 if compact else 6.2,
        leading=7.6 if readable_compact else (7.0 if ultra_compact else 7.4),
        textColor=C_MUTED,
        alignment=TA_CENTER,
    )
    p_hr = ParagraphStyle('PvBtHR', parent=p_h, alignment=TA_RIGHT)
    p_cell = ParagraphStyle(
        'PvBtN',
        parent=ph_small,
        fontSize=7.0 if readable_compact else (6.55 if ultra_compact else 6.9),
        leading=8.3 if readable_compact else (7.6 if ultra_compact else 8.0),
        textColor=C_SLATE_TEXT,
        alignment=TA_CENTER,
    )
    p_cell_r = ParagraphStyle('PvBtNR', parent=p_cell, alignment=TA_RIGHT)
    p_tot = ParagraphStyle(
        'PvBtT',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=7.35 if readable_compact else (6.8 if ultra_compact else 7.2),
        leading=8.5 if readable_compact else (7.8 if ultra_compact else 8.2),
        textColor=C_HEADER_DEEP,
        alignment=TA_RIGHT,
    )
    p_note = ParagraphStyle(
        'PvBtNote',
        parent=ph_small,
        fontSize=6.35 if readable_compact else (5.95 if ultra_compact else 6.2),
        leading=7.5 if readable_compact else (7.0 if ultra_compact else 7.4),
        textColor=C_MUTED,
        alignment=TA_LEFT,
    )

    cw = [page_w * f for f in _PV_BATCH_COL_FRACS]
    table_rows: list[list] = [
        [
            Paragraph('<b>Un.</b>', p_h),
            Paragraph('<b>Qtd.</b>', p_h),
            Paragraph('<b>Unit.</b>', p_hr),
            Paragraph('<b>Prod.</b>', p_hr),
            Paragraph('<b>Desc.</b>', p_hr),
            Paragraph('<b>IPI</b>', p_hr),
            Paragraph('<b>ST</b>', p_hr),
            Paragraph('<b>Total</b>', p_hr),
        ]
    ]
    span_cmds: list = []
    row_idx = 1
    pad_row = 2.0 if readable_compact else (1.0 if ultra_compact else 1.5)
    pad_h = 5.0 if readable_compact else (3.5 if ultra_compact else 4.0)

    for item_idx, linha in enumerate(linhas):
        desc = linha['descricao']
        nota = (linha.get('nota_rodape') or '').strip()
        if inline_nota and nota and not descricao_largura_total:
            if linha.get('descricao_markup'):
                desc_html = f'{desc}<br/><font size="6.5" color="#64748b">{escape(nota)}</font>'
            else:
                desc_html = (
                    f'<b>{escape(desc)}</b><br/>'
                    f'<font size="6.5" color="#64748b">{escape(nota)}</font>'
                )
            desc_para = Paragraph(desc_html, p_desc)
        else:
            desc_para = Paragraph(
                desc if linha.get('descricao_markup') else escape(desc),
                p_desc,
            )

        if descricao_largura_total:
            table_rows.append([desc_para, '', '', '', '', '', '', ''])
            span_cmds.append(('SPAN', (0, row_idx), (7, row_idx)))
        else:
            cod_para = Paragraph(f'Cód. {escape(linha["codigo"])}', p_cod)
            table_rows.append([desc_para, '', '', '', '', '', cod_para, ''])
            span_cmds.append(('SPAN', (0, row_idx), (5, row_idx)))
            span_cmds.append(('SPAN', (6, row_idx), (7, row_idx)))
        if item_idx:
            span_cmds.append(('LINEABOVE', (0, row_idx), (-1, row_idx), 0.18, colors.HexColor('#e8edf3')))
        row_idx += 1

        table_rows.append(
            [
                Paragraph(nobr(linha['unidade']), p_cell),
                Paragraph(nobr(linha['qtd_txt']), p_cell),
                Paragraph(format_currency_br(linha['valor_unit']), p_cell_r),
                Paragraph(format_currency_br(linha['valor_produtos']), p_cell_r),
                Paragraph(format_currency_br(linha['desconto']), p_cell_r),
                Paragraph(format_currency_br(linha['ipi']), p_cell_r),
                Paragraph(format_currency_br(linha['icms_st']), p_cell_r),
                Paragraph(format_currency_br(linha['total']), p_tot),
            ]
        )
        row_idx += 1

        if nota and not inline_nota:
            table_rows.append([Paragraph(escape(nota), p_note), '', '', '', '', '', '', ''])
            span_cmds.append(('SPAN', (0, row_idx), (7, row_idx)))
            row_idx += 1

    tbl = Table(table_rows, colWidths=cw, repeatRows=1, hAlign='LEFT')
    style_cmds = [
        ('BOX', (0, 0), (-1, -1), 0.32, C_FRAME_LIGHT),
        ('BACKGROUND', (0, 0), (-1, 0), C_TABLE_HEADER_BG),
        ('LINEABOVE', (0, 0), (-1, 0), 0.3, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 0), (-1, 0), 0.2, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), pad_row),
        ('BOTTOMPADDING', (0, 0), (-1, -1), pad_row),
        ('LEFTPADDING', (0, 0), (-1, -1), pad_h),
        ('RIGHTPADDING', (0, 0), (-1, -1), pad_h),
    ]
    style_cmds.extend(span_cmds)
    tbl.setStyle(TableStyle(style_cmds))
    return wrap_plate_full_width(tbl, page_w)


def build_item_product_card(
    *,
    codigo: str,
    descricao: str,
    unidade: str,
    qtd_txt: str,
    valor_unit,
    valor_produtos,
    desconto,
    ipi,
    icms_st,
    total,
    page_w: float,
    ph_small: ParagraphStyle,
) -> Table:
    """PdfItemCard: código em destaque, descrição legível, totais alinhados."""
    p_cod = ParagraphStyle(
        'NxItCod',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=C_HEADER_DEEP,
        alignment=TA_LEFT,
    )
    p_desc = ParagraphStyle(
        'NxItDesc',
        parent=ph_small,
        fontSize=9.5,
        leading=13,
        textColor=C_PRIMARY,
        alignment=TA_LEFT,
    )
    pst = ParagraphStyle('NxItM', parent=ph_small, fontSize=8.5, leading=11, textColor=C_SLATE_TEXT)
    pst_r = ParagraphStyle('NxItMR', parent=pst, alignment=TA_RIGHT)
    pst_c = ParagraphStyle('NxItMC', parent=pst, alignment=TA_CENTER, fontName='Helvetica-Bold')
    p_tot_lbl = ParagraphStyle('NxItTL', parent=pst, fontName='Helvetica-Bold', fontSize=9, textColor=C_HEADER_DEEP, alignment=TA_RIGHT)

    line_cod = Paragraph(f'<b>{escape(codigo)}</b>', p_cod)
    line_desc = Paragraph(escape(descricao), p_desc)

    row_mid = Table(
        [
            [
                Paragraph(f'Unidade: {nobr(unidade)}', pst_c),
                Paragraph(f'Quantidade: {nobr(qtd_txt)}', pst_c),
                Paragraph(f'Valor unitário: {format_currency_br(valor_unit)}', pst_r),
                Paragraph(f'Valor produtos: {format_currency_br(valor_produtos)}', pst_r),
            ]
        ],
        colWidths=[page_w * 0.16, page_w * 0.16, page_w * 0.32, page_w * 0.36],
    )
    row_mid.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LINEABOVE', (0, 0), (-1, 0), 0.35, colors.HexColor('#e2e8f0')),
            ]
        )
    )

    row_bot = Table(
        [
            [
                Paragraph(f'Desconto: {format_currency_br(desconto)}', pst_r),
                Paragraph(f'IPI: {format_currency_br(ipi)}', pst_r),
                Paragraph(f'ICMS ST: {format_currency_br(icms_st)}', pst_r),
                Paragraph(f'<b>Total do item: {format_currency_br(total)}</b>', p_tot_lbl),
            ]
        ],
        colWidths=[page_w * 0.24, page_w * 0.2, page_w * 0.22, page_w * 0.34],
    )
    row_bot.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]
        )
    )

    card = Table([[line_cod], [line_desc], [row_mid], [row_bot]], colWidths=[page_w])
    card.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.55, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 11),
                ('RIGHTPADDING', (0, 0), (-1, -1), 11),
            ]
        )
    )
    return card


def build_financial_summary_block(
    *,
    page_w: float,
    subtotal_produtos,
    desconto_total,
    frete,
    outras_despesas,
    ipi,
    icms_st,
    valor_total_final,
    ph_small: ParagraphStyle,
    ph_right: ParagraphStyle,
    compact: bool = False,
    ultra_compact: bool = False,
    full_width: bool = False,
) -> Table:
    """PdfFinancialSummary: bloco à direita ou largura útil total (`full_width`)."""
    if ultra_compact:
        fs, lead = 7.15, 8.6
        block_w = page_w if full_width else page_w * 0.56
        pad, pad_big = 1.9, 3.5
        fs_tot, fs_lbl = 11.0, 7.8
        w_lbl, w_val = block_w * 0.56, block_w * 0.44
    elif compact:
        fs, lead = 7.6, 9.0
        w_lbl, w_val = 48 * mm, 40 * mm
        pad, pad_big = 3.2, 5.5
        fs_tot, fs_lbl = 12.5, 8.8
    else:
        fs, lead = 9, 11
        w_lbl, w_val = 58 * mm, 50 * mm
        pad, pad_big = 5, 9
        fs_tot, fs_lbl = 14, 10
    p_tot = ParagraphStyle('TotL', parent=ph_small, fontSize=fs, leading=lead)
    p_tot_r = ParagraphStyle('TotR', parent=ph_right, fontSize=fs, leading=lead)

    def _par_lbl(txt: str) -> Paragraph:
        return Paragraph(txt, p_tot)

    def _par_val(val) -> Paragraph:
        return Paragraph(format_currency_br(val), p_tot_r)

    if ultra_compact:
        half = block_w / 2.0
        w_lbl_h, w_val_h = half * 0.56, half * 0.44
        left_rows = [
            [_par_lbl('Subtotal produtos'), _par_val(subtotal_produtos)],
            [_par_lbl('Desconto total'), _par_val(desconto_total)],
            [_par_lbl('Frete'), _par_val(frete)],
        ]
        right_rows = [
            [_par_lbl('Outras despesas'), _par_val(outras_despesas)],
            [_par_lbl('IPI'), _par_val(ipi)],
            [_par_lbl('ICMS ST'), _par_val(icms_st)],
        ]
        left_tbl = Table(left_rows, colWidths=[w_lbl_h, w_val_h])
        right_tbl = Table(right_rows, colWidths=[w_lbl_h, w_val_h])
        pair_style = TableStyle(
            [
                ('FONT', (0, 0), (-1, -1), 'Helvetica', fs),
                ('TEXTCOLOR', (0, 0), (-1, -1), C_SLATE_TEXT),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), pad),
                ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
                ('LEFTPADDING', (0, 0), (-1, -1), pad),
                ('RIGHTPADDING', (0, 0), (-1, -1), pad),
            ]
        )
        left_tbl.setStyle(pair_style)
        right_tbl.setStyle(pair_style)
        cols = Table([[left_tbl, right_tbl]], colWidths=[half, half])
        cols.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
        tot_row = Table(
            [
                [
                    Paragraph(
                        f'<b><font size="{fs_lbl}" color="#ffffff">VALOR TOTAL FINAL</font></b>',
                        ParagraphStyle('TotLF', parent=p_tot, textColor=colors.white, fontName='Helvetica-Bold'),
                    ),
                    Paragraph(
                        f'<b><font size="{fs_tot}" color="#ffffff">{format_currency_br(valor_total_final)}</font></b>',
                        ParagraphStyle(
                            'TotRF',
                            parent=p_tot_r,
                            textColor=colors.white,
                            fontName='Helvetica-Bold',
                            fontSize=fs_tot,
                        ),
                    ),
                ]
            ],
            colWidths=[block_w * 0.56, block_w * 0.44],
        )
        tot_row.setStyle(
            TableStyle(
                [
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), pad_big),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), pad_big),
                    ('LEFTPADDING', (0, 0), (-1, -1), pad + 1),
                    ('RIGHTPADDING', (0, 0), (-1, -1), pad + 1),
                    ('BACKGROUND', (0, 0), (-1, -1), C_BRAND_PRIMARY),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ]
            )
        )
        tot_inner = Table([[cols], [tot_row]], colWidths=[block_w])
        tot_inner.setStyle(
            TableStyle(
                [
                    ('BOX', (0, 0), (-1, -1), 0.5, C_FRAME_LIGHT),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.white),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ]
            )
        )
        tot_wrap = Table([[tot_inner]], colWidths=[page_w], hAlign='LEFT')
        align_wrap = 'LEFT' if full_width else 'RIGHT'
        tot_wrap.setStyle(
            TableStyle([('ALIGN', (0, 0), (-1, -1), align_wrap), ('LEFTPADDING', (0, 0), (-1, -1), 0)])
        )
        return tot_wrap

    if full_width:
        block_w = page_w
        w_lbl, w_val = block_w * 0.56, block_w * 0.44
        tot_rows = [
            [_par_lbl('Subtotal produtos'), _par_val(subtotal_produtos)],
            [_par_lbl('Desconto total'), _par_val(desconto_total)],
            [_par_lbl('Frete'), _par_val(frete)],
            [_par_lbl('Outras despesas'), _par_val(outras_despesas)],
            [_par_lbl('IPI'), _par_val(ipi)],
            [_par_lbl('ICMS ST'), _par_val(icms_st)],
            [
                Paragraph(
                    f'<b><font size="{fs_lbl}" color="#ffffff">VALOR TOTAL FINAL</font></b>',
                    ParagraphStyle('TotLF', parent=p_tot, textColor=colors.white, fontName='Helvetica-Bold'),
                ),
                Paragraph(
                    f'<b><font size="{fs_tot}" color="#ffffff">{format_currency_br(valor_total_final)}</font></b>',
                    ParagraphStyle(
                        'TotRF',
                        parent=p_tot_r,
                        textColor=colors.white,
                        fontName='Helvetica-Bold',
                        fontSize=fs_tot,
                    ),
                ),
            ],
        ]
        tot_inner = Table(tot_rows, colWidths=[w_lbl, w_val], hAlign='LEFT')
        tot_inner.setStyle(
            TableStyle(
                [
                    ('FONT', (0, 0), (-1, -2), 'Helvetica', fs),
                    ('TEXTCOLOR', (0, 0), (-1, -2), C_SLATE_TEXT),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -2), pad),
                    ('BOTTOMPADDING', (0, 0), (-1, -2), pad),
                    ('TOPPADDING', (0, -1), (-1, -1), pad_big),
                    ('BOTTOMPADDING', (0, -1), (-1, -1), pad_big),
                    ('LEFTPADDING', (0, 0), (-1, -1), pad + 1),
                    ('RIGHTPADDING', (0, 0), (-1, -1), pad + 1),
                    ('BOX', (0, 0), (-1, -1), 0.5, C_FRAME_LIGHT),
                    ('BACKGROUND', (0, 0), (-1, -2), colors.white),
                    ('BACKGROUND', (0, -1), (-1, -1), C_BRAND_PRIMARY),
                    ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
                    ('LINEABOVE', (0, -1), (-1, -1), 0.5, colors.white),
                ]
            )
        )
        return wrap_plate_full_width(tot_inner, page_w)

    tot_rows = [
        [Paragraph('Subtotal produtos', p_tot), Paragraph(format_currency_br(subtotal_produtos), p_tot_r)],
        [Paragraph('Desconto total', p_tot), Paragraph(format_currency_br(desconto_total), p_tot_r)],
        [Paragraph('Frete', p_tot), Paragraph(format_currency_br(frete), p_tot_r)],
        [Paragraph('Outras despesas', p_tot), Paragraph(format_currency_br(outras_despesas), p_tot_r)],
        [Paragraph('IPI', p_tot), Paragraph(format_currency_br(ipi), p_tot_r)],
        [Paragraph('ICMS ST', p_tot), Paragraph(format_currency_br(icms_st), p_tot_r)],
        [
            Paragraph(
                f'<b><font size="{fs_lbl}" color="#ffffff">VALOR TOTAL FINAL</font></b>',
                ParagraphStyle('TotLF', parent=p_tot, textColor=colors.white, fontName='Helvetica-Bold'),
            ),
            Paragraph(
                f'<b><font size="{fs_tot}" color="#ffffff">{format_currency_br(valor_total_final)}</font></b>',
                ParagraphStyle(
                    'TotRF',
                    parent=p_tot_r,
                    textColor=colors.white,
                    fontName='Helvetica-Bold',
                    fontSize=fs_tot,
                ),
            ),
        ],
    ]
    tot_inner = Table(tot_rows, colWidths=[w_lbl, w_val])
    tot_inner.setStyle(
        TableStyle(
            [
                ('FONT', (0, 0), (-1, -2), 'Helvetica', fs),
                ('TEXTCOLOR', (0, 0), (-1, -2), C_SLATE_TEXT),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -2), pad),
                ('BOTTOMPADDING', (0, 0), (-1, -2), pad),
                ('TOPPADDING', (0, -1), (-1, -1), pad_big),
                ('BOTTOMPADDING', (0, -1), (-1, -1), pad_big),
                ('LEFTPADDING', (0, 0), (-1, -1), pad + 1),
                ('RIGHTPADDING', (0, 0), (-1, -1), pad + 1),
                ('BOX', (0, 0), (-1, -1), 0.5, C_FRAME_LIGHT),
                ('BACKGROUND', (0, 0), (-1, -2), colors.white),
                ('BACKGROUND', (0, -1), (-1, -1), C_BRAND_PRIMARY),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
                ('LINEABOVE', (0, -1), (-1, -1), 0.5, colors.white),
            ]
        )
    )
    tot_wrap = Table([[tot_inner]], colWidths=[page_w], hAlign='RIGHT')
    tot_wrap.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'RIGHT'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    return tot_wrap


def build_financial_summary_section(
    *,
    page_w: float,
    subtotal_produtos,
    desconto_total,
    frete,
    outras_despesas,
    ipi,
    icms_st,
    valor_total_final,
    ph_small: ParagraphStyle,
    ph_right: ParagraphStyle,
    compact: bool = True,
    tight: bool = False,
    ultra_compact: bool = False,
    full_width: bool = False,
) -> list:
    """Título + resumo financeiro (reutilizável em pedidos / propostas)."""
    tbl = build_financial_summary_block(
        page_w=page_w,
        subtotal_produtos=subtotal_produtos,
        desconto_total=desconto_total,
        frete=frete,
        outras_despesas=outras_despesas,
        ipi=ipi,
        icms_st=icms_st,
        valor_total_final=valor_total_final,
        ph_small=ph_small,
        ph_right=ph_right,
        compact=compact and not ultra_compact,
        ultra_compact=ultra_compact,
        full_width=full_width,
    )
    if ultra_compact:
        sp = 0.25 * mm
    elif tight:
        sp = 0.35 * mm
    else:
        sp = 0.65 * mm
    return [
        build_section_title('Resumo financeiro', ph_small=ph_small, compact=True, page_w=page_w),
        Spacer(1, sp),
        tbl,
    ]


def build_supplier_instructions_block(
    *,
    page_w: float,
    ph_small: ParagraphStyle,
    title: str = 'Instruções ao fornecedor',
    lines: tuple[str, ...] | None = None,
) -> list:
    """Texto fixo reutilizável; `lines` opcional substitui o padrão."""
    use_lines = lines if lines is not None else _DEFAULT_SUPPLIER_INSTRUCTIONS
    p_item = ParagraphStyle('NxInst', parent=ph_small, fontSize=8.8, leading=12.5, textColor=C_SLATE_TEXT, leftIndent=8)
    bullets = [Paragraph(f'• {escape(line)}', p_item) for line in use_lines]
    inner = Table([[b] for b in bullets], colWidths=[page_w - 4 * mm])
    inner.setStyle(
        TableStyle(
            [
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ]
        )
    )
    box = Table([[inner]], colWidths=[page_w])
    box.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [build_section_title(title, ph_small=ph_small, page_w=page_w), Spacer(1, 2 * mm), box]


def build_supplier_instructions_compact(
    *,
    page_w: float,
    ph_small: ParagraphStyle,
    title: str = 'Instruções ao fornecedor',
    lines: tuple[str, ...] | None = None,
) -> list:
    """Versão densa: parágrafo único (menos altura que lista com bullets)."""
    use_lines = lines if lines is not None else _DEFAULT_SUPPLIER_INSTRUCTIONS
    merged = ' '.join(s.strip() for s in use_lines if s.strip())
    p = ParagraphStyle(
        'NxInstC',
        parent=ph_small,
        fontSize=6.5,
        leading=8.4,
        textColor=C_SLATE_TEXT,
    )
    body = Paragraph(f'<b>{escape(title)}:</b> {escape(merged)}', p)
    tbl = Table([[body]], colWidths=[page_w - 2 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.32, C_FRAME_LIGHT),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('TOPPADDING', (0, 0), (-1, -1), 3.2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3.2),
                ('LEFTPADDING', (0, 0), (-1, -1), 4.5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4.5),
            ]
        )
    )
    return [Spacer(1, 0.35 * mm), tbl]


def build_observations_block_commercial(
    *,
    texto: str | None,
    page_w: float,
    ph_small: ParagraphStyle,
    compact_empty: bool = True,
) -> list:
    """PdfObservationsBlock: sempre exibe; texto vazio vira '—'."""
    raw_stripped = (texto or '').strip()
    is_empty = not raw_stripped
    raw = raw_stripped or '—'
    if is_empty and compact_empty:
        p_body = ParagraphStyle('NxObs', parent=ph_small, fontSize=6.8, leading=8.2, textColor=C_SLATE_TEXT)
        pad = 2.5
        line = Paragraph(f'<b>Observações comerciais:</b> {escape(raw)}', p_body)
        tbl = Table([[line]], colWidths=[page_w - 2 * mm])
        tbl.setStyle(
            TableStyle(
                [
                    ('BOX', (0, 0), (-1, -1), 0.32, C_FRAME_LIGHT),
                    ('TOPPADDING', (0, 0), (-1, -1), pad),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
                    ('LEFTPADDING', (0, 0), (-1, -1), pad + 1),
                    ('RIGHTPADDING', (0, 0), (-1, -1), pad + 1),
                ]
            )
        )
        return [Spacer(1, 0.45 * mm), tbl]

    p_body = ParagraphStyle('NxObs', parent=ph_small, fontSize=8.2, leading=10.2, textColor=C_SLATE_TEXT)
    pad = 6
    sp_after_title = SPACE_XS
    line = Paragraph(f'<b>Observações:</b> {escape(raw)}', p_body)
    tbl = Table([[line]], colWidths=[page_w - 2 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
                ('TOPPADDING', (0, 0), (-1, -1), pad),
                ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
                ('LEFTPADDING', (0, 0), (-1, -1), pad + 1),
                ('RIGHTPADDING', (0, 0), (-1, -1), pad + 1),
            ]
        )
    )
    return [
        build_section_title('Observações comerciais', ph_small=ph_small, compact=True, page_w=page_w),
        Spacer(1, sp_after_title),
        tbl,
    ]
