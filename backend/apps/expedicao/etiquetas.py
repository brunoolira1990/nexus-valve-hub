from __future__ import annotations

from io import BytesIO
from typing import Any

from django.db import transaction
from django.http import HttpResponse
from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image, ImageChops, ImageOps
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


def _texto_na_largura(
    valor: Any,
    fonte: str,
    tamanho: float,
    largura_maxima: float,
    fallback: str = '—',
) -> str:
    texto = _texto(valor, fallback=fallback, limite=256)
    if stringWidth(texto, fonte, tamanho) <= largura_maxima:
        return texto
    sufixo = '…'
    while texto and stringWidth(f'{texto}{sufixo}', fonte, tamanho) > largura_maxima:
        texto = texto[:-1]
    return f'{texto.rstrip()}{sufixo}' if texto else sufixo


def _quebrar_texto(
    valor: Any,
    fonte: str,
    tamanho: float,
    largura_maxima: float,
    max_linhas: int = 2,
    fallback: str = '—',
) -> list[str]:
    texto = _texto(valor, fallback=fallback, limite=256)
    palavras = texto.split()
    linhas: list[str] = []
    atual = ''
    for palavra in palavras:
        candidato = f'{atual} {palavra}'.strip()
        if not atual and stringWidth(candidato, fonte, tamanho) > largura_maxima:
            linhas.append(_texto_na_largura(candidato, fonte, tamanho, largura_maxima))
            continue
        if stringWidth(candidato, fonte, tamanho) <= largura_maxima:
            atual = candidato
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    if not linhas:
        return [fallback]
    if len(linhas) <= max_linhas:
        return linhas
    preservadas = linhas[: max_linhas - 1]
    restante = ' '.join(linhas[max_linhas - 1 :])
    preservadas.append(_texto_na_largura(restante, fonte, tamanho, largura_maxima))
    return preservadas


def _quantidade_volumes(expedicao: Expedicao) -> int:
    quantidade = int(expedicao.volumes or 0)
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
    dados = b''
    arquivo = getattr(empresa, 'logotipo', None) if empresa else None
    if arquivo and getattr(arquivo, 'name', ''):
        try:
            arquivo.open('rb')
            dados = arquivo.read()
        except (AttributeError, OSError, ValueError):
            dados = b''
        finally:
            try:
                arquivo.close()
            except (AttributeError, OSError, ValueError):
                pass

    if not dados:
        return None
    try:
        imagem = Image.open(BytesIO(dados)).convert('RGBA')
        alpha = imagem.getchannel('A')
        rgb = ImageOps.grayscale(imagem.convert('RGB'))
        fundo = Image.new('L', rgb.size, 255)
        bbox = ImageChops.difference(rgb, fundo).getbbox()
        if bbox:
            margem = max(2, round(min(rgb.size) * 0.025))
            bbox = (
                max(0, bbox[0] - margem),
                max(0, bbox[1] - margem),
                min(rgb.width, bbox[2] + margem),
                min(rgb.height, bbox[3] + margem),
            )
            rgb = rgb.crop(bbox)
            alpha = alpha.crop(bbox)
        rgb = ImageOps.autocontrast(rgb)
        # A QL-800 imprime em monocromático: transforma as cores da marca
        # em preto sólido, preservando o alpha e evitando que o azul/laranja
        # apareçam como cinza fraco ou desapareçam no rolo térmico.
        rgb = rgb.point(lambda pixel: 0 if pixel < 210 else 255)
        rgb.putalpha(alpha)
        return ImageReader(rgb)
    except (OSError, ValueError, TypeError):
        return None


