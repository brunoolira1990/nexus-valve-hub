"""PDF prévia/comprovante — Carta de Correção (CC-e). Não é DANFE."""

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


def _p(text: str, style) -> Paragraph:
    return Paragraph(escape(text).replace('\n', '<br/>'), style)


def _fmt_datetime(iso: str | None) -> str:
    if not iso:
        return '—'
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return str(iso)[:19]


def _tabela_campos(linhas: list[tuple[str, str]], body_style) -> Table:
    data = [[Paragraph(f'<b>{escape(k)}</b>', body_style), _p(v, body_style)] for k, v in linhas]
    tbl = Table(data, colWidths=[45 * mm, 135 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8fafc')),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ],
        ),
    )
    return tbl


def _gerar_pdf_cce(*, titulo: str, avisos: list[str], campos: list[tuple[str, str]], texto: str, rodape: str) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle('CceTitle', parent=styles['Heading1'], fontSize=14, spaceAfter=8)
    warn = ParagraphStyle('CceWarn', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#b45309'), spaceAfter=4)
    body = ParagraphStyle('CceBody', parent=styles['Normal'], fontSize=9, leading=12)
    label = ParagraphStyle('CceLabel', parent=styles['Heading3'], fontSize=10, spaceBefore=8, spaceAfter=4)

    story: list[Any] = [Paragraph(escape(titulo), title)]
    for av in avisos:
        story.append(Paragraph(f'<b>{escape(av)}</b>', warn))
    story.append(Spacer(1, 6))
    story.append(_tabela_campos(campos, body))
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>Texto da correção</b>', label))
    story.append(_p(texto or '—', body))
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>O que a CC-e não pode corrigir</b>', label))
    story.append(_p(rodape, body))
    doc.build(story)
    return buf.getvalue()


def gerar_pdf_previa_cce(dados: dict[str, Any]) -> bytes:
    avisos = ['PRÉVIA — NÃO TRANSMITIDA À SEFAZ']
    if dados.get('homologacao'):
        avisos.append('HOMOLOGAÇÃO — SEM VALOR FISCAL')
    campos = [
        ('Ambiente', str(dados.get('ambiente_label') or '')),
        ('Emitente', str(dados.get('emitente') or '')),
        ('CNPJ emitente', str(dados.get('emitente_cnpj') or '')),
        ('Destinatário', str(dados.get('destinatario') or '')),
        ('NF-e nº', str(dados.get('numero_nfe') or '')),
        ('Série', str(dados.get('serie_nfe') or '')),
        ('Chave de acesso', str(dados.get('chave_acesso') or '')),
        ('Sequência prevista', str(dados.get('sequencia_prevista') or '')),
        ('Prévia gerada em', _fmt_datetime(dados.get('previa_em'))),
    ]
    return _gerar_pdf_cce(
        titulo='Prévia da Carta de Correção Eletrônica — CC-e',
        avisos=avisos,
        campos=campos,
        texto=str(dados.get('texto_correcao') or ''),
        rodape=MSG_O_QUE_NAO_PODE_CORRIGIR,
    )


def gerar_pdf_comprovante_cce(dados: dict[str, Any]) -> bytes:
    avisos = ['COMPROVANTE — EVENTO TRANSMITIDO À SEFAZ']
    if dados.get('homologacao'):
        avisos.append('HOMOLOGAÇÃO — SEM VALOR FISCAL')
    campos = [
        ('Ambiente', str(dados.get('ambiente_label') or '')),
        ('Emitente', str(dados.get('emitente') or '')),
        ('Destinatário', str(dados.get('destinatario') or '')),
        ('NF-e nº', str(dados.get('numero_nfe') or '')),
        ('Série', str(dados.get('serie_nfe') or '')),
        ('Chave de acesso', str(dados.get('chave_acesso') or '')),
        ('Sequência do evento', str(dados.get('sequencia_evento') or '')),
        ('cStat', str(dados.get('cstat') or '')),
        ('xMotivo', str(dados.get('xmotivo') or '')),
        ('Protocolo', str(dados.get('protocolo') or '')),
        ('Transmissão em', _fmt_datetime(dados.get('emitido_em'))),
        ('Usuário', str(dados.get('usuario_nome') or '—')),
    ]
    return _gerar_pdf_cce(
        titulo='Comprovante da Carta de Correção Eletrônica — CC-e',
        avisos=avisos,
        campos=campos,
        texto=str(dados.get('texto_correcao') or ''),
        rodape=MSG_O_QUE_NAO_PODE_CORRIGIR,
    )
