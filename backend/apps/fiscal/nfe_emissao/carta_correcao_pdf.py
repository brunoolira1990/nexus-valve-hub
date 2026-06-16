"""Representação Gráfica de CC-e — layout fiscal clássico Nexus (prévia e autorizada). Não é DANFE."""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.pdf.components import (
    _HEADER_LOGO_MAX_DRAW_H,
    _HEADER_LOGO_MAX_DRAW_W,
    _HEADER_LOGO_PAD_X,
    _HEADER_LOGO_PAD_Y,
    _logo_fit_proportional_box,
    _read_logo_pixel_size,
    build_logo_cell,
)
from apps.core.pdf.styles import (
    C_BORDER,
    C_BRAND_PRIMARY,
    C_FRAME_LIGHT,
    C_LABEL_BG,
    C_MUTED,
    C_PRIMARY,
    C_SLATE_TEXT,
    FONT_PDF_SMALL,
    base_paragraph_styles,
)
from apps.core.pdf.formatters import nobr
from apps.fiscal.nfe_emissao.carta_correcao_dados import MSG_O_QUE_NAO_PODE_CORRIGIR, resolver_barcode_cce

_MARGIN_X = 10 * mm
_MARGIN_Y = 10 * mm
_PAGE_W = A4[0]
_CONTENT_W = _PAGE_W - 2 * _MARGIN_X
_MOLDURA_PAD = 5 * mm
_MOLDURA_BORDER = 0.75

_COR_AVISO = colors.HexColor('#b45309')
_COR_AVISO_FUNDO = colors.HexColor('#fffbeb')
_W_LBL = 36 * mm
_PAD = 10
_MIN_ALTURA_CORRECOES = 58 * mm

MSG_TEXTO_LEGAL_CCE = (
    'A Carta de Correção Eletrônica (CC-e) constitui evento vinculado à NF-e identificada neste '
    'documento. As correções abaixo devem ser consideradas conforme a legislação aplicável à '
    'utilização da CC-e e integradas ao fluxo fiscal da nota fiscal eletrônica correspondente.'
)


def _inner_w() -> float:
    return _CONTENT_W - 2 * _MOLDURA_PAD


def _w_val() -> float:
    return _inner_w() - _W_LBL


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


def _html_chave_acesso(chave: str) -> str:
    bruto = str(chave or '').strip()
    digits = ''.join(c for c in bruto if c.isdigit())
    if len(digits) == 44:
        grupos = [digits[i : i + 4] for i in range(0, 44, 4)]
        return nobr(' '.join(grupos))
    if bruto and bruto != '—':
        return nobr(bruto)
    return '—'


def _lbl(texto: str, style) -> Paragraph:
    return Paragraph(f'<font color="#64748b"><b>{escape(texto)}</b></font>', style)


def _estilo_painel(*, linhas: int) -> TableStyle:
    style = TableStyle(
        [
            ('BOX', (0, 0), (-1, -1), 0.45, C_SLATE_TEXT),
            ('LINEBELOW', (0, 0), (-1, 0), 1.0, C_BRAND_PRIMARY),
            ('BACKGROUND', (0, 0), (-1, 0), C_LABEL_BG),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), _PAD),
            ('RIGHTPADDING', (0, 0), (-1, -1), _PAD),
            ('TOPPADDING', (0, 0), (0, 0), 7),
            ('BOTTOMPADDING', (0, 0), (0, 0), 7),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ],
    )
    for r in range(1, linhas):
        style.add('LINEBELOW', (0, r), (-1, r), 0.25, C_BORDER)
    return style


