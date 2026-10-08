import io
import logging
from datetime import date, datetime
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.cadastros.models import Empresa
from apps.core.pdf.styles import (
    C_BRAND_PRIMARY,
    C_CARD_BG,
    C_DOC_FRAME,
    C_FRAME_LIGHT,
    C_MUTED,
    C_PRIMARY,
    C_ROW_ALT,
    C_SLATE_TEXT,
    C_TABLE_HEADER_BG,
    FONT_PDF_SECTION,
    FONT_PDF_SMALL,
)
from apps.fiscal.models import NFeSaida
from apps.qualidade.models import CertificadoQualidade

logger = logging.getLogger(__name__)

# Paleta alinhada a apps.core.pdf.styles (identidade Nexus); chaves extras só para PDF de certificado.
PDF_THEME = {
    'brand_dark': C_PRIMARY,
    'brand_primary': C_BRAND_PRIMARY,
    'table_header_bg': C_TABLE_HEADER_BG,
    'border': C_DOC_FRAME,
    'border_frame': C_FRAME_LIGHT,
    'text': C_PRIMARY,
    'muted': C_MUTED,
    'white': colors.white,
    'card_bg': C_CARD_BG,
    'row_alt': C_ROW_ALT,
    # Rascunho/prévia: marca d'água em tom institucional (azul), sem alterar o texto "PRÉVIA / RASCUNHO".
    'draft_watermark': colors.Color(15 / 255, 94 / 255, 219 / 255, alpha=0.078),
    'draft_text': C_BRAND_PRIMARY,
    'cancel_watermark': colors.Color(0.55, 0.06, 0.06, alpha=0.095),
    'cancel_text': colors.HexColor('#991B1B'),
    'section_title_size': FONT_PDF_SECTION - 0.4,
    'header_main_size': 9.4,
    'header_sub_size': 7.8,
    'header_right_title_size': 12,
    'header_right_number_size': 10,
    'body_size': FONT_PDF_SMALL,
    'footer_size': FONT_PDF_SMALL - 0.2,
}
PDF_TEMPLATE_VERSION = 'certificado-qualidade-v3-visual-nexus'

NEXUS_HEADER_FALLBACK = {
    'razao': 'NEXUS VALVULAS E CONEXOES INDUSTRIAIS LTDA',
    'cnpj': '03.999.102/0001-50',
    'ie': '152.451.500.118',
    'tel': '(11) 4240-8832',
    'endereco': 'R MIGUEL LANGONE, 341 - Cep: 08215-330 - ITAQUERA - SAO PAULO - SP',
    'site': 'www.nexusvalvulas.com.br',
    'email': 'nexus@nexusvalvulas.com.br',
}

COMPOSICAO_COLS = ['C', 'Mn', 'P', 'S', 'Si', 'Ni', 'Cr', 'Mo', 'Cu', 'V', 'Nb', 'Al', 'Ti', 'N', 'Zn', 'Fe', 'Sn', 'Pb', 'Ca', 'Ta', 'W', 'Li', 'Co']
IMPACTO_COLS = ['norma', 'corpo_prova', 'direcao', 'posicao', 'temperatura', 'corpo_prova_a', 'corpo_prova_b', 'corpo_prova_c', 'media']


def gerar_certificado_pdf(nf: NFeSaida) -> ContentFile:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4
    y = height - 50
    c.setFont('Helvetica-Bold', 14)
    c.drawString(50, y, 'Certificado de conformidade')
    y -= 28
    c.setFont('Helvetica', 10)
    c.drawString(50, y, f'NF Saída: {nf.numero}')
    y -= 16
    c.drawString(50, y, f'Cliente: {nf.cliente.razao_social}')
    y -= 16
    c.drawString(50, y, f'Data: {nf.data.isoformat()}')
    y -= 28
    c.drawString(50, y, 'Itens e corridas:')
    y -= 16
    for it in nf.itens.select_related('produto', 'corrida').all():
        linha = (
            f'{it.produto.codigo_completo} — Qtd {it.quantidade} — '
            f'Corrida: {it.corrida.numero if it.corrida_id else "-"}'
        )
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont('Helvetica', 10)
        c.drawString(50, y, linha[:120])
        y -= 14
    c.save()
    buffer.seek(0)
    nome = f'certificado_nf_{nf.id}_{nf.numero.replace("/", "-")}.pdf'
    return ContentFile(buffer.read(), name=nome)