def _desenhar_logo(c: canvas.Canvas, empresa: Any, altura: float) -> None:
    box_x = 5 * mm
    box_y = altura - 19 * mm
    box_w = 22 * mm
    box_h = 14 * mm
    imagem = _imagem_logo(empresa)
    if imagem is not None:
        largura_original, altura_original = imagem.getSize()
        if largura_original and altura_original:
            escala = min((box_w - 1.2 * mm) / largura_original, (box_h - 1.2 * mm) / altura_original)
            largura = largura_original * escala
            altura_logo = altura_original * escala
            c.drawImage(
                imagem,
                box_x + (box_w - largura) / 2,
                box_y + (box_h - altura_logo) / 2,
                width=largura,
                height=altura_logo,
                preserveAspectRatio=True,
                mask='auto',
            )
            return

    # Fallback vetorial, sempre monocromático e sem depender de outro cadastro.
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.black)
    c.setLineWidth(0.8)
    marca_x = box_x + 1.0 * mm
    marca_y = box_y + 6.0 * mm
    marca_w = 4.8 * mm
    marca_h = 6.0 * mm
    c.line(marca_x, marca_y, marca_x, marca_y + marca_h)
    c.line(marca_x, marca_y + marca_h, marca_x + marca_w, marca_y)
    c.line(marca_x + marca_w, marca_y, marca_x + marca_w, marca_y + marca_h)
    c.setFont('Helvetica-Bold', 8.4)
    c.drawString(marca_x + 6.1 * mm, marca_y + 1.0 * mm, 'NEXUS')
    c.setFont('Helvetica-Bold', 3.9)
    c.drawString(marca_x + 6.1 * mm, marca_y - 2.0 * mm, 'VÁLVULAS E CONEXÕES')


def _desenhar_linha(
    c: canvas.Canvas,
    rotulo: str,
    valor: str,
    y: float,
    quebrar: bool = False,
) -> float:
    fonte_rotulo = 'Helvetica-Bold'
    fonte_valor = 'Helvetica'
    tamanho = 7.6
    x_valor = 29 * mm
    largura_valor = 62 * mm - x_valor - 5 * mm
    linhas = (
        _quebrar_texto(valor, fonte_valor, tamanho, largura_valor, max_linhas=2)
        if quebrar
        else [_texto_na_largura(valor, fonte_valor, tamanho, largura_valor)]
    )
    c.setFont(fonte_rotulo, tamanho)
    c.setFillColor(colors.black)
    c.drawString(5 * mm, y, f'{rotulo}:')
    c.setFont(fonte_valor, tamanho)
    c.setFillColor(colors.black)
    for indice, linha in enumerate(linhas):
        c.drawString(x_valor, y - indice * 4.2 * mm, linha)
    espacamento = len(linhas) * 4.2 * mm if len(linhas) > 1 else 5.5 * mm
    return y - espacamento