def _painel_duas_colunas(
    titulo: str,
    linhas: list[list],
    titulo_style,
    *,
    spans: list[tuple[tuple[int, int], tuple[int, int]]] | None = None,
    linhas_sem_divisor: set[int] | None = None,
    extra_style: list[tuple] | None = None,
) -> Table:
    rows = [[Paragraph(f'<b>{escape(titulo)}</b>', titulo_style), '']] + linhas
    tbl = Table(rows, colWidths=[_W_LBL, _w_val()])
    style = _estilo_painel(linhas=len(rows))
    style.add('SPAN', (0, 0), (1, 0))
    style.add('ALIGN', (0, 0), (-1, 0), 'LEFT')
    for a, b in spans or ():
        style.add('SPAN', a, b)
    for r in linhas_sem_divisor or set():
        style.add('LINEBELOW', (0, r), (-1, r), 0, colors.white)
    for cmd in extra_style or ():
        style.add(*cmd)
    tbl.setStyle(style)
    return tbl


def _linha_tripla_nfe(dados: dict[str, Any], rotulo_style, valor_style) -> Table:
    w = _w_val()
    w_col = w / 3
    w_lbl = 17 * mm
    campos = (
        ('NF-e nº', str(dados.get('numero_nfe') or '—')),
        ('Série', str(dados.get('serie_nfe') or '—')),
        ('Ambiente', str(dados.get('ambiente_label') or '—')),
    )
    row = []
    col_w = []
    for lbl, val in campos:
        row.extend([_lbl(lbl, rotulo_style), Paragraph(escape(val), valor_style)])
        col_w.extend([w_lbl, w_col - w_lbl])
    tbl = Table([row], colWidths=col_w)
    tbl.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ],
        ),
    )
    return tbl


def _bloco_chave_acesso_nfe(chave_fmt: str, chave_lbl_style, chave_style) -> Table:
    w = _inner_w()
    tbl = Table(
        [
            [
                Paragraph(
                    f'<nobr><font color="#64748b"><b>{escape("Chave de acesso da NF-e")}</b></font></nobr>',
                    chave_lbl_style,
                ),
            ],
            [Paragraph(_html_chave_acesso(chave_fmt), chave_style)],
        ],
        colWidths=[w],
    )
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.45, C_SLATE_TEXT),
                ('LINEABOVE', (0, 0), (-1, 0), 0, colors.white),
                ('LINEBELOW', (0, 0), (-1, 0), 0.25, C_BORDER),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), _PAD),
                ('RIGHTPADDING', (0, 0), (-1, -1), _PAD),
                ('TOPPADDING', (0, 0), (0, 0), 7),
                ('BOTTOMPADDING', (0, 0), (0, 0), 3),
                ('TOPPADDING', (0, 1), (0, 1), 4),
                ('BOTTOMPADDING', (0, 1), (0, 1), 10),
            ],
        ),
    )
    return tbl


def _bloco_identificacao_nfe(
    dados: dict[str, Any],
    titulo_style,
    rotulo_style,
    valor_style,
    chave_style,
    chave_lbl_style,
    *,
    incluir_chave: bool = True,
) -> list[Any]:
    chave_fmt = str(dados.get('chave_acesso_fmt') or dados.get('chave_acesso') or '—')
    linhas = [
        [_linha_tripla_nfe(dados, rotulo_style, valor_style), ''],
        [
            _lbl('Destinatário', rotulo_style),
            Paragraph(escape(str(dados.get('destinatario') or '—')), valor_style),
        ],
    ]
    painel = _painel_duas_colunas(
        'IDENTIFICAÇÃO DA NF-e',
        linhas,
        titulo_style,
        spans=[((0, 1), (1, 1))],
        extra_style=[
            ('LINEBELOW', (0, 2), (-1, 2), 0, colors.white),
            ('BOTTOMPADDING', (0, 2), (-1, 2), 6),
        ],
    )
    out: list[Any] = [painel]
    if incluir_chave:
        out.append(_bloco_chave_acesso_nfe(chave_fmt, chave_lbl_style, chave_style))
    return out


def _status_evento_html(*, transmitido: bool, dados: dict[str, Any]) -> str:
    if transmitido:
        return escape(str(dados.get('status_evento') or 'Registrado na SEFAZ'))
    return '<font color="#b45309"><b>PRÉVIA</b></font> — não transmitida à SEFAZ'