def _draw_table(c: canvas.Canvas, data: list[list[str]], x: float, y_top: float, col_widths: list[float], row_h: float = 5.9 * mm):
    t = Table(data, colWidths=col_widths, rowHeights=[row_h] * len(data))
    t.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.28, PDF_THEME['border']),
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 7.1),
                ('FONT', (0, 1), (-1, -1), 'Helvetica', PDF_THEME['body_size']),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BACKGROUND', (0, 0), (-1, 0), PDF_THEME['table_header_bg']),
                ('LINEBELOW', (0, 0), (-1, 0), 0.85, PDF_THEME['brand_primary']),
                ('TEXTCOLOR', (0, 0), (-1, -1), PDF_THEME['text']),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PDF_THEME['row_alt']]),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ],
        ),
    )
    w, h = t.wrapOn(c, 0, 0)
    t.drawOn(c, x, y_top - h)
    return y_top - h - 2 * mm


def _fmt_value(v: object) -> str:
    if v in (None, '', {}):
        return ''
    if isinstance(v, (float, Decimal)):
        return str(v).replace('.', ',')
    return str(v)


def _digits_only(value: object) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _format_cnpj(value: object) -> str:
    digits = _digits_only(value)
    if not digits:
        return '—'
    if len(digits) == 14:
        return f'{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}'
    return str(value or '').strip() or '—'


def _format_ie(value: object) -> str:
    raw = str(value or '').strip()
    digits = _digits_only(raw)
    if not digits:
        return '—'
    if len(digits) == 12:
        return f'{digits[0:3]}.{digits[3:6]}.{digits[6:9]}.{digits[9:12]}'
    return raw


def _format_date_br(value: object) -> str:
    if value in (None, ''):
        return '—'
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y')
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    txt = str(value).strip()
    if not txt:
        return '—'
    if 'T' in txt:
        txt = txt.split('T', 1)[0]
    try:
        parsed = date.fromisoformat(txt)
        return parsed.strftime('%d/%m/%Y')
    except Exception:
        return txt if '/' in txt else '—'


def _resolve_cert_issue_date(cert: CertificadoQualidade) -> object:
    if cert.nota_fiscal_id and cert.nota_fiscal and getattr(cert.nota_fiscal, 'data', None):
        return cert.nota_fiscal.data
    if cert.nota_fiscal_historica_id and cert.nota_fiscal_historica and getattr(cert.nota_fiscal_historica, 'dh_emissao', None):
        return cert.nota_fiscal_historica.dh_emissao
    return cert.data_emissao


def _resolve_company_entity(cert: CertificadoQualidade) -> tuple[Empresa | None, dict[str, str]]:
    diag: dict[str, str] = {'origem_empresa': 'nenhuma', 'motivo_fallback_logo': ''}
    empresa = None

    if cert.nota_fiscal_id and cert.nota_fiscal:
        if cert.nota_fiscal.pedido_venda_id and cert.nota_fiscal.pedido_venda and cert.nota_fiscal.pedido_venda.empresa_emitente_id:
            empresa = cert.nota_fiscal.pedido_venda.empresa_emitente
            diag['origem_empresa'] = 'nf_saida.pedido_venda.empresa_emitente'
        elif getattr(cert.nota_fiscal, 'empresa_emitente_id', None):
            empresa = cert.nota_fiscal.empresa_emitente
            diag['origem_empresa'] = 'nf_saida.empresa_emitente'

    if not empresa and cert.nota_fiscal_historica_id and cert.nota_fiscal_historica and cert.nota_fiscal_historica.empresa_emitente_id:
        empresa = cert.nota_fiscal_historica.empresa_emitente
        diag['origem_empresa'] = 'nf_saida_historica.empresa_emitente'

    if not empresa:
        empresa = Empresa.objects.exclude(logotipo='').exclude(logotipo__isnull=True).order_by('id').first()
        if empresa:
            diag['origem_empresa'] = 'empresa_padrao_com_logo'
        else:
            empresa = Empresa.objects.order_by('id').first()
            diag['origem_empresa'] = 'empresa_padrao_primeira'

    if not empresa:
        diag['motivo_fallback_logo'] = 'empresa nao encontrada'
    return empresa, diag


