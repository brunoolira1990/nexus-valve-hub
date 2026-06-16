"""Representação Gráfica de CC-e — layout fiscal Nexus (prévia e autorizada). Não é DANFE."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.pdf.components import build_logo_cell
from apps.core.pdf.styles import (
    C_BORDER,
    C_FRAME_LIGHT,
    C_HEADER_DEEP,
    C_LABEL_BG,
    C_MUTED,
    C_PRIMARY,
    C_SLATE_TEXT,
    C_TABLE_HEADER_BG,
    FONT_PDF_BODY,
    FONT_PDF_SECTION,
    FONT_PDF_SMALL,
    base_paragraph_styles,
)
from apps.fiscal.nfe_emissao.carta_correcao_dados import MSG_O_QUE_NAO_PODE_CORRIGIR

_MARGIN_X = 10 * mm
_MARGIN_Y = 10 * mm
_PAGE_W = A4[0]
_CONTENT_W = _PAGE_W - 2 * _MARGIN_X

_COR_AVISO = colors.HexColor('#b45309')
_COR_AVISO_FUNDO = colors.HexColor('#fffbeb')


def _p(text: str, style) -> Paragraph:
    normalizado = str(text or '').replace('\r\n', '\n').replace('\r', '\n')
    html = escape(normalizado).replace('\n', '<br/>')
    return Paragraph(html or '—', style)


def _fmt_datetime(iso: str | None) -> str:
    if not iso:
        return '—'
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return str(iso)[:19]


def _linhas_emitente(dados: dict[str, Any]) -> list[str]:
    linhas: list[str] = []
    rz = str(dados.get('emitente') or '').strip()
    fantasia = str(dados.get('emitente_fantasia') or '').strip()
    if rz:
        linhas.append(rz)
    if fantasia and fantasia.upper() != rz.upper():
        linhas.append(fantasia)
    cnpj = str(dados.get('emitente_cnpj') or '').strip()
    ie = str(dados.get('emitente_ie') or '').strip()
    doc_bits = [p for p in [f'CNPJ {cnpj}' if cnpj else '', f'IE {ie}' if ie else ''] if p]
    if doc_bits:
        linhas.append(' · '.join(doc_bits))
    endereco = str(dados.get('emitente_endereco') or '').strip()
    if endereco and endereco != '—':
        linhas.append(endereco)
    cidade = str(dados.get('emitente_cidade') or '').strip()
    uf = str(dados.get('emitente_uf') or '').strip()
    cep = str(dados.get('emitente_cep') or '').strip()
    loc = ' — '.join(p for p in [f'{cidade}/{uf}' if cidade and uf else (cidade or uf), f'CEP {cep}' if cep else ''] if p)
    if loc:
        linhas.append(loc)
    tel = str(dados.get('emitente_telefone') or '').strip()
    email = str(dados.get('emitente_email') or '').strip()
    contato = ' · '.join(p for p in [f'Tel. {tel}' if tel else '', email] if p)
    if contato:
        linhas.append(contato)
    return linhas


def _cabecalho_emitente(dados: dict[str, Any], ph_small, ph_center, ph_bold) -> Table:
    logo_path = str(dados.get('emitente_logo_path') or '').strip() or None
    if logo_path:
        logo_cell = build_logo_cell(logo_path, ph_center=ph_center, header_spacious=True)
    else:
        rz = escape(str(dados.get('emitente') or 'Emitente'))
        logo_cell = Table(
            [[Paragraph(f'<b><font size="11" color="#0F5EDB">{rz}</font></b>', ph_center)]],
            colWidths=[46 * mm],
            rowHeights=[20 * mm],
        )
        logo_cell.setStyle(
            TableStyle(
                [
                    ('BOX', (0, 0), (-1, -1), 0.5, C_FRAME_LIGHT),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ],
            ),
        )

    mid_lines = _linhas_emitente(dados)
    mid_rows = [[Paragraph(escape(ln), ph_bold if idx == 0 else ph_small)] for idx, ln in enumerate(mid_lines)]
    if not mid_rows:
        mid_rows = [[Paragraph('—', ph_small)]]
    mid_tbl = Table(mid_rows, colWidths=[_CONTENT_W - 46 * mm - 58 * mm])
    mid_tbl.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))

    transmitido = bool(dados.get('transmitido'))
    status_doc = 'AUTORIZADA' if transmitido else 'PRÉVIA'
    quadro = Table(
        [
            [Paragraph('<b><font size="11">Representação Gráfica de CC-e</font></b>', ph_center)],
            [Paragraph('<font size="9">Carta de Correção Eletrônica</font>', ph_center)],
            [Paragraph(f'<font size="8"><b>{escape(str(dados.get("ambiente_label") or ""))}</b></font>', ph_center)],
            [Paragraph(f'<font size="8" color="#64748b">{status_doc}</font>', ph_center)],
        ],
        colWidths=[58 * mm],
    )
    quadro.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 1, C_HEADER_DEEP),
                ('BACKGROUND', (0, 0), (-1, -1), C_TABLE_HEADER_BG),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ],
        ),
    )

    hdr = Table([[logo_cell, mid_tbl, quadro]], colWidths=[46 * mm, _CONTENT_W - 46 * mm - 58 * mm, 58 * mm])
    hdr.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.75, C_SLATE_TEXT),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LINEAFTER', (0, 0), (0, 0), 0.25, C_BORDER),
                ('LINEAFTER', (1, 0), (1, 0), 0.25, C_BORDER),
            ],
        ),
    )
    return hdr


def _faixa_avisos(avisos: list[str], warn_style) -> list[Any]:
    if not avisos:
        return []
    html = '<br/>'.join(f'<b>{escape(av)}</b>' for av in avisos)
    tbl = Table([[Paragraph(html, warn_style)]], colWidths=[_CONTENT_W])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), _COR_AVISO_FUNDO),
                ('BOX', (0, 0), (-1, -1), 1, _COR_AVISO),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ],
        ),
    )
    return [tbl, Spacer(1, 6)]


def _titulo_secao(titulo: str, style) -> Table:
    tbl = Table([[Paragraph(f'<b>{escape(titulo)}</b>', style)]], colWidths=[_CONTENT_W])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), C_LABEL_BG),
                ('BOX', (0, 0), (-1, -1), 0.5, C_SLATE_TEXT),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ],
        ),
    )
    return tbl


def _grade_duas_colunas(
    esquerda: list[tuple[str, str]],
    direita: list[tuple[str, str]],
    label_style,
    value_style,
) -> Table:
    col_w = (_CONTENT_W - 4) / 2
    label_w = 32 * mm

    def bloco(linhas: list[tuple[str, str]]) -> Table:
        data = [[Paragraph(f'<b>{escape(k)}</b>', label_style), _p(v, value_style)] for k, v in linhas]
        tbl = Table(data, colWidths=[label_w, col_w - label_w - 2 * mm])
        tbl.setStyle(
            TableStyle(
                [
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('BOX', (0, 0), (-1, -1), 0.5, C_SLATE_TEXT),
                    ('INNERGRID', (0, 0), (-1, -1), 0.25, C_BORDER),
                    ('BACKGROUND', (0, 0), (0, -1), C_LABEL_BG),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ],
            ),
        )
        return tbl

    outer = Table([[bloco(esquerda), bloco(direita)]], colWidths=[col_w, col_w])
    outer.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    return outer


def _caixa_correcoes(texto: str, titulo_style, corpo_style) -> Table:
    header = Paragraph('<b>CORREÇÕES A SEREM CONSIDERADAS</b>', titulo_style)
    corpo = _p(texto or '—', corpo_style)
    tbl = Table([[header], [corpo]], colWidths=[_CONTENT_W])
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 1.2, C_HEADER_DEEP),
                ('BACKGROUND', (0, 0), (0, 0), C_TABLE_HEADER_BG),
                ('BACKGROUND', (0, 1), (0, 1), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (0, 0), 8),
                ('BOTTOMPADDING', (0, 0), (0, 0), 8),
                ('TOPPADDING', (0, 1), (0, 1), 10),
                ('BOTTOMPADDING', (0, 1), (0, 1), 12),
                ('MINHEIGHT', (0, 1), (0, 1), 75 * mm),
            ],
        ),
    )
    return tbl


def _bloco_legal(texto: str, titulo_style, corpo_style) -> Table:
    tbl = Table(
        [
            [Paragraph('<b>Limitações da Carta de Correção</b>', titulo_style)],
            [_p(texto, corpo_style)],
        ],
        colWidths=[_CONTENT_W],
    )
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.5, C_SLATE_TEXT),
                ('BACKGROUND', (0, 0), (0, 0), C_LABEL_BG),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ],
        ),
    )
    return tbl


def gerar_pdf_representacao_cce(dados: dict[str, Any]) -> bytes:
    """Layout único — variação apenas nos dados e avisos conforme prévia ou autorizada."""
    transmitido = bool(dados.get('transmitido'))
    homolog = bool(dados.get('homologacao'))

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=_MARGIN_X,
        rightMargin=_MARGIN_X,
        topMargin=_MARGIN_Y,
        bottomMargin=_MARGIN_Y,
    )
    ph, ph_small, _ph_right, ph_center, _ph_white = base_paragraph_styles()
    styles = getSampleStyleSheet()

    ph_bold = ParagraphStyle(
        'CceEmitBold',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=C_PRIMARY,
    )
    ph_emit_ln = ParagraphStyle(
        'CceEmitLn',
        parent=ph_small,
        fontSize=8,
        leading=10,
        textColor=C_MUTED,
    )
    secao = ParagraphStyle(
        'CceSecao',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=FONT_PDF_SECTION,
        leading=11,
        textColor=C_PRIMARY,
        alignment=TA_LEFT,
    )
    label = ParagraphStyle(
        'CceLabel',
        parent=ph,
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        textColor=C_SLATE_TEXT,
    )
    body = ParagraphStyle(
        'CceBody',
        parent=ph,
        fontSize=FONT_PDF_BODY,
        leading=12,
        textColor=C_PRIMARY,
    )
    correcao = ParagraphStyle(
        'CceCorrecao',
        parent=ph,
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=C_PRIMARY,
        alignment=TA_LEFT,
    )
    correcao_titulo = ParagraphStyle(
        'CceCorrecaoTit',
        parent=secao,
        fontSize=11,
        alignment=TA_CENTER,
        textColor=C_HEADER_DEEP,
    )
    warn = ParagraphStyle(
        'CceWarn',
        parent=ph,
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=_COR_AVISO,
        leading=13,
        alignment=TA_CENTER,
    )
    legal_titulo = ParagraphStyle('CceLegalTit', parent=secao, fontSize=9)
    legal_corpo = ParagraphStyle('CceLegalCorpo', parent=ph_small, fontSize=FONT_PDF_SMALL + 0.3, leading=10)
    rodape = ParagraphStyle(
        'CceRodape',
        parent=ph_small,
        fontSize=8,
        leading=11,
        textColor=C_MUTED,
        alignment=TA_CENTER,
    )

    avisos: list[str] = []
    if not transmitido:
        avisos.append('PRÉVIA — NÃO TRANSMITIDA À SEFAZ')
    if homolog:
        avisos.append('HOMOLOGAÇÃO — SEM VALOR FISCAL')

    chave_fmt = str(dados.get('chave_acesso_fmt') or dados.get('chave_acesso') or '—')
    campos_nfe = [
        ('Número', str(dados.get('numero_nfe') or '—')),
        ('Série', str(dados.get('serie_nfe') or '—')),
        ('Chave de acesso', chave_fmt),
        ('Destinatário', str(dados.get('destinatario') or '—')),
    ]

    if transmitido:
        seq = dados.get('sequencia_evento') or dados.get('sequencia_prevista') or '—'
        status_ev = str(dados.get('status_evento') or 'Registrado na SEFAZ')
        campos_evento = [
            ('Sequência', str(seq)),
            ('Status', status_ev),
            ('Registro em', _fmt_datetime(dados.get('emitido_em'))),
            ('Protocolo', str(dados.get('protocolo') or '—')),
            ('ID do evento', str(dados.get('id_evento') or '—')),
            ('Retorno SEFAZ', f"{dados.get('cstat') or '—'} — {dados.get('xmotivo') or '—'}"),
        ]
        texto_rodape = (
            'Evento registrado na SEFAZ conforme retorno eletrônico. '
            'Representação gráfica auxiliar — não substitui o XML do evento.'
        )
    else:
        campos_evento = [
            ('Sequência prevista', str(dados.get('sequencia_prevista') or '—')),
            ('Status', 'Prévia — não transmitida'),
            ('Prévia gerada em', _fmt_datetime(dados.get('previa_em'))),
            ('Ambiente', str(dados.get('ambiente_label') or '—')),
        ]
        texto_rodape = 'Documento de prévia — não transmitido à SEFAZ. Não possui validade fiscal.'

    story: list[Any] = [
        _cabecalho_emitente(dados, ph_emit_ln, ph_center, ph_bold),
        Spacer(1, 8),
    ]
    story.extend(_faixa_avisos(avisos, warn))
    story.append(_titulo_secao('IDENTIFICAÇÃO DA NF-e / DADOS DO EVENTO', secao))
    story.append(Spacer(1, 4))
    story.append(_grade_duas_colunas(campos_nfe, campos_evento, label, body))
    story.append(Spacer(1, 8))
    story.append(_bloco_legal(str(dados.get('o_que_nao_pode_corrigir') or MSG_O_QUE_NAO_PODE_CORRIGIR), legal_titulo, legal_corpo))
    story.append(Spacer(1, 8))
    story.append(_caixa_correcoes(str(dados.get('texto_correcao') or ''), correcao_titulo, correcao))
    story.append(Spacer(1, 10))
    story.append(Paragraph(escape(texto_rodape), rodape))

    doc.build(story)
    return buf.getvalue()


def gerar_pdf_previa_cce(dados: dict[str, Any]) -> bytes:
    dados = {**dados, 'transmitido': False, 'modo': 'previa'}
    return gerar_pdf_representacao_cce(dados)


def gerar_pdf_comprovante_cce(dados: dict[str, Any]) -> bytes:
    dados = {**dados, 'transmitido': True, 'modo': 'autorizada'}
    return gerar_pdf_representacao_cce(dados)