def _desenhar_linha_largura(
    c: canvas.Canvas,
    rotulo: str,
    valor: str,
    y: float,
) -> float:
    """Desenha rótulo e valor em linhas próprias, usando toda a largura útil."""
    margem = 5 * mm
    largura_util = 62 * mm - (2 * margem)
    fonte_rotulo = 'Helvetica-Bold'
    fonte_valor = 'Helvetica'
    tamanho_rotulo = 6.4
    tamanho_valor = 7.1
    linhas = _quebrar_texto(
        valor,
        fonte_valor,
        tamanho_valor,
        largura_util,
        max_linhas=2,
    )
    c.setFillColor(colors.black)
    c.setFont(fonte_rotulo, tamanho_rotulo)
    c.drawString(margem, y, f'{rotulo}:')
    c.setFont(fonte_valor, tamanho_valor)
    for indice, linha in enumerate(linhas):
        c.drawString(margem, y - (4.0 + indice * 3.8) * mm, linha)
    return y - ((len(linhas) + 1) * 4.0 + 1.0) * mm


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
    empresa_telefone = getattr(empresa, 'telefone', '') if empresa else ''
    empresa_email = str(getattr(empresa, 'email', '') or '').strip() if empresa else ''
    empresa_site = str(getattr(empresa, 'site', '') or '').strip() if empresa else ''
    cliente_obj = expedicao.cliente if expedicao.cliente_id else None
    transportadora_obj = expedicao.transportadora if expedicao.transportadora_id else None
    cliente = getattr(cliente_obj, 'razao_social', '') or getattr(cliente_obj, 'nome', '')
    transportadora = getattr(transportadora_obj, 'razao_social', '') or getattr(transportadora_obj, 'nome', '')
    nfe_numero = (getattr(nfe, 'numero_nfe', '') or getattr(nfe, 'numero', '')) if nfe else ''
    nfe_numeracao_volumes = getattr(nfe, 'numeracao_volumes', '') if nfe else ''

    header_x = 30 * mm
    header_width = largura - header_x - 5 * mm
    header_lines = _quebrar_texto(
        empresa_nome,
        'Helvetica-Bold',
        4.8,
        header_width,
        max_linhas=2,
    )
    contatos = [
        (f'CNPJ {empresa_cnpj}' if empresa_cnpj else 'OPERAÇÃO LOGÍSTICA', True),
        (f'Tel. {empresa_telefone}', bool(empresa_telefone)),
        (f'E-mail {empresa_email}', bool(empresa_email)),
        (f'Site {empresa_site}', bool(empresa_site)),
    ]
    # O divisor acompanha o último contato. A altura mínima preserva o layout
    # original quando os campos opcionais não estão preenchidos.
    linha_contato_final = 11.5 + (len(header_lines) - 1) * 3.2
    linha_contato_final += sum(3.1 for _texto_contato, presente in contatos if presente)
    tamanho_contato = 4.2
    header_bottom_mm = max(27.0, linha_contato_final + 1.4)
    titulo_y_mm = header_bottom_mm + 3.5
    volume_y_mm = header_bottom_mm + 10.0
    barcode_y_mm = header_bottom_mm + 23.0
    dados_y_mm = header_bottom_mm + 26.0

    for indice in range(1, quantidade + 1):
        pdf.setFillColor(colors.white)
        pdf.rect(
            0,
            altura - header_bottom_mm * mm,
            largura,
            header_bottom_mm * mm,
            fill=1,
            stroke=0,
        )
        _desenhar_logo(pdf, empresa, altura)
        pdf.setFillColor(colors.black)
        pdf.setFont('Helvetica-Bold', 4.8)
        for linha, texto_header in enumerate(header_lines):
            pdf.drawString(header_x, altura - (6.2 + linha * 3.2) * mm, texto_header)

        pdf.setFont('Helvetica', tamanho_contato)
        linha_contato = 11.5 + (len(header_lines) - 1) * 3.2
        for texto_contato, presente in contatos:
            if not presente:
                continue
            pdf.drawString(
                header_x,
                altura - linha_contato * mm,
                _texto_na_largura(
                    texto_contato,
                    'Helvetica',
                    tamanho_contato,
                    header_width,
                ),
            )
            linha_contato += 3.1

        pdf.setStrokeColor(colors.black)
        pdf.setLineWidth(0.8)
        pdf.line(
            5 * mm,
            altura - header_bottom_mm * mm,
            largura - 5 * mm,
            altura - header_bottom_mm * mm,
        )

        # Título da etiqueta como elemento próprio, centralizado abaixo do
        # cabeçalho da empresa e acima da identificação física do volume.
        pdf.setFillColor(colors.black)
        pdf.setFont('Helvetica-Bold', 5.2)
        pdf.drawCentredString(largura / 2, altura - titulo_y_mm * mm, 'ETIQUETA DE TRANSPORTE')

        pdf.setFont('Helvetica-Bold', 9.5)
        pdf.drawString(5 * mm, altura - volume_y_mm * mm, f'VOLUME {indice}/{quantidade}')

        barcode = code128.Code128(
            expedicao.codigo,
            barHeight=8 * mm,
            barWidth=0.25 * mm,
            quiet=False,
            humanReadable=False,
        )
        barcode_x = (largura - barcode.width) / 2
        barcode.drawOn(pdf, barcode_x, altura - barcode_y_mm * mm)

        y = altura - dados_y_mm * mm
        y = _desenhar_linha_largura(pdf, 'Cliente', cliente, y)
        y = _desenhar_linha_largura(pdf, 'Transportadora', transportadora, y)
        y = _desenhar_linha(pdf, 'NF-e', nfe_numero, y)
        y = _desenhar_linha(pdf, 'Numeração', nfe_numeracao_volumes, y)
        peso = expedicao.peso_bruto or expedicao.peso_liquido or '—'
        y = _desenhar_linha(pdf, 'Peso', f'{peso} kg', y)

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
