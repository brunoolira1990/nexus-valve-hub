import io

from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from apps.fiscal.models import NFeSaida


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
