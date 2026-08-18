from __future__ import annotations

from io import BytesIO
from typing import Any

from django.db import transaction
from django.http import HttpResponse
from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.comercial.comercial_pdf_shared import pdf_http_response
from apps.expedicao.models import Expedicao, StatusExpedicao
from apps.expedicao.services.expedicao_service import ExpedicaoErro, sincronizar_numeracao_nfe


class ExpedicaoEtiquetaErro(ValueError):
    """Erro de regra de negócio para preparação/impressão de etiquetas."""


def _texto(valor: Any, fallback: str = '—', limite: int = 48) -> str:
    texto = str(valor or '').strip()
    if not texto:
        return fallback
    if len(texto) <= limite:
        return texto
    return f'{texto[: limite - 1]}…'


def _quantidade_volumes(expedicao: Expedicao) -> int:
    quantidade = int(expedicao.volumes or 0)
    if expedicao.nfe_saida_id:
        quantidade = max(quantidade, int(expedicao.nfe_saida.quantidade_volumes or 0))
    if quantidade < 1:
        raise ExpedicaoEtiquetaErro('Informe ao menos 1 volume antes de imprimir as etiquetas.')
    return quantidade


def _preparar_dados(expedicao: Expedicao) -> tuple[Expedicao, int]:
    if expedicao.status == StatusExpedicao.CANCELADO:
        raise ExpedicaoEtiquetaErro('Expedição cancelada não pode gerar etiquetas.')
    codigo = (expedicao.codigo or '').strip()
    if not codigo:
        raise ExpedicaoEtiquetaErro('A expedição não possui código operacional para a etiqueta.')

    try:
        sincronizar_numeracao_nfe(expedicao)
    except ExpedicaoErro as exc:
        raise ExpedicaoEtiquetaErro(str(exc)) from exc

    return expedicao, _quantidade_volumes(expedicao)


def _desenhar_linha(c: canvas.Canvas, rotulo: str, valor: str, y: float) -> float:
    c.setFont('Helvetica-Bold', 8.5)
    c.setFillColor(colors.HexColor('#374151'))
    c.drawString(8 * mm, y, f'{rotulo}:')
    c.setFont('Helvetica', 8.5)
    c.setFillColor(colors.black)
    c.drawString(31 * mm, y, _texto(valor, limite=38))
    return y - 7 * mm


def _renderizar_etiquetas(expedicao: Expedicao, quantidade: int) -> bytes:
    largura, altura = (100 * mm, 150 * mm)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=portrait((largura, altura)))
    nfe = expedicao.nfe_saida
    cliente_obj = expedicao.cliente if expedicao.cliente_id else None
    fornecedor_obj = expedicao.fornecedor if expedicao.fornecedor_id else None
    transportadora_obj = expedicao.transportadora if expedicao.transportadora_id else None
    cliente = getattr(cliente_obj, 'razao_social', '') or getattr(cliente_obj, 'nome', '')
    fornecedor = getattr(fornecedor_obj, 'razao_social', '') or getattr(fornecedor_obj, 'nome', '')
    transportadora = getattr(transportadora_obj, 'razao_social', '') or getattr(transportadora_obj, 'nome', '')
    nfe_numero = getattr(nfe, 'numero_nfe', '') or getattr(nfe, 'numero', '') if nfe else ''

    for indice in range(1, quantidade + 1):
        pdf.setFillColor(colors.HexColor('#0f172a'))
        pdf.rect(0, altura - 28 * mm, largura, 28 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont('Helvetica-Bold', 8)
        pdf.drawCentredString(largura / 2, altura - 9 * mm, 'NEXUS VÁLVULAS — ETIQUETA DE TRANSPORTE')
        pdf.setFont('Helvetica-Bold', 16)
        pdf.drawCentredString(largura / 2, altura - 20 * mm, _texto(expedicao.codigo, limite=24))

        pdf.setFillColor(colors.HexColor('#111827'))
        pdf.setFont('Helvetica-Bold', 13)
        pdf.drawString(8 * mm, altura - 38 * mm, f'VOLUME {indice}/{quantidade}')

        barcode = code128.Code128(expedicao.codigo, barHeight=12 * mm, barWidth=0.42 * mm)
        barcode.drawOn(pdf, 8 * mm, altura - 57 * mm)

        y = altura - 67 * mm
        y = _desenhar_linha(pdf, 'Cliente', cliente, y)
        y = _desenhar_linha(pdf, 'Fornecedor', fornecedor, y)
        y = _desenhar_linha(pdf, 'Transportadora', transportadora, y)
        y = _desenhar_linha(pdf, 'Motorista', expedicao.motorista_nome, y)
        y = _desenhar_linha(pdf, 'Placa', expedicao.placa_veiculo, y)
        y = _desenhar_linha(pdf, 'NF-e', nfe_numero, y)
        y = _desenhar_linha(pdf, 'Peso bruto', f'{expedicao.peso_bruto or "—"} kg', y)
        y = _desenhar_linha(pdf, 'Peso líquido', f'{expedicao.peso_liquido or "—"} kg', y)

        pdf.setStrokeColor(colors.HexColor('#cbd5e1'))
        pdf.line(8 * mm, 19 * mm, largura - 8 * mm, 19 * mm)
        pdf.setFillColor(colors.HexColor('#475569'))
        pdf.setFont('Helvetica', 7.5)
        pdf.drawCentredString(
            largura / 2,
            12 * mm,
            'Identificação operacional — reimpressão permitida sem gerar nova numeração',
        )
        pdf.showPage()

    pdf.save()
    return buffer.getvalue()


@transaction.atomic
def gerar_etiquetas_pdf(expedicao_id: int) -> HttpResponse:
    expedicao = (
        Expedicao.objects.select_for_update()
        .select_related('cliente', 'fornecedor', 'transportadora', 'nfe_saida')
        .get(pk=expedicao_id)
    )
    expedicao, quantidade = _preparar_dados(expedicao)
    pdf = _renderizar_etiquetas(expedicao, quantidade)
    return pdf_http_response(pdf, filename=f'etiquetas-{expedicao.codigo}.pdf')
