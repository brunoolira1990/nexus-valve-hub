"""Paleta institucional + estilos de parágrafo base para PDFs (ReportLab)."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm

# Paleta institucional (tokens de cor reutilizáveis)
C_PRIMARY = colors.HexColor('#0f172a')
# Faixa escura legada (ex.: cabeçalhos antigos em PDF); comerciais preferem cartão claro + acentos.
C_HEADER_BG = colors.HexColor('#0f2847')
C_HEADER_DEEP = colors.HexColor('#0a1628')
C_HEADER_FG = colors.white
C_BORDER = colors.HexColor('#e2e8f0')
C_MUTED = colors.HexColor('#64748b')
C_LABEL_BG = colors.HexColor('#f1f5f9')
# Alinhado ao certificado de qualidade (`apps.qualidade.certificado_pdf`) — títulos de secção / linhas de rótulo.
C_TABLE_HEADER_BG = colors.HexColor('#E8EEF5')
# Azul institucional do certificado (`brand_primary`) — acentos (nº documento, totais).
C_BRAND_PRIMARY = colors.HexColor('#0F5EDB')
# Acento laranja marca (pontual; evitar preenchimentos amplos).
C_BRAND_ACCENT_ORANGE = colors.HexColor('#EA580C')
# Contorno de documento comercial em fundo branco (mais leve que a grelha densa do certificado A4 paisagem).
C_DOC_FRAME = colors.HexColor('#94a3b8')
# Moldura muito suave (cartão branco — alinhado ao certificado, sem peso no topo).
C_FRAME_LIGHT = colors.HexColor('#dce3eb')
C_ROW_ALT = colors.HexColor('#f8fafc')
C_CARD_BG = colors.HexColor('#fafbfc')
C_BADGE_BG = colors.HexColor('#dbeafe')
C_BADGE_FG = colors.HexColor('#1e40af')
C_SLATE_TEXT = colors.HexColor('#334155')

# Aliases semânticos (documentos comerciais)
COLOR_NAVY = C_HEADER_DEEP
COLOR_BLUE = C_BADGE_FG
COLOR_BORDER = C_BORDER
COLOR_MUTED = C_MUTED

# Tipografia PDF (pt)
FONT_PDF_TITLE = 12.5
FONT_PDF_SECTION = 9.0
FONT_PDF_BODY = 8.5
FONT_PDF_SMALL = 7.4

# Espaçamento vertical (ReportLab usa pontos; mm converte de forma consistente)
SPACE_XS = 1.0 * mm
SPACE_SM = 2.0 * mm
SPACE_MD = 3.0 * mm


def base_paragraph_styles():
    """Helvetica, corpo denso mas legível para A4 comercial (pedidos, propostas)."""
    styles = getSampleStyleSheet()
    ph = ParagraphStyle(
        name='NxPh',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=FONT_PDF_BODY,
        leading=11,
        textColor=C_PRIMARY,
        alignment=TA_LEFT,
    )
    ph_small = ParagraphStyle('NxSm', parent=ph, fontSize=FONT_PDF_SMALL + 0.2, leading=10, textColor=C_PRIMARY)
    ph_right = ParagraphStyle('NxPhR', parent=ph, alignment=TA_RIGHT)
    ph_center = ParagraphStyle('NxPhC', parent=ph, alignment=TA_CENTER, fontSize=FONT_PDF_BODY, leading=11)
    ph_white = ParagraphStyle(
        name='NxWh',
        parent=ph,
        textColor=colors.white,
        fontName='Helvetica',
        fontSize=FONT_PDF_BODY,
        leading=11,
    )
    return ph, ph_small, ph_right, ph_center, ph_white
