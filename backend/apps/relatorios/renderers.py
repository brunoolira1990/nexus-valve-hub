"""Renderers DRF para respostas binárias de relatório (isolado do fiscal/DANFE)."""

from rest_framework.renderers import BaseRenderer


class PdfBytesRenderer(BaseRenderer):
    """Aceita Accept: application/pdf e devolve bytes sem serializar JSON."""

    media_type = 'application/pdf'
    format = 'pdf'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b''
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        return b''