def _campo_evento(rotulo: str, valor_html: str, rotulo_style, valor_style) -> list:
    return [_lbl(rotulo, rotulo_style), Paragraph(valor_html, valor_style)]


def _bloco_dados_evento_cc(
    dados: dict[str, Any],
    *,
    transmitido: bool,
    titulo_style,
    rotulo_style,
    valor_style,
) -> Table:
    if transmitido:
        seq = str(dados.get('sequencia_evento') or dados.get('sequencia_prevista') or '—')
        linhas = [
            _campo_evento('Sequência do evento', escape(seq), rotulo_style, valor_style),
            _campo_evento(
                'Status do evento',
                _status_evento_html(transmitido=True, dados=dados),
                rotulo_style,
                valor_style,
            ),
        ]
        criado = _fmt_datetime(dados.get('criado_em_evento') or dados.get('emitido_em'))
        if criado != '—':
            linhas.append(_campo_evento('Criado em', escape(criado), rotulo_style, valor_style))
        id_evento = str(dados.get('id_evento') or '').strip()
        if id_evento:
            linhas.append(_campo_evento('ID do Evento', escape(id_evento), rotulo_style, valor_style))
        protocolo = str(dados.get('protocolo') or '').strip()
        if protocolo:
            linhas.append(_campo_evento('Protocolo', escape(protocolo), rotulo_style, valor_style))
        dh_reg = _fmt_datetime(dados.get('dh_reg_evento'))
        if dh_reg != '—':
            linhas.append(
                _campo_evento('Registrado na SEFAZ em', escape(dh_reg), rotulo_style, valor_style),
            )
        cstat = str(dados.get('cstat') or '').strip()
        xmotivo = str(dados.get('xmotivo') or '').strip()
        if cstat or xmotivo:
            linhas.append(
                _campo_evento(
                    'Retorno SEFAZ',
                    escape(f'{cstat or "—"} — {xmotivo or "—"}'),
                    rotulo_style,
                    valor_style,
                ),
            )
    else:
        linhas = [
            _campo_evento(
                'Sequência prevista',
                escape(str(dados.get('sequencia_prevista') or '—')),
                rotulo_style,
                valor_style,
            ),
            _campo_evento(
                'Status do evento',
                _status_evento_html(transmitido=False, dados=dados),
                rotulo_style,
                valor_style,
            ),
            _campo_evento(
                'Prévia gerada em',
                escape(_fmt_datetime(dados.get('previa_em'))),
                rotulo_style,
                valor_style,
            ),
        ]

    return _painel_duas_colunas('DADOS DO EVENTO CC-e', linhas, titulo_style)


def _bloco_texto_legal(style) -> Table:
    tbl = Table([[Paragraph(escape(MSG_TEXTO_LEGAL_CCE), style)]], colWidths=[_inner_w()])
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.35, C_BORDER),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafbfc')),
                ('LEFTPADDING', (0, 0), (-1, -1), _PAD),
                ('RIGHTPADDING', (0, 0), (-1, -1), _PAD),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ],
        ),
    )
    return tbl


def _caixa_correcoes(texto: str, titulo_style, corpo_style) -> Table:
    tbl = Table(
        [
            [Paragraph('<b>CORREÇÕES A SEREM CONSIDERADAS</b>', titulo_style)],
            [_p(texto or '—', corpo_style)],
        ],
        colWidths=[_inner_w()],
    )
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.55, C_SLATE_TEXT),
                ('BACKGROUND', (0, 0), (0, 0), C_LABEL_BG),
                ('LINEBELOW', (0, 0), (-1, 0), 0.45, C_SLATE_TEXT),
                ('BACKGROUND', (0, 1), (0, 1), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (0, 0), 8),
                ('BOTTOMPADDING', (0, 0), (0, 0), 8),
                ('TOPPADDING', (0, 1), (0, 1), 14),
                ('BOTTOMPADDING', (0, 1), (0, 1), 14),
                ('MINHEIGHT', (0, 1), (0, 1), _MIN_ALTURA_CORRECOES),
            ],
        ),
    )
    return tbl