def _resolve_company_header(cert: CertificadoQualidade) -> dict[str, str]:
    empresa, diag = _resolve_company_entity(cert)

    def pick(field: str, fallback: str) -> str:
        if not empresa:
            return fallback
        val = getattr(empresa, field, None)
        if val is None:
            return fallback
        txt = str(val).strip()
        return txt or fallback

    endereco = NEXUS_HEADER_FALLBACK['endereco']
    if empresa:
        endereco = (
            f"{pick('logradouro', '')}, {pick('numero', '')}"
            f"{(' - ' + pick('complemento', '')) if str(getattr(empresa, 'complemento', '')).strip() else ''}"
            f" - Cep: {pick('cep', '')} - {pick('bairro', '')} - {pick('cidade', '')} - {pick('uf', '')}"
        ).strip()
        if not endereco or endereco.startswith(','):
            endereco = NEXUS_HEADER_FALLBACK['endereco']

    logo_name = str(empresa.logotipo.name) if empresa and getattr(empresa, 'logotipo', None) else ''
    if not logo_name and not diag.get('motivo_fallback_logo'):
        diag['motivo_fallback_logo'] = 'campo logotipo vazio'

    return {
        'razao': pick('razao_social', NEXUS_HEADER_FALLBACK['razao']),
        'cnpj': _format_cnpj(pick('cnpj', NEXUS_HEADER_FALLBACK['cnpj'])),
        'ie': _format_ie(pick('ie', NEXUS_HEADER_FALLBACK['ie'])),
        'tel': pick('telefone', NEXUS_HEADER_FALLBACK['tel']),
        'endereco': endereco,
        'site': pick('site', NEXUS_HEADER_FALLBACK['site']),
        'email': pick('email', NEXUS_HEADER_FALLBACK['email']),
        'logo_name': logo_name,
        'empresa_id': str(empresa.id) if empresa else '',
        'origem_empresa': diag.get('origem_empresa', ''),
        'motivo_fallback_logo': diag.get('motivo_fallback_logo', ''),
    }


def _item_sources(cert: CertificadoQualidade):
    rows = []
    for it in cert.itens.filter(incluir_no_certificado=True).all():
        if it.tipo_dados_tecnicos == 'VALVULA_COMPONENTES':
            comps = it.componentes.filter(ativo=True).all()
            if comps:
                for cp in comps:
                    rows.append(
                        {
                            'item': it,
                            'componente': cp.nome_componente or '',
                            'quantidade': cp.quantidade if cp.quantidade is not None else it.quantidade,
                            'norma': cp.norma or it.norma,
                            'corrida': cp.corrida or it.corrida,
                            'composicao': cp.composicao_json or {},
                            'tracao': cp.ensaio_tracao_json or {},
                            'impacto': cp.ensaio_impacto_json or {},
                        }
                    )
                    continue
        rows.append(
            {
                'item': it,
                'componente': '',
                'quantidade': it.quantidade,
                'norma': it.norma,
                'corrida': it.corrida,
                'composicao': it.composicao_json or {},
                'tracao': it.ensaio_tracao_json or {},
                'impacto': it.ensaio_impacto_json or {},
            }
        )
    return rows


def _draw_section_title(c: canvas.Canvas, text: str, x: float, y: float, w: float):
    c.setFillColor(PDF_THEME['table_header_bg'])
    c.rect(x, y - 5.8 * mm, w, 5.8 * mm, fill=1, stroke=0)
    c.setStrokeColor(PDF_THEME['brand_primary'])
    c.setLineWidth(0.85)
    c.line(x, y - 5.8 * mm, x + w, y - 5.8 * mm)
    c.setFillColor(PDF_THEME['brand_dark'])
    c.setFont('Helvetica-Bold', PDF_THEME['section_title_size'])
    c.drawString(x + 2 * mm, y - 4.1 * mm, text)
    c.setFillColor(PDF_THEME['text'])


