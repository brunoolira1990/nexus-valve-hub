"""Respostas HTTP para PDF de relatório (isolado do fiscal)."""

from __future__ import annotations

import re

from django.http import HttpResponse


def pdf_http_response(content: bytes, *, filename: str) -> HttpResponse:
    safe = re.sub(r'[/\\]+', '-', filename or 'relatorio').strip() or 'relatorio'
    if not safe.lower().endswith('.pdf'):
        safe = f'{safe}.pdf'
    resp = HttpResponse(content, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{safe}"'
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp['Pragma'] = 'no-cache'
    resp['Expires'] = '0'
    resp['Vary'] = 'Authorization, Cookie'
    return resp