def _bloco_limitacoes(texto: str, titulo_style, corpo_style) -> Table:
    tbl = Table(
        [
            [Paragraph('<b>Limitações da Carta de Correção</b>', titulo_style)],
            [_p(texto, corpo_style)],
        ],
        colWidths=[_inner_w()],
    )
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.35, C_BORDER),
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#fafbfc')),
                ('LINEBELOW', (0, 0), (-1, 0), 0.25, C_BORDER),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), _PAD),
                ('RIGHTPADDING', (0, 0), (-1, -1), _PAD),
                ('TOPPADDING', (0, 0), (0, 0), 6),
                ('BOTTOMPADDING', (0, 0), (0, 0), 4),
                ('TOPPADDING', (0, 1), (0, 1), 4),
                ('BOTTOMPADDING', (0, 1), (0, 1), 8),
            ],
        ),
    )
    return tbl


def _linha_evento_cce(dados: dict[str, Any], *, transmitido: bool) -> str:
    seq = str(dados.get('sequencia_evento') or dados.get('sequencia_prevista') or '—')
    if transmitido:
        return f'Evento CC-e — Sequência {seq}'
    return f'Evento CC-e — Sequência prevista {seq}'


def _cabecalho_fiscal_cce(dados: dict[str, Any], ph_small, ph_center) -> Table:
    logo_path = str(dados.get('emitente_logo_path') or '').strip() or None
    logo_cell = build_logo_cell(logo_path, ph_center=ph_center, header_spacious=True)

    if logo_path and os.path.isfile(logo_path):
        iw, ih = _read_logo_pixel_size(logo_path)
    else:
        iw, ih = 361.0, 198.0
    _lw, _lh, cw_logo, _rh = _logo_fit_proportional_box(
        iw,
        ih,
        max_draw_w=_HEADER_LOGO_MAX_DRAW_W,
        max_draw_h=_HEADER_LOGO_MAX_DRAW_H,
        pad_x=_HEADER_LOGO_PAD_X,
        pad_y=_HEADER_LOGO_PAD_Y,
    )

    p_em_rz = ParagraphStyle(
        'CceHdrRz', parent=ph_small, fontName='Helvetica-Bold', fontSize=7.35, leading=9.0, textColor=C_PRIMARY
    )
    p_em_ln = ParagraphStyle('CceHdrLn', parent=ph_small, fontSize=6.05, leading=7.45, textColor=C_MUTED)
    p_em_mu = ParagraphStyle('CceHdrMu', parent=ph_small, fontSize=5.95, leading=7.25, textColor=C_MUTED)

    mid_rows: list[list] = []
    rz = str(dados.get('emitente') or '').strip()
    if rz:
        mid_rows.append([Paragraph(escape(rz), p_em_rz)])
    cnpj = str(dados.get('emitente_cnpj') or '').strip()
    ie = str(dados.get('emitente_ie') or '').strip()
    doc_bits = [p for p in [cnpj, f'IE {ie}' if ie else ''] if p]
    if doc_bits:
        mid_rows.append([Paragraph(escape(' · '.join(doc_bits)), p_em_ln)])

    endereco = str(dados.get('emitente_endereco') or '').strip()
    cidade = str(dados.get('emitente_cidade') or '').strip()
    uf = str(dados.get('emitente_uf') or '').strip()
    cep = str(dados.get('emitente_cep') or '').strip()
    loc_bits = []
    if cidade or uf:
        loc_bits.append(f'{cidade}/{uf}' if cidade and uf else (cidade or uf))
    if cep:
        loc_bits.append(f'CEP {cep}')
    if endereco and endereco != '—':
        if loc_bits:
            endereco = f'{endereco} — {" · ".join(loc_bits)}'
        mid_rows.append([Paragraph(escape(endereco), p_em_ln)])
    elif loc_bits:
        mid_rows.append([Paragraph(escape(' · '.join(loc_bits)), p_em_ln)])

    tel = str(dados.get('emitente_telefone') or '').strip()
    email = str(dados.get('emitente_email') or '').strip()
    contato = ' · '.join(p for p in [tel, email] if p)
    if contato:
        mid_rows.append([Paragraph(escape(contato), p_em_mu)])
    if not mid_rows:
        mid_rows.append([Paragraph('—', p_em_mu)])

    cpad = 4 * mm
    g_logo_emit = 4.6 * mm
    g_emit_doc = 2.85 * mm
    w_inner = _inner_w()
    w_doc = max(66 * mm, min(88 * mm, w_inner * 0.30))
    w_log = cw_logo
    w_mid = w_inner - w_log - w_doc
    if w_mid < 38 * mm:
        w_doc = max(60 * mm, w_inner - w_log - 38 * mm)
        w_mid = w_inner - w_log - w_doc

    mid_stack = Table(mid_rows, colWidths=[w_mid])
    mid_stack.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 0.35 * mm),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 0.35 * mm),
            ],
        ),
    )

    transmitido = bool(dados.get('transmitido'))
    ambiente = escape(str(dados.get('ambiente_label') or ''))
    evento_linha = escape(_linha_evento_cce(dados, transmitido=transmitido))
    status_html = (
        '<font color="#15803d"><b>AUTORIZADA</b></font>'
        if transmitido
        else '<font color="#b45309"><b>PRÉVIA</b></font>'
    )

    p_kind = ParagraphStyle(
        'CceHdrKind', parent=ph_small, fontSize=6.95, leading=9, textColor=C_MUTED, alignment=TA_RIGHT
    )
    p_title = ParagraphStyle(
        'CceHdrTitle',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=13.5,
        textColor=C_BRAND_PRIMARY,
        alignment=TA_RIGHT,
    )
    p_evento = ParagraphStyle(
        'CceHdrEvento',
        parent=ph_small,
        fontName='Helvetica-Bold',
        fontSize=7.6,
        leading=9.5,
        textColor=C_SLATE_TEXT,
        alignment=TA_RIGHT,
    )
    p_meta = ParagraphStyle(
        'CceHdrMeta', parent=ph_small, fontSize=7.1, leading=9.5, textColor=C_MUTED, alignment=TA_RIGHT
    )

    right_rows = [
        [Paragraph('REPRESENTAÇÃO GRÁFICA DE CC-e', p_kind)],
        [Paragraph('Carta de Correção Eletrônica', p_title)],
        [Paragraph(evento_linha, p_evento)],
        [Paragraph(f'{ambiente} · {status_html}', p_meta)],
    ]

    right_stack = Table(right_rows, colWidths=[w_doc])
    right_stack.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 0),
            ],
        ),
    )

    band = Table([[logo_cell, mid_stack, right_stack]], colWidths=[w_log, w_mid, w_doc])
    band.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 0.45, C_SLATE_TEXT),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4 * mm),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4 * mm),
                ('LEFTPADDING', (0, 0), (0, 0), cpad),
                ('RIGHTPADDING', (0, 0), (0, 0), g_logo_emit / 2),
                ('LEFTPADDING', (1, 0), (1, 0), g_logo_emit / 2),
                ('RIGHTPADDING', (1, 0), (1, 0), g_emit_doc / 2),
                ('LEFTPADDING', (2, 0), (2, 0), g_emit_doc / 2),
                ('RIGHTPADDING', (2, 0), (2, 0), cpad),
            ],
        ),
    )
    return band