def _draw_header_block(c: canvas.Canvas, cert: CertificadoQualidade, width: float, height: float):
    company = _resolve_company_header(cert)
    left = 7 * mm
    right = width - 7 * mm
    top = height - 7 * mm
    total_w = right - left
    h = 42 * mm
    c.setStrokeColor(PDF_THEME['border'])
    c.setLineWidth(0.55)
    c.rect(left, top - h, total_w, h, stroke=1, fill=0)

    inner_pad = 2.2 * mm
    logo_w = 50 * mm
    logo_x = left + inner_pad
    logo_box_y = top - h + inner_pad
    logo_box_w = logo_w - (inner_pad * 0.9)
    logo_box_h = h - (inner_pad * 2)
    logo_name = company.get('logo_name') or ''
    logo_drawn = False
    if logo_name:
        try:
            if not default_storage.exists(logo_name):
                company['motivo_fallback_logo'] = f'arquivo nao existe no storage: {logo_name}'
            else:
                with default_storage.open(logo_name, 'rb') as fh:
                    img = ImageReader(fh)
                    iw, ih = img.getSize()
                    if iw > 0 and ih > 0:
                        ratio = min(logo_box_w / iw, logo_box_h / ih)
                        dw, dh = iw * ratio, ih * ratio
                        dx = logo_x + (logo_box_w - dw) / 2
                        dy = logo_box_y + (logo_box_h - dh) / 2
                        c.drawImage(img, dx, dy, dw, dh, preserveAspectRatio=True, mask='auto')
                        logo_drawn = True
                    else:
                        company['motivo_fallback_logo'] = 'imagem invalida (dimensao zero)'
        except Exception as exc:
            company['motivo_fallback_logo'] = f'erro ao abrir imagem: {exc}'
            logo_drawn = False
    if not logo_drawn:
        logger.info(
            'Fallback logo certificado=%s empresa_id=%s origem=%s logo_name=%s motivo=%s',
            cert.id,
            company.get('empresa_id') or '-',
            company.get('origem_empresa') or '-',
            logo_name or '-',
            company.get('motivo_fallback_logo') or 'logo nao renderizado',
        )
    if not logo_drawn:
        c.setFillColor(PDF_THEME['brand_dark'])
        c.rect(logo_x, logo_box_y, logo_box_w, logo_box_h, fill=1, stroke=0)
        c.setFillColor(PDF_THEME['white'])
        c.setFont('Helvetica-Bold', 9)
        c.drawCentredString(left + logo_w / 2, top - h / 2 + 2 * mm, 'NEXUS APP')
        c.setFillColor(PDF_THEME['text'])

    info_x = left + logo_w + 4.0 * mm
    info_top = top - 6.8 * mm
    line_h = 4.95 * mm
    c.setFont('Helvetica-Bold', 10.6)
    c.setFillColor(PDF_THEME['brand_dark'])
    c.drawString(info_x, info_top, company['razao'][:86])
    c.setFont('Helvetica', 7.8)
    c.setFillColor(PDF_THEME['muted'])
    c.drawString(info_x, info_top - line_h, f"TEL.: {company['tel']}")
    c.drawString(info_x, info_top - (line_h * 2), company['endereco'][:96])
    c.drawString(info_x, info_top - (line_h * 3), f"CNPJ: {company['cnpj']}   I.E: {company['ie']}")
    c.drawString(info_x, info_top - (line_h * 4), f"{company['site']}   {company['email']}")
    c.setFillColor(PDF_THEME['text'])

    cert_w = 67 * mm
    cert_x = right - cert_w - inner_pad
    cert_inner_h = h - (inner_pad * 2)
    cert_inner_y = top - h + inner_pad
    c.setFillColor(PDF_THEME['table_header_bg'])
    c.rect(cert_x, cert_inner_y, cert_w, cert_inner_h, stroke=0, fill=1)
    c.setStrokeColor(PDF_THEME['border_frame'])
    c.setLineWidth(0.55)
    c.rect(cert_x, cert_inner_y, cert_w, cert_inner_h, stroke=1, fill=0)
    c.setFillColor(PDF_THEME['brand_dark'])
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(cert_x + (cert_w / 2), top - 11.2 * mm, 'CERTIFICADO')
    c.drawCentredString(cert_x + (cert_w / 2), top - 18.3 * mm, 'DE QUALIDADE')
    c.setFillColor(PDF_THEME['brand_primary'])
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(cert_x + (cert_w / 2), top - 30.4 * mm, f"Nº {cert.numero_formatado if cert.numero else 'RASCUNHO'}")
    c.setFillColor(PDF_THEME['text'])
    return top - h - 1.5 * mm


