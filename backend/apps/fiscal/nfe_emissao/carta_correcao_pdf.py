"""Representação Gráfica de CC-e — layout fiscal único (prévia e autorizada). Não é DANFE."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.fiscal.nfe_emissao.carta_correcao_dados import MSG_O_QUE_NAO_PODE_CORRIGIR

_COR_BORDA = colors.HexColor('#334155')
_COR_CABECALHO = colors.HexColor('#1e293b')
_COR_FUNDO_LABEL = colors.HexColor('#f1f5f9')
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


def _bloco_titulo(titulo: str, style) -> Table:
    tbl = Table([[Paragraph(f'<b>{escape(titulo)}</b>', style)]], colWidths=[180 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), _COR_FUNDO_LABEL),
                ('BOX', (0, 0), (-1, -1), 0.5, _COR_BORDA),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ],
        ),
    )
    return tbl


def _grade_campos(linhas: list[tuple[str, str]], body_style, col_label: float = 42 * mm) -> Table:
    data = [[Paragraph(f'<b>{escape(k)}</b>', body_style), _p(v, body_style)] for k, v in linhas]
    tbl = Table(data, colWidths=[col_label, 180 * mm - col_label])
    tbl.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOX', (0, 0), (-1, -1), 0.5, _COR_BORDA),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0, 0), (0, -1), _COR_FUNDO_LABEL),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ],
        ),
    )
    return tbl


def _caixa_correcoes(texto: str, body_style) -> Table:
    par = _p(texto or '—', body_style)
    tbl = Table([[par]], colWidths=[180 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 1, _COR_BORDA),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('MINHEIGHT', (0, 0), (-1, -1), 55 * mm),
            ],
        ),
    )
    return tbl


def _faixa_avisos(avisos: list[str], warn_style) -> list[Any]:
    if not avisos:
        return []
    linhas = ''.join(f'<br/><b>{escape(av)}</b>' for av in avisos)
    tbl = Table([[Paragraph(linhas.lstrip('<br/>'), warn_style)]], colWidths=[180 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), _COR_AVISO_FUNDO),
                ('BOX', (0, 0), (-1, -1), 0.75, _COR_AVISO),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ],
        ),
    )
    return [tbl, Spacer(1, 6)]


def gerar_pdf_representacao_cce(dados: dict[str, Any]) -> bytes:
    """Layout único — variação apenas nos dados e avisos conforme prévia ou autorizada."""
    transmitido = bool(dados.get('transmitido'))
    homolog = bool(dados.get('homologacao'))

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    titulo_principal = ParagraphStyle(
        'CceTituloPrincipal',
        parent=styles['Heading1'],
        fontSize=13,
        leading=15,
        alignment=1,
        textColor=colors.white,
        spaceAfter=0,
    )
    subtitulo = ParagraphStyle(
        'CceSubtitulo',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#e2e8f0'),
    )
    emitente_hdr = ParagraphStyle(
        'CceEmitenteHdr',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=1,
        textColor=colors.HexColor('#cbd5e1'),
    )
    secao = ParagraphStyle('CceSecao', parent=styles['Heading3'], fontSize=9, spaceBefore=6, spaceAfter=3)
    body = ParagraphStyle('CceBody', parent=styles['Normal'], fontSize=8.5, leading=11)
    warn = ParagraphStyle('CceWarn', parent=styles['Normal'], fontSize=9, textColor=_COR_AVISO, leading=12)
    rodape = ParagraphStyle(
        'CceRodape',
        parent=styles['Normal'],
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#64748b'),
        alignment=1,
    )

    emitente = str(dados.get('emitente') or '')
    cnpj = str(dados.get('emitente_cnpj') or '')
    hdr_data = [
        [
            Paragraph('<b>Representação Gráfica de CC-e</b>', titulo_principal),
        ],
        [Paragraph('Carta de Correção Eletrônica', subtitulo)],
    ]
    if emitente:
        hdr_data.append([Paragraph(f'{escape(emitente)}' + (f' — CNPJ {escape(cnpj)}' if cnpj else ''), emitente_hdr)])
    cabecalho = Table(hdr_data, colWidths=[180 * mm])
    cabecalho.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), _COR_CABECALHO),
                ('BOX', (0, 0), (-1, -1), 0.5, _COR_BORDA),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (0, 0), 10),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
            ],
        ),
    )

    avisos: list[str] = []
    if not transmitido:
        avisos.append('PRÉVIA — NÃO TRANSMITIDA À SEFAZ')
    if homolog:
        avisos.append('HOMOLOGAÇÃO — SEM VALOR FISCAL')

    chave_fmt = str(dados.get('chave_acesso_fmt') or dados.get('chave_acesso') or '')
    campos_nfe = [
        ('Número da NF-e', str(dados.get('numero_nfe') or '')),
        ('Série', str(dados.get('serie_nfe') or '')),
        ('Chave de acesso', chave_fmt),
        ('Ambiente', str(dados.get('ambiente_label') or '')),
        ('Destinatário', str(dados.get('destinatario') or '')),
    ]

    if transmitido:
        seq = dados.get('sequencia_evento') or dados.get('sequencia_prevista') or ''
        status_ev = str(dados.get('status_evento') or 'Registrado na SEFAZ')
        campos_evento = [
            ('Sequência da CC-e', str(seq)),
            ('Status do evento', status_ev),
            ('Data/hora do registro', _fmt_datetime(dados.get('emitido_em'))),
            ('Protocolo', str(dados.get('protocolo') or '—')),
            ('ID do evento', str(dados.get('id_evento') or '—')),
            ('cStat / xMotivo', f"{dados.get('cstat') or '—'} — {dados.get('xmotivo') or '—'}"),
        ]
        texto_rodape = (
            'Evento registrado na SEFAZ conforme retorno eletrônico. '
            'Este documento é representação gráfica auxiliar — não substitui o XML do evento.'
        )
    else:
        campos_evento = [
            ('Sequência prevista', str(dados.get('sequencia_prevista') or '')),
            ('Status do evento', 'Prévia — não transmitida'),
            ('Prévia gerada em', _fmt_datetime(dados.get('previa_em'))),
        ]
        texto_rodape = 'Documento de prévia — não transmitido à SEFAZ. Não possui validade fiscal.'

    story: list[Any] = [cabecalho, Spacer(1, 8)]
    story.extend(_faixa_avisos(avisos, warn))
    story.append(_bloco_titulo('IDENTIFICAÇÃO DA NF-e', secao))
    story.append(_grade_campos(campos_nfe, body))
    story.append(Spacer(1, 6))
    story.append(_bloco_titulo('DADOS DO EVENTO', secao))
    story.append(_grade_campos(campos_evento, body))
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>CORREÇÕES A SEREM CONSIDERADAS</b>', secao))
    story.append(_caixa_correcoes(str(dados.get('texto_correcao') or ''), body))
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>Limitações da Carta de Correção</b>', secao))
    story.append(_p(str(dados.get('o_que_nao_pode_corrigir') or MSG_O_QUE_NAO_PODE_CORRIGIR), body))
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