def _dados_barcode_cce(dados: dict[str, Any]) -> tuple[str, str, str]:
    valor = str(dados.get('barcode_valor') or '').strip()
    rotulo = str(dados.get('barcode_rotulo') or '').strip()
    texto = str(dados.get('barcode_texto_fmt') or '').strip()
    if valor:
        return valor, rotulo or 'Código de barras', texto or valor
    return resolver_barcode_cce(
        id_evento=str(dados.get('id_evento') or ''),
        chave_acesso=str(dados.get('chave_acesso') or ''),
    )


def _criar_desenho_codigo_barras(valor: str):
    bar_w = max(0.22 * mm, min(0.32 * mm, (_inner_w() * 0.85) / max(len(valor) * 11, 1)))
    return createBarcodeDrawing(
        'Code128',
        value=valor,
        barHeight=11 * mm,
        barWidth=bar_w,
        humanReadable=0,
    )


def _bloco_codigo_barras(dados: dict[str, Any], rotulo_style, texto_style) -> Table | None:
    valor, rotulo, texto_fmt = _dados_barcode_cce(dados)
    if not valor:
        return None

    drawing = _criar_desenho_codigo_barras(valor)
    max_w = _inner_w() - 24
    scale = min(1.0, max_w / max(float(drawing.width), 1.0))
    if scale < 1.0:
        drawing.width *= scale
        drawing.height *= scale
        drawing.scale(scale, scale)

    if rotulo == 'Chave de acesso da NF-e':
        texto_html = _html_chave_acesso(texto_fmt)
    else:
        texto_html = nobr(escape(texto_fmt))

    tbl = Table(
        [
            [drawing],
            [
                Paragraph(
                    f'<nobr><font color="#64748b"><b>{escape(rotulo)}</b></font></nobr>',
                    rotulo_style,
                ),
            ],
            [Paragraph(texto_html, texto_style)],
        ],
        colWidths=[_inner_w()],
    )
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.45, C_SLATE_TEXT),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (0, 0), 10),
                ('BOTTOMPADDING', (0, 0), (0, 0), 4),
                ('TOPPADDING', (0, 1), (0, 1), 6),
                ('BOTTOMPADDING', (0, 1), (0, 1), 2),
                ('TOPPADDING', (0, 2), (0, 2), 2),
                ('BOTTOMPADDING', (0, 2), (0, 2), 10),
            ],
        ),
    )
    return tbl


