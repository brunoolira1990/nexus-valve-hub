"""Representação Gráfica de CC-e — layout fiscal Nexus (prévia e autorizada). Não é DANFE."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.pdf.components import build_logo_cell
from apps.core.pdf.styles import (
    C_BORDER,
    C_FRAME_LIGHT,
    C_HEADER_DEEP,
    C_HEADER_FG,
    C_LABEL_BG,
    C_MUTED,
    C_PRIMARY,
    C_SLATE_TEXT,
    C_TABLE_HEADER_BG,
    FONT_PDF_SECTION,
    FONT_PDF_SMALL,
    base_paragraph_styles,
)
from apps.core.pdf.formatters import nobr
from apps.fiscal.nfe_emissao.carta_correcao_dados import MSG_O_QUE_NAO_PODE_CORRIGIR

_MARGIN_X = 8 * mm
_MARGIN_Y = 8 * mm
_PAGE_W = A4[0]
_CONTENT_W = _PAGE_W - 2 * _MARGIN_X

_COR_AVISO = colors.HexColor('#b45309')
_COR_AVISO_FUNDO = colors.HexColor('#fffbeb')
_W_LOGO = 48 * mm
_W_DOC = 62 * mm


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


_W_ROTULO = 34 * mm
_MIN_ALTURA_CORRECOES = 42 * mm


def _html_chave_acesso(chave: str) -> str:
    """Chave em até duas linhas horizontais — evita quebra vertical por coluna estreita."""
    bruto = str(chave or '').strip()
    digits = ''.join(c for c in bruto if c.isdigit())
    if len(digits) == 44:
        grupos = [digits[i : i + 4] for i in range(0, 44, 4)]
        linha1 = ' '.join(grupos[:6])
        linha2 = ' '.join(grupos[6:])
        return f'{nobr(linha1)}<br/>{nobr(linha2)}'
    if bruto and bruto != '—':
        return nobr(bruto)
    return '—'


def _estilo_bloco_largura_total() -> TableStyle:
    return TableStyle(
        [
            ('BOX', (0, 0), (-1, -1), 0.75, C_SLATE_TEXT),
            ('INNERGRID', (0, 0), (-1, -1), 0.35, C_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, -1), C_LABEL_BG),
            ('LEFTPADDING', (0, 0), (-1, -1), 7),
            ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ],
    )


def _titulo_faixa(titulo: str, style) -> Table:
    tbl = Table([[Paragraph(f'<b>{escape(titulo)}</b>', style)]], colWidths=[_CONTENT_W])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), C_TABLE_HEADER_BG),
                ('BOX', (0, 0), (-1, -1), 0.75, C_SLATE_TEXT),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ],
        ),
    )
    return tbl


def _bloco_identificacao_nfe(
    dados: dict[str, Any],
    rotulo_style,
    valor_style,
    chave_style,
) -> Table:
    """Identificação da NF-e em largura total."""
    w_val = _CONTENT_W - _W_ROTULO
    w_terco = w_val / 3
    row_topo = [
        [
            Paragraph('<b>NF-e nº</b>', rotulo_style),
            Paragraph(escape(str(dados.get('numero_nfe') or '—')), valor_style),
            Paragraph('<b>Série</b>', rotulo_style),
            Paragraph(escape(str(dados.get('serie_nfe') or '—')), valor_style),
            Paragraph('<b>Ambiente</b>', rotulo_style),
            Paragraph(escape(str(dados.get('ambiente_label') or '—')), valor_style),
        ],
    ]
    tbl_topo = Table(
        row_topo,
        colWidths=[_W_ROTULO * 0.55, w_terco - _W_ROTULO * 0.55, _W_ROTULO * 0.45, w_terco - _W_ROTULO * 0.45, _W_ROTULO * 0.55, w_terco - _W_ROTULO * 0.55],
    )
    style_topo = _estilo_bloco_largura_total()
    style_topo.add('BACKGROUND', (0, 0), (0, 0), C_LABEL_BG)
    style_topo.add('BACKGROUND', (2, 0), (2, 0), C_LABEL_BG)
    style_topo.add('BACKGROUND', (4, 0), (4, 0), C_LABEL_BG)
    tbl_topo.setStyle(style_topo)

    row_dest = [
        [
            Paragraph('<b>Destinatário</b>', rotulo_style),
            Paragraph(escape(str(dados.get('destinatario') or '—')), valor_style),
        ],
    ]
    tbl_dest = Table(row_dest, colWidths=[_W_ROTULO, w_val])
    style_dest = _estilo_bloco_largura_total()
    tbl_dest.setStyle(style_dest)

    chave_fmt = str(dados.get('chave_acesso_fmt') or dados.get('chave_acesso') or '—')
    row_chave = [
        [
            Paragraph('<b>Chave de acesso</b>', rotulo_style),
            Paragraph(_html_chave_acesso(chave_fmt), chave_style),
        ],
    ]
    tbl_chave = Table(row_chave, colWidths=[_W_ROTULO, w_val])
    style_chave = _estilo_bloco_largura_total()
    tbl_chave.setStyle(style_chave)

    bloco = Table([[tbl_topo], [tbl_dest], [tbl_chave]], colWidths=[_CONTENT_W])
    bloco.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    return bloco


def _bloco_dados_evento(
    dados: dict[str, Any],
    *,
    transmitido: bool,
    rotulo_style,
    valor_style,
) -> Table:
    """Dados do evento em grade horizontal legível."""
    w_val = _CONTENT_W - _W_ROTULO
    if transmitido:
        seq = str(dados.get('sequencia_evento') or dados.get('sequencia_prevista') or '—')
        linhas = [
            [
                Paragraph('<b>Sequência</b>', rotulo_style),
                Paragraph(escape(seq), valor_style),
                Paragraph('<b>Status</b>', rotulo_style),
                Paragraph(escape(str(dados.get('status_evento') or 'Registrado na SEFAZ')), valor_style),
            ],
            [
                Paragraph('<b>Registro em</b>', rotulo_style),
                Paragraph(escape(_fmt_datetime(dados.get('emitido_em'))), valor_style),
                Paragraph('<b>Protocolo</b>', rotulo_style),
                Paragraph(escape(str(dados.get('protocolo') or '—')), valor_style),
            ],
            [
                Paragraph('<b>ID do evento</b>', rotulo_style),
                Paragraph(escape(str(dados.get('id_evento') or '—')), valor_style),
                Paragraph('<b>Retorno SEFAZ</b>', rotulo_style),
                Paragraph(
                    escape(f"{dados.get('cstat') or '—'} — {dados.get('xmotivo') or '—'}"),
                    valor_style,
                ),
            ],
        ]
        col_w = w_val / 2
        tbl = Table(linhas, colWidths=[_W_ROTULO * 0.72, col_w - _W_ROTULO * 0.72, _W_ROTULO * 0.72, col_w - _W_ROTULO * 0.72])
    else:
        linhas = [
            [
                Paragraph('<b>Sequência prevista</b>', rotulo_style),
                Paragraph(escape(str(dados.get('sequencia_prevista') or '—')), valor_style),
                Paragraph('<b>Status</b>', rotulo_style),
                Paragraph('Prévia — não transmitida', valor_style),
            ],
            [
                Paragraph('<b>Prévia gerada em</b>', rotulo_style),
                Paragraph(escape(_fmt_datetime(dados.get('previa_em'))), valor_style),
                '',
                '',
            ],
        ]
        col_w = w_val / 2
        tbl = Table(linhas, colWidths=[_W_ROTULO * 0.85, col_w - _W_ROTULO * 0.85, _W_ROTULO * 0.55, col_w - _W_ROTULO * 0.55])
        style = _estilo_bloco_largura_total()
        style.add('BACKGROUND', (0, 0), (0, 0), C_LABEL_BG)
        style.add('BACKGROUND', (2, 0), (2, 0), C_LABEL_BG)
        style.add('BACKGROUND', (0, 1), (0, 1), C_LABEL_BG)
        style.add('SPAN', (1, 1), (3, 1))
        tbl.setStyle(style)
        return tbl

    style = _estilo_bloco_largura_total()
    for r in range(len(linhas)):
        style.add('BACKGROUND', (0, r), (0, r), C_LABEL_BG)
        style.add('BACKGROUND', (2, r), (2, r), C_LABEL_BG)
    tbl.setStyle(style)
    return tbl


def _caixa_correcoes(texto: str, titulo_style, corpo_style) -> Table:
    """Bloco principal — largura total com altura mínima equilibrada."""
    header = Paragraph('<b>CORREÇÕES A SEREM CONSIDERADAS</b>', titulo_style)
    corpo = _p(texto or '—', corpo_style)
    tbl = Table([[header], [corpo]], colWidths=[_CONTENT_W])
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 1.2, C_HEADER_DEEP),
                ('BACKGROUND', (0, 0), (0, 0), C_HEADER_DEEP),
                ('TEXTCOLOR', (0, 0), (0, 0), C_HEADER_FG),
                ('BACKGROUND', (0, 1), (0, 1), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (0, 0), 9),
                ('BOTTOMPADDING', (0, 0), (0, 0), 9),
                ('TOPPADDING', (0, 1), (0, 1), 12),
                ('BOTTOMPADDING', (0, 1), (0, 1), 12),
                ('MINHEIGHT', (0, 1), (0, 1), _MIN_ALTURA_CORRECOES),
            ],
        ),
    )
    return tbl


def _linhas_emitente(dados: dict[str, Any]) -> list[tuple[str, bool]]:
    """(texto, é_título)"""
    out: list[tuple[str, bool]] = []
    rz = str(dados.get('emitente') or '').strip()
    fantasia = str(dados.get('emitente_fantasia') or '').strip()
    if rz:
        out.append((rz, True))
    if fantasia and fantasia.upper() != rz.upper():
        out.append((fantasia, False))
    cnpj = str(dados.get('emitente_cnpj') or '').strip()
    ie = str(dados.get('emitente_ie') or '').strip()
    doc_bits = [p for p in [f'CNPJ {cnpj}' if cnpj else '', f'IE {ie}' if ie else ''] if p]
    if doc_bits:
        out.append((' · '.join(doc_bits), False))
    endereco = str(dados.get('emitente_endereco') or '').strip()
    if endereco and endereco != '—':
        out.append((endereco, False))
    cidade = str(dados.get('emitente_cidade') or '').strip()
    uf = str(dados.get('emitente_uf') or '').strip()
    cep = str(dados.get('emitente_cep') or '').strip()
    loc = ' — '.join(p for p in [f'{cidade}/{uf}' if cidade and uf else (cidade or uf), f'CEP {cep}' if cep else ''] if p)
    if loc:
        out.append((loc, False))
    tel = str(dados.get('emitente_telefone') or '').strip()
    email = str(dados.get('emitente_email') or '').strip()
    contato = ' · '.join(p for p in [tel, email] if p)
    if contato:
        out.append((contato, False))
    return out


def _cabecalho_emitente(dados: dict[str, Any], ph_title, ph_line, ph_center, ph_doc) -> Table:
    logo_path = str(dados.get('emitente_logo_path') or '').strip() or None
    if logo_path:
        logo_cell = build_logo_cell(logo_path, ph_center=ph_center, header_spacious=True)
    else:
        rz = escape(str(dados.get('emitente') or 'Emitente'))
        logo_cell = Table(
            [[Paragraph(f'<b><font size="10" color="#0F5EDB">{rz}</font></b>', ph_center)]],
            colWidths=[_W_LOGO],
            rowHeights=[22 * mm],
        )
        logo_cell.setStyle(
            TableStyle(
                [
                    ('BOX', (0, 0), (-1, -1), 0.5, C_FRAME_LIGHT),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ],
            ),
        )

    w_mid = _CONTENT_W - _W_LOGO - _W_DOC
    mid_rows = [
        [Paragraph(escape(txt), ph_title if is_title else ph_line)]
        for txt, is_title in _linhas_emitente(dados)
    ]
    if not mid_rows:
        mid_rows = [[Paragraph('—', ph_line)]]
    mid_tbl = Table(mid_rows, colWidths=[w_mid])
    mid_tbl.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ],
        ),
    )

    transmitido = bool(dados.get('transmitido'))
    status_doc = 'AUTORIZADA' if transmitido else 'PRÉVIA'
    quadro = Table(
        [
            [Paragraph('<font size="7" color="#cbd5e1">DOCUMENTO FISCAL</font>', ph_doc)],
            [Paragraph('<b><font size="16" color="white">CC-e</font></b>', ph_doc)],
            [Paragraph('<font size="8" color="#e2e8f0">Representação Gráfica</font>', ph_doc)],
            [Paragraph('<font size="7.5" color="#94a3b8">Carta de Correção Eletrônica</font>', ph_doc)],
            [Paragraph(f'<b><font size="9" color="white">{escape(str(dados.get("ambiente_label") or ""))}</font></b>', ph_doc)],
            [Paragraph(f'<font size="8" color="#fbbf24">{status_doc}</font>', ph_doc)],
        ],
        colWidths=[_W_DOC],
    )
    quadro.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 1, C_HEADER_DEEP),
                ('BACKGROUND', (0, 0), (-1, -1), C_HEADER_DEEP),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ],
        ),
    )

    hdr = Table([[logo_cell, mid_tbl, quadro]], colWidths=[_W_LOGO, w_mid, _W_DOC])
    hdr.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 1, C_SLATE_TEXT),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (1, 0), colors.white),
                ('LEFTPADDING', (0, 0), (1, 0), 8),
                ('RIGHTPADDING', (0, 0), (1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LINEAFTER', (0, 0), (0, 0), 0.5, C_BORDER),
                ('LINEAFTER', (1, 0), (1, 0), 0.5, C_BORDER),
            ],
        ),
    )
    return hdr


def _faixa_avisos(avisos: list[str], warn_style) -> list[Any]:
    if not avisos:
        return []
    html = ' &nbsp;|&nbsp; '.join(f'<b>{escape(av)}</b>' for av in avisos)
    tbl = Table([[Paragraph(html, warn_style)]], colWidths=[_CONTENT_W])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), _COR_AVISO_FUNDO),
                ('BOX', (0, 0), (-1, -1), 1.2, _COR_AVISO),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ],
        ),
    )
    return [tbl, Spacer(1, 5)]


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
                ('BOX', (0, 0), (-1, -1), 0.5, C_BORDER),
                ('BACKGROUND', (0, 0), (0, 0), C_LABEL_BG),
                ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#fafbfc')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
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

    ph_title = ParagraphStyle(
        'CceEmitTitle',
        parent=ph,
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=12.5,
        textColor=C_PRIMARY,
    )
    ph_line = ParagraphStyle(
        'CceEmitLine',
        parent=ph_small,
        fontSize=8.5,
        leading=10.5,
        textColor=C_MUTED,
    )
    ph_doc = ParagraphStyle('CceDoc', parent=ph, alignment=TA_RIGHT, textColor=C_HEADER_FG)
    secao = ParagraphStyle(
        'CceSecao',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=FONT_PDF_SECTION + 0.5,
        leading=12,
        textColor=C_HEADER_DEEP,
        alignment=TA_LEFT,
    )
    rotulo = ParagraphStyle(
        'CceRotulo',
        parent=ph,
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=C_SLATE_TEXT,
    )
    valor = ParagraphStyle(
        'CceValor',
        parent=ph,
        fontSize=9.5,
        leading=11.5,
        textColor=C_PRIMARY,
    )
    chave = ParagraphStyle(
        'CceChave',
        parent=valor,
        fontName='Courier',
        fontSize=8.8,
        leading=11,
    )
    correcao = ParagraphStyle(
        'CceCorrecao',
        parent=ph,
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=C_PRIMARY,
        alignment=TA_LEFT,
        spaceBefore=0,
        spaceAfter=0,
    )
    correcao_titulo = ParagraphStyle(
        'CceCorrecaoTit',
        parent=secao,
        fontSize=11,
        alignment=TA_CENTER,
        textColor=C_HEADER_FG,
    )
    warn = ParagraphStyle(
        'CceWarn',
        parent=ph,
        fontName='Helvetica-Bold',
        fontSize=10.5,
        textColor=_COR_AVISO,
        leading=13,
        alignment=TA_CENTER,
    )
    legal_titulo = ParagraphStyle('CceLegalTit', parent=rotulo, fontSize=8)
    legal_corpo = ParagraphStyle('CceLegalCorpo', parent=ph_small, fontSize=FONT_PDF_SMALL, leading=9.5, textColor=C_MUTED)
    rodape = ParagraphStyle(
        'CceRodape',
        parent=ph_small,
        fontSize=7.5,
        leading=10,
        textColor=C_MUTED,
        alignment=TA_CENTER,
    )

    avisos: list[str] = []
    if not transmitido:
        avisos.append('PRÉVIA — NÃO TRANSMITIDA À SEFAZ')
    if homolog:
        avisos.append('HOMOLOGAÇÃO — SEM VALOR FISCAL')

    if transmitido:
        texto_rodape = (
            'Evento registrado na SEFAZ conforme retorno eletrônico. '
            'Representação gráfica auxiliar — não substitui o XML do evento.'
        )
    else:
        texto_rodape = 'Documento de prévia — não transmitido à SEFAZ. Não possui validade fiscal.'

    story: list[Any] = [
        _cabecalho_emitente(dados, ph_title, ph_line, ph_center, ph_doc),
        Spacer(1, 5),
    ]
    story.extend(_faixa_avisos(avisos, warn))
    story.append(_titulo_faixa('IDENTIFICAÇÃO DA NF-e', secao))
    story.append(_bloco_identificacao_nfe(dados, rotulo, valor, chave))
    story.append(Spacer(1, 4))
    story.append(_titulo_faixa('DADOS DO EVENTO', secao))
    story.append(_bloco_dados_evento(dados, transmitido=transmitido, rotulo_style=rotulo, valor_style=valor))
    story.append(Spacer(1, 6))
    story.append(_caixa_correcoes(str(dados.get('texto_correcao') or ''), correcao_titulo, correcao))
    story.append(Spacer(1, 5))
    story.append(_bloco_legal(str(dados.get('o_que_nao_pode_corrigir') or MSG_O_QUE_NAO_PODE_CORRIGIR), legal_titulo, legal_corpo))
    story.append(Spacer(1, 6))
    story.append(Paragraph(escape(texto_rodape), rodape))

    doc.build(story)
    return buf.getvalue()


def gerar_pdf_previa_cce(dados: dict[str, Any]) -> bytes:
    dados = {**dados, 'transmitido': False, 'modo': 'previa'}
    return gerar_pdf_representacao_cce(dados)


def gerar_pdf_comprovante_cce(dados: dict[str, Any]) -> bytes:
    dados = {**dados, 'transmitido': True, 'modo': 'autorizada'}
    return gerar_pdf_representacao_cce(dados)