def gerar_certificado_qualidade_pdf(cert: CertificadoQualidade, preview: bool = False) -> bytes:
    logger.info(
        'PDF Certificado Qualidade gerado template=%s cert_id=%s preview=%s status=%s',
        PDF_TEMPLATE_VERSION,
        cert.id,
        preview,
        cert.status,
    )
    MAX_ITENS_COMUNS_POR_PAGINA = 5
    MAX_COMPONENTES_VALVULA_POR_BLOCO = 8

    def _chunks(seq, size: int):
        for i in range(0, len(seq), size):
            yield seq[i:i + size]

    buf = io.BytesIO()
    width, height = landscape(A4)
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=7 * mm,
        rightMargin=7 * mm,
        topMargin=52 * mm,
        bottomMargin=19 * mm,
        title=f'Certificado de Qualidade {cert.numero_formatado or cert.numero or cert.id}',
        author='NEXUS APP',
    )
    footer_text = cert.texto_padrao or (
        'Os certificados originais encontram-se em nosso poder, à sua disposição, certificamos que o(s) produto(s) '
        'supra está(ão) aprovado(s), de acordo com as especificações acima mencionadas. '
        'Documento impresso eletronicamente, dispensa assinatura. '
        'Certificado referente somente aos itens relacionados neste documento.'
    )

    def section_title(text: str) -> Table:
        t = Table([[str(text or '').upper()]], colWidths=[doc.width], rowHeights=[5.8 * mm])
        t.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), PDF_THEME['table_header_bg']),
                    ('TEXTCOLOR', (0, 0), (-1, -1), PDF_THEME['brand_dark']),
                    ('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', PDF_THEME['section_title_size']),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
                    ('TOPPADDING', (0, 0), (-1, -1), 1.3 * mm),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0.8 * mm),
                    ('LINEBELOW', (0, 0), (-1, 0), 1.0, PDF_THEME['brand_primary']),
                ]
            )
        )
        return t

    def data_table(data: list[list[str]], col_widths: list[float], row_h: float) -> Table:
        rows = [row_h] * len(data)
        t = Table(data, colWidths=col_widths, rowHeights=rows, repeatRows=1 if len(data) > 1 else 0)
        t.setStyle(
            TableStyle(
                [
                    ('GRID', (0, 0), (-1, -1), 0.28, PDF_THEME['border']),
                    ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 7.1),
                    ('FONT', (0, 1), (-1, -1), 'Helvetica', PDF_THEME['body_size']),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('BACKGROUND', (0, 0), (-1, 0), PDF_THEME['table_header_bg']),
                    ('LINEBELOW', (0, 0), (-1, 0), 0.85, PDF_THEME['brand_primary']),
                    ('TEXTCOLOR', (0, 0), (-1, -1), PDF_THEME['text']),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PDF_THEME['row_alt']]),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ],
            ),
        )
        return t

    def draw_page_frame(canv: canvas.Canvas, total_pages: int) -> None:
        _draw_header_block(canv, cert, width, height)
        if cert.status == CertificadoQualidade.Status.CANCELADO:
            canv.saveState()
            canv.setFillColor(PDF_THEME['cancel_watermark'])
            canv.setFont('Helvetica-Bold', 26)
            canv.translate(width / 2, height / 2)
            canv.rotate(28)
            canv.drawCentredString(0, 0, 'CANCELADO')
            canv.restoreState()
            canv.setFont('Helvetica', 6.8)
            canv.setFillColor(PDF_THEME['cancel_text'])
            canv.drawString(
                7 * mm,
                2.6 * mm,
                'Documento cancelado — sem valor comercial. Mantido apenas para rastreabilidade.',
            )
            canv.setFillColor(PDF_THEME['text'])
        elif preview or cert.status == CertificadoQualidade.Status.RASCUNHO:
            canv.saveState()
            canv.setFillColor(PDF_THEME['draft_watermark'])
            canv.setFont('Helvetica-Bold', 22)
            canv.translate(width / 2, height / 2)
            canv.rotate(28)
            canv.drawCentredString(0, 0, 'PRÉVIA / RASCUNHO')
            canv.restoreState()
            canv.setFont('Helvetica', 6.75)
            canv.setFillColor(PDF_THEME['draft_text'])
            canv.drawString(7 * mm, 2.6 * mm, 'Prévia sem valor de emissão final')
            canv.setFillColor(PDF_THEME['text'])
        canv.setStrokeColor(PDF_THEME['border_frame'])
        canv.setLineWidth(0.45)
        footer_y = 6 * mm
        footer_h = 10 * mm
        canv.setFillColor(PDF_THEME['card_bg'])
        canv.setStrokeColor(PDF_THEME['border_frame'])
        canv.setLineWidth(0.45)
        canv.rect(7 * mm, footer_y, width - 14 * mm, footer_h, stroke=1, fill=1)
        footer_style = ParagraphStyle(
            'footer',
            fontName='Helvetica',
            fontSize=PDF_THEME['footer_size'],
            leading=PDF_THEME['footer_size'] + 1.2,
            textColor=PDF_THEME['text'],
        )
        footer_p = Paragraph(footer_text.replace('\n', '<br/>'), footer_style)
        f_w = width - 20 * mm
        _, fh = footer_p.wrap(f_w, 8.2 * mm)
        footer_p.drawOn(canv, 10 * mm, footer_y + footer_h - fh - 1.0 * mm)
        canv.setFont('Helvetica', PDF_THEME['footer_size'])
        canv.setFillColor(C_SLATE_TEXT)
        canv.drawRightString(width - 9 * mm, footer_y + footer_h + 1.4 * mm, f'Página {canv.getPageNumber()} de {total_pages}')
        canv.setFillColor(PDF_THEME['text'])

    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            # ReportLab/Platypus finalizes pages via showPage before save().
            total_pages = len(self._saved_page_states)
            for page_idx, state in enumerate(self._saved_page_states, start=1):
                self.__dict__.update(state)
                self._pageNumber = page_idx
                draw_page_frame(self, total_pages)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

    story = []
    data_certificado = _format_date_br(_resolve_cert_issue_date(cert))
    itens_cert = list(cert.itens.filter(incluir_no_certificado=True).all())
    itens_comuns = [it for it in itens_cert if it.tipo_dados_tecnicos != 'VALVULA_COMPONENTES']
    itens_valvula = [it for it in itens_cert if it.tipo_dados_tecnicos == 'VALVULA_COMPONENTES']

    def comercial_flowables() -> list:
        comercial_data = [[
            f'Cliente: {cert.cliente_nome_snapshot or "-"}',
            f'Pedido Cliente: {cert.pedido_cliente or "-"}',
            f'Nota Fiscal: {cert.nota_fiscal_numero or "-"}',
            f'Data: {data_certificado}',
        ]]
        return [
            section_title('DADOS COMERCIAIS'),
            data_table(comercial_data, [110 * mm, 68 * mm, 54 * mm, 43 * mm], row_h=7.8 * mm),
            Spacer(1, 2 * mm),
        ]

    def item_row(item):
        return {
            'item': item,
            'quantidade': item.quantidade,
            'corrida': item.corrida,
            'norma': item.norma,
            'composicao': item.composicao_json or {},
            'tracao': item.ensaio_tracao_json or {},
            'impacto': item.ensaio_impacto_json or {},
        }

    def build_common_block_flow(bloco: list[dict]) -> list:
        bloco_flow = []
        bloco_flow.extend(comercial_flowables())

        itens_data = [['Item', 'Corrida', 'Código Produto', 'Quantidade', 'Descrição do Material', 'Norma']]
        for r in bloco:
            it = r['item']
            itens_data.append([str(it.ordem), it.corrida or '—', it.codigo_produto or '—', _fmt_value(it.quantidade), (it.descricao_material or '—')[:78], it.norma or '—'])
        bloco_flow.append(section_title('ITENS'))
        bloco_flow.append(data_table(itens_data, [12 * mm, 24 * mm, 38 * mm, 20 * mm, 128 * mm, 62 * mm], row_h=7.5 * mm))
        bloco_flow.append(Spacer(1, 1.8 * mm))

        comp_data = [['Item', 'QTD'] + COMPOSICAO_COLS]
        for r in bloco:
            mapa = r['composicao'] if isinstance(r['composicao'], dict) else {}
            row = [str(r['item'].ordem), _fmt_value(r['quantidade'])]
            row.extend([_fmt_value(mapa.get(k)) for k in COMPOSICAO_COLS])
            comp_data.append(row)
        bloco_flow.append(section_title('Composição Química (%) / Chemical Composition (%)'))
        bloco_flow.append(data_table(comp_data, [8 * mm, 10 * mm] + [9.2 * mm] * len(COMPOSICAO_COLS), row_h=5.9 * mm))
        bloco_flow.append(Spacer(1, 1.8 * mm))

        tracao_data = [[
            'Item', 'Corpo Prova', 'Direção Corpo', 'Posição Corpo', 'Temperatura',
            'Limite Escoamento', 'Limite Resistência', 'Alongamento', 'Estricção', 'Dureza', 'Tratamento Térmico',
        ]]
        for r in bloco:
            mapa = r['tracao'] if isinstance(r['tracao'], dict) else {}
            tracao_data.append([
                str(r['item'].ordem),
                _fmt_value(mapa.get('corpo_prova')),
                _fmt_value(mapa.get('direcao')),
                _fmt_value(mapa.get('posicao')),
                _fmt_value(mapa.get('temperatura')),
                _fmt_value(mapa.get('limite_escoamento')),
                _fmt_value(mapa.get('limite_resistencia')),
                _fmt_value(mapa.get('alongamento')),
                _fmt_value(mapa.get('estriccao')),
                _fmt_value(mapa.get('dureza')),
                _fmt_value(mapa.get('tratamento_termico')),
            ])
        bloco_flow.append(section_title('Teste de Tração / Traction Test'))
        bloco_flow.append(
            data_table(
                tracao_data,
                [10 * mm, 22 * mm, 20 * mm, 20 * mm, 18 * mm, 26 * mm, 26 * mm, 20 * mm, 18 * mm, 16 * mm, 52 * mm],
                row_h=6.2 * mm,
            )
        )

        impact_sources = []
        for r in bloco:
            mapa = r['impacto'] if isinstance(r['impacto'], dict) else {}
            if any((mapa.get(k) not in (None, '', {})) for k in IMPACTO_COLS):
                impact_sources.append((r, mapa))
        if impact_sources:
            impacto_data = [['Item', 'Norma', 'Corpo Prova', 'Direção', 'Posição', 'Temperatura', 'CP A', 'CP B', 'CP C', 'Média']]
            for r, mapa in impact_sources:
                impacto_data.append([
                    str(r['item'].ordem),
                    _fmt_value(mapa.get('norma')),
                    _fmt_value(mapa.get('corpo_prova')),
                    _fmt_value(mapa.get('direcao')),
                    _fmt_value(mapa.get('posicao')),
                    _fmt_value(mapa.get('temperatura')),
                    _fmt_value(mapa.get('corpo_prova_a')),
                    _fmt_value(mapa.get('corpo_prova_b')),
                    _fmt_value(mapa.get('corpo_prova_c')),
                    _fmt_value(mapa.get('media')),
                ])
            bloco_flow.append(Spacer(1, 1.8 * mm))
            bloco_flow.append(section_title('Teste de Impacto / Impact Test'))
            bloco_flow.append(data_table(impacto_data, [12 * mm, 24 * mm, 28 * mm, 22 * mm, 22 * mm, 18 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm], row_h=6.0 * mm))
        return bloco_flow

    def estimate_height(flowables: list) -> float:
        total = 0.0
        for fl in flowables:
            _, h = fl.wrap(doc.width, doc.height)
            total += h
        return total

    common_rows_all = [item_row(it) for it in itens_comuns]
    i = 0
    common_blocks: list[list[dict]] = []
    while i < len(common_rows_all):
        remaining = len(common_rows_all) - i
        max_try = min(MAX_ITENS_COMUNS_POR_PAGINA, remaining)
        min_try = 3 if remaining > 3 else 1
        chosen = None
        for size in range(max_try, min_try - 1, -1):
            bloco = common_rows_all[i:i + size]
            bloco_h = estimate_height(build_common_block_flow(bloco))
            if bloco_h <= (doc.height - 2.0 * mm):
                chosen = bloco
                break
        if chosen is None:
            fallback_size = max_try if max_try < 3 else 3
            chosen = common_rows_all[i:i + fallback_size]
        common_blocks.append(chosen)
        i += len(chosen)

    for idx_bloco, bloco in enumerate(common_blocks):
        story.append(KeepTogether(build_common_block_flow(bloco)))
        has_more_sections = idx_bloco < len(common_blocks) - 1 or bool(itens_valvula)
        if has_more_sections:
            story.append(PageBreak())

    for idx_valvula, item_valvula in enumerate(itens_valvula):
        componentes = list(item_valvula.componentes.filter(ativo=True).all())
        comp_chunks = list(_chunks(componentes, MAX_COMPONENTES_VALVULA_POR_BLOCO)) or [[]]
        for idx_comp_chunk, comp_chunk in enumerate(comp_chunks):
            story.extend(comercial_flowables())
            story.append(section_title('Válvula / Componentes'))

            item_valvula_data = [[
                'Item', 'Código', 'Descrição', 'Quantidade', 'Unidade', 'Norma', 'Certificado Fornecedor (snapshot)',
            ], [
                str(item_valvula.ordem),
                item_valvula.codigo_produto or '—',
                (item_valvula.descricao_material or '—')[:74],
                _fmt_value(item_valvula.quantidade),
                item_valvula.unidade or '—',
                item_valvula.norma or '—',
                item_valvula.numero_certificado_fornecedor_item_snapshot or '—',
            ]]
            story.append(data_table(item_valvula_data, [12 * mm, 30 * mm, 95 * mm, 22 * mm, 18 * mm, 36 * mm, 58 * mm], row_h=7.2 * mm))
            story.append(Spacer(1, 1.8 * mm))

            if comp_chunk:
                comp_rows = [['Comp.', 'Corrida', 'Lote', 'Norma', 'Certificado Fornecedor', 'Observação']]
                for cp in comp_chunk:
                    comp_rows.append([
                        cp.nome_componente or '—',
                        cp.corrida or '—',
                        getattr(cp, 'lote', '') or item_valvula.lote_snapshot or '—',
                        cp.norma or '—',
                        cp.numero_certificado_fornecedor_componente_snapshot or item_valvula.numero_certificado_fornecedor_item_snapshot or '—',
                        (cp.observacoes or '—')[:38],
                    ])
                story.append(section_title('Componentes da válvula'))
                story.append(data_table(comp_rows, [42 * mm, 30 * mm, 24 * mm, 40 * mm, 48 * mm, 87 * mm], row_h=6.7 * mm))
                story.append(Spacer(1, 1.8 * mm))

                composicao_componentes = [['Comp.', 'QTD'] + COMPOSICAO_COLS]
                for cp in comp_chunk:
                    mapa = cp.composicao_json if isinstance(cp.composicao_json, dict) else {}
                    row = [cp.nome_componente or '—', _fmt_value(cp.quantidade if cp.quantidade is not None else item_valvula.quantidade)]
                    row.extend([_fmt_value(mapa.get(k)) for k in COMPOSICAO_COLS])
                    composicao_componentes.append(row)
                story.append(section_title('Composição Química por componente'))
                story.append(data_table(composicao_componentes, [17 * mm, 10 * mm] + [8.8 * mm] * len(COMPOSICAO_COLS), row_h=5.8 * mm))
                story.append(Spacer(1, 1.8 * mm))

                tracao_componentes = [[
                    'Comp.', 'Corpo Prova', 'Direção Corpo', 'Posição Corpo', 'Temperatura',
                    'Limite Escoamento', 'Limite Resistência', 'Alongamento', 'Estricção', 'Dureza', 'Tratamento Térmico',
                ]]
                for cp in comp_chunk:
                    mapa = cp.ensaio_tracao_json if isinstance(cp.ensaio_tracao_json, dict) else {}
                    tracao_componentes.append([
                        cp.nome_componente or '—',
                        _fmt_value(mapa.get('corpo_prova')),
                        _fmt_value(mapa.get('direcao')),
                        _fmt_value(mapa.get('posicao')),
                        _fmt_value(mapa.get('temperatura')),
                        _fmt_value(mapa.get('limite_escoamento')),
                        _fmt_value(mapa.get('limite_resistencia')),
                        _fmt_value(mapa.get('alongamento')),
                        _fmt_value(mapa.get('estriccao')),
                        _fmt_value(mapa.get('dureza')),
                        _fmt_value(mapa.get('tratamento_termico')),
                    ])
                story.append(section_title('Propriedades mecânicas por componente'))
                story.append(data_table(tracao_componentes, [17 * mm, 20 * mm, 18 * mm, 18 * mm, 16 * mm, 23 * mm, 23 * mm, 18 * mm, 16 * mm, 14 * mm, 44 * mm], row_h=6.1 * mm))

                impactos_componentes = []
                for cp in comp_chunk:
                    mapa = cp.ensaio_impacto_json if isinstance(cp.ensaio_impacto_json, dict) else {}
                    if any((mapa.get(k) not in (None, '', {})) for k in IMPACTO_COLS):
                        impactos_componentes.append((cp, mapa))
                if impactos_componentes:
                    impacto_data = [['Comp.', 'Norma', 'Corpo Prova', 'Direção', 'Posição', 'Temperatura', 'CP A', 'CP B', 'CP C', 'Média']]
                    for cp, mapa in impactos_componentes:
                        impacto_data.append([
                            cp.nome_componente or '—',
                            _fmt_value(mapa.get('norma')),
                            _fmt_value(mapa.get('corpo_prova')),
                            _fmt_value(mapa.get('direcao')),
                            _fmt_value(mapa.get('posicao')),
                            _fmt_value(mapa.get('temperatura')),
                            _fmt_value(mapa.get('corpo_prova_a')),
                            _fmt_value(mapa.get('corpo_prova_b')),
                            _fmt_value(mapa.get('corpo_prova_c')),
                            _fmt_value(mapa.get('media')),
                        ])
                    story.append(Spacer(1, 1.8 * mm))
                    story.append(section_title('Impacto por componente'))
                    story.append(data_table(impacto_data, [17 * mm, 22 * mm, 24 * mm, 18 * mm, 18 * mm, 16 * mm, 14 * mm, 14 * mm, 14 * mm, 14 * mm], row_h=6.0 * mm))

            needs_break = not (idx_valvula == len(itens_valvula) - 1 and idx_comp_chunk == len(comp_chunks) - 1)
            if needs_break:
                story.append(PageBreak())

    observacoes_raw = (cert.observacoes or '').strip()
    observacoes_has_content = observacoes_raw not in ('', '-', '—')
    if observacoes_has_content:
        obs_style = ParagraphStyle(
            'obs',
            fontName='Helvetica',
            fontSize=8.0,
            leading=9.4,
            textColor=PDF_THEME['text'],
        )
        obs_table = Table([[Paragraph(observacoes_raw.replace('\n', '<br/>'), obs_style)]], colWidths=[doc.width], rowHeights=[18 * mm])
        obs_table.setStyle(
            TableStyle(
                [
                    ('GRID', (0, 0), (-1, -1), 0.28, PDF_THEME['border']),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3 * mm),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 3 * mm),
                    ('TOPPADDING', (0, 0), (-1, -1), 2.2 * mm),
                ],
            )
        )
        story.append(Spacer(1, 2 * mm))
        story.append(section_title('Observações / Comments'))
        story.append(obs_table)
    doc.build(story, canvasmaker=NumberedCanvas)
    buf.seek(0)
    return buf.read()