def _faixa_avisos(avisos: list[str], warn_style) -> list[Any]:
    if not avisos:
        return []
    html = ' &nbsp;|&nbsp; '.join(f'<b>{escape(av)}</b>' for av in avisos)
    tbl = Table([[Paragraph(html, warn_style)]], colWidths=[_inner_w()])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), _COR_AVISO_FUNDO),
                ('BOX', (0, 0), (-1, -1), 0.55, _COR_AVISO),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ],
        ),
    )
    return [tbl]


def _rodape_fiscal(texto: str, style) -> Table:
    tbl = Table([[Paragraph(escape(texto), style)]], colWidths=[_inner_w()])
    tbl.setStyle(
        TableStyle(
            [
                ('LINEABOVE', (0, 0), (-1, 0), 0.35, C_BORDER),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ],
        ),
    )
    return tbl


def _moldura_externa(partes: list[Any]) -> Table:
    """Moldura fiscal clássica envolvendo toda a área útil do documento."""
    rows = [[parte] for parte in partes]
    tbl = Table(rows, colWidths=[_CONTENT_W])
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), _MOLDURA_BORDER, C_SLATE_TEXT),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), _MOLDURA_PAD),
                ('RIGHTPADDING', (0, 0), (-1, -1), _MOLDURA_PAD),
                ('TOPPADDING', (0, 0), (0, 0), _MOLDURA_PAD),
                ('BOTTOMPADDING', (0, -1), (-1, -1), _MOLDURA_PAD),
                ('TOPPADDING', (0, 1), (-1, -2), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -2), 3),
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

    titulo_secao = ParagraphStyle(
        'CceTitSec',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        textColor=C_SLATE_TEXT,
        alignment=TA_LEFT,
    )
    rotulo = ParagraphStyle('CceRotulo', parent=ph_small, fontSize=7.5, leading=9)
    valor = ParagraphStyle('CceValor', parent=ph, fontSize=9.5, leading=12, textColor=C_PRIMARY)
    chave_lbl = ParagraphStyle('CceChaveLbl', parent=rotulo, fontSize=7.5, leading=9)
    chave = ParagraphStyle(
        'CceChave',
        parent=ph,
        fontName='Courier',
        fontSize=6.2,
        leading=8.5,
        textColor=C_PRIMARY,
        alignment=TA_LEFT,
    )
    legal_pre = ParagraphStyle(
        'CceLegalPre',
        parent=ph_small,
        fontSize=FONT_PDF_SMALL + 0.4,
        leading=10.5,
        textColor=C_SLATE_TEXT,
        alignment=TA_JUSTIFY,
    )
    correcao = ParagraphStyle(
        'CceCorrecao',
        parent=ph,
        fontName='Helvetica',
        fontSize=11.5,
        leading=15.5,
        textColor=C_PRIMARY,
        alignment=TA_LEFT,
    )
    correcao_titulo = ParagraphStyle(
        'CceCorrecaoTit',
        parent=titulo_secao,
        fontSize=9,
        textColor=C_SLATE_TEXT,
        alignment=TA_CENTER,
    )
    warn = ParagraphStyle(
        'CceWarn',
        parent=ph,
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=_COR_AVISO,
        leading=11.5,
        alignment=TA_CENTER,
    )
    legal_titulo = ParagraphStyle(
        'CceLegalTit', parent=ph_small, fontName='Helvetica-Bold', fontSize=8, textColor=C_SLATE_TEXT
    )
    legal_corpo = ParagraphStyle(
        'CceLegalCorpo', parent=ph_small, fontSize=FONT_PDF_SMALL + 0.2, leading=9.5, textColor=C_MUTED
    )
    rodape = ParagraphStyle(
        'CceRodape', parent=ph_small, fontSize=8, leading=10.5, textColor=C_MUTED, alignment=TA_CENTER
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

    partes: list[Any] = [
        _cabecalho_fiscal_cce(dados, ph_small, ph_center),
    ]
    partes.extend(_faixa_avisos(avisos, warn))

    barcode_valor, barcode_rotulo, _ = _dados_barcode_cce(dados) if transmitido else ('', '', '')
    incluir_chave_identificacao = not (
        transmitido and barcode_valor and barcode_rotulo == 'Chave de acesso da NF-e'
    )
    partes.extend(
        _bloco_identificacao_nfe(
            dados,
            titulo_secao,
            rotulo,
            valor,
            chave,
            chave_lbl,
            incluir_chave=incluir_chave_identificacao,
        ),
    )
    partes.append(
        _bloco_dados_evento_cc(
            dados,
            transmitido=transmitido,
            titulo_style=titulo_secao,
            rotulo_style=rotulo,
            valor_style=valor,
        ),
    )
    if transmitido:
        bloco_bc = _bloco_codigo_barras(dados, chave_lbl, chave)
        if bloco_bc is not None:
            partes.append(bloco_bc)
    partes.append(_bloco_texto_legal(legal_pre))
    partes.append(
        _caixa_correcoes(str(dados.get('texto_correcao') or ''), correcao_titulo, correcao),
    )
    partes.append(
        _bloco_limitacoes(
            str(dados.get('o_que_nao_pode_corrigir') or MSG_O_QUE_NAO_PODE_CORRIGIR),
            legal_titulo,
            legal_corpo,
        ),
    )
    partes.append(_rodape_fiscal(texto_rodape, rodape))

    story: list[Any] = [_moldura_externa(partes)]
    doc.build(story)
    return buf.getvalue()


def gerar_pdf_previa_cce(dados: dict[str, Any]) -> bytes:
    dados = {**dados, 'transmitido': False, 'modo': 'previa'}
    return gerar_pdf_representacao_cce(dados)


def gerar_pdf_comprovante_cce(dados: dict[str, Any]) -> bytes:
    dados = {**dados, 'transmitido': True, 'modo': 'autorizada'}
    return gerar_pdf_representacao_cce(dados)
