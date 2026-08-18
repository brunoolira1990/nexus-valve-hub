from __future__ import annotations

from io import BytesIO
from typing import Any

from django.db import transaction
from django.http import HttpResponse
from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from PIL import Image, ImageOps
from reportlab.lib.utils import ImageReader
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


def _imagem_logo(empresa: Any) -> ImageReader | None:
    if not empresa:
        return None
    arquivo = getattr(empresa, 'logotipo', None)
    if not arquivo or not getattr(arquivo, 'name', ''):
        return None
    try:
        arquivo.open('rb')
        dados = arquivo.read()
    except (AttributeError, OSError, ValueError):
        return None
    finally:
        try:
            arquivo.close()
        except (AttributeError, OSError, ValueError):
            pass
    if not dados:
        return None
    try:
        imagem = Image.open(BytesIO(dados))
        alpha = imagem.getchannel('A') if 'A' in imagem.getbands() else None
        imagem = ImageOps.grayscale(imagem.convert('RGB'))
        if alpha is not None:
            imagem.putalpha(alpha)
        return ImageReader(imagem)
    except (OSError, ValueError, TypeError):
        return None


def _desenhar_logo(c: canvas.Canvas, empresa: Any, altura: float) -> None:
    imagem = _imagem_logo(empresa)
    if imagem is None:
        return
    largura_original, altura_original = imagem.getSize()
    if not largura_original or not altura_original:
        return
    largura_maxima = 16 * mm
    altura_maxima = 17 * mm
    escala = min(largura_maxima / largura_original, altura_maxima / altura_original)
    c.drawImage(
        imagem,
        4 * mm,
        altura - 22 * mm,
        width=largura_original * escala,
        height=altura_original * escala,
        preserveAspectRatio=True,
        mask='auto',
    )


def _desenhar_linha(c: canvas.Canvas, rotulo: str, valor: str, y: float) -> float:
    c.setFont('Helvetica-Bold', 8.5)
    c.setFillColor(colors.black)
    c.drawString(5 * mm, y, f'{rotulo}:')
    c.setFont('Helvetica', 8.5)
    c.setFillColor(colors.black)
    c.drawString(30 * mm, y, _texto(valor, limite=38))
    return y - 7 * mm


def _renderizar_etiquetas(expedicao: Expedicao, quantidade: int) -> bytes:
    largura, altura = (62 * mm, 100 * mm)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=portrait((largura, altura)))
    nfe = expedicao.nfe_saida
    empresa = getattr(nfe, 'empresa_emitente', None) if nfe else None
    empresa_nome = (
        getattr(empresa, 'nome_fantasia', '')
        or getattr(empresa, 'razao_social', '')
        or 'NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS'
    )
    empresa_cnpj = getattr(empresa, 'cnpj', '') if empresa else ''
    cliente_obj = expedicao.cliente if expedicao.cliente_id else None
    transportadora_obj = expedicao.transportadora if expedicao.transportadora_id else None
    cliente = getattr(cliente_obj, 'razao_social', '') or getattr(cliente_obj, 'nome', '')
    transportadora = getattr(transportadora_obj, 'razao_social', '') or getattr(transportadora_obj, 'nome', '')
    nfe_numero = (getattr(nfe, 'numero_nfe', '') or getattr(nfe, 'numero', '')) if nfe else ''
    nfe_numeracao_volumes = getattr(nfe, 'numeracao_volumes', '') if nfe else ''

    for indice in range(1, quantidade + 1):
        pdf.setFillColor(colors.white)
        pdf.rect(0, altura - 27 * mm, largura, 27 * mm, fill=1, stroke=0)
        _desenhar_logo(pdf, empresa, altura)
        pdf.setFillColor(colors.black)
        pdf.setFont('Helvetica-Bold', 5.8)
        pdf.drawString(23 * mm, altura - 6 * mm, _texto(empresa_nome, limite=31))
        pdf.setFillColor(colors.black)
        pdf.setFont('Helvetica', 5.4)
        pdf.drawString(
            23 * mm,
            altura - 10 * mm,
            _texto(f'CNPJ {empresa_cnpj}', limite=31) if empresa_cnpj else 'OPERAÇÃO LOGÍSTICA',
        )
        pdf.setFillColor(colors.black)
        pdf.setFont('Helvetica-Bold', 7.8)
        pdf.drawCentredString(largura / 2, altura - 21.5 * mm, _texto(expedicao.codigo, limite=23))
        pdf.setStrokeColor(colors.black)
        pdf.setLineWidth(1.2)
        pdf.line(5 * mm, altura - 27 * mm, largura - 5 * mm, altura - 27 * mm)

        pdf.setFillColor(colors.black)
        pdf.setFont('Helvetica-Bold', 9.5)
        pdf.drawString(5 * mm, altura - 33 * mm, f'VOLUME {indice}/{quantidade}')

        barcode = code128.Code128(
            expedicao.codigo,
            barHeight=8 * mm,
            barWidth=0.32 * mm,
            humanReadable=False,
        )
        barcode.drawOn(pdf, 5 * mm, altura - 46 * mm)

        y = altura - 53 * mm
        y = _desenhar_linha(pdf, 'Cliente', cliente, y)
        y = _desenhar_linha(pdf, 'Transportadora', transportadora, y)
        y = _desenhar_linha(pdf, 'Motorista', expedicao.motorista_nome, y)
        y = _desenhar_linha(pdf, 'Placa', expedicao.placa_veiculo, y)
        y = _desenhar_linha(pdf, 'NF-e', nfe_numero, y)
        y = _desenhar_linha(pdf, 'Vol. NF-e', nfe_numeracao_volumes, y)
        y = _desenhar_linha(pdf, 'Peso bruto', f'{expedicao.peso_bruto or "—"} kg', y)
        y = _desenhar_linha(pdf, 'Peso líquido', f'{expedicao.peso_liquido or "—"} kg', y)

        pdf.showPage()

    pdf.save()
    return buffer.getvalue()


@transaction.atomic
def gerar_etiquetas_pdf(expedicao_id: int) -> HttpResponse:
    # A sincronização de NF-e em rascunho possui seu próprio bloqueio
    # transacional. Não usar FOR UPDATE junto a relações opcionais: no
    # PostgreSQL isso tenta bloquear o lado nullable de LEFT OUTER JOIN.
    expedicao = (
        Expedicao.objects.select_related(
            'cliente', 'fornecedor', 'transportadora', 'nfe_saida__empresa_emitente'
        )
        .get(pk=expedicao_id)
    )
    expedicao, quantidade = _preparar_dados(expedicao)
    pdf = _renderizar_etiquetas(expedicao, quantidade)
    return pdf_http_response(pdf, filename=f'etiquetas-{expedicao.codigo}.pdf')
