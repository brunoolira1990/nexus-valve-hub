"""
PDF NEXUS APP (ReportLab + Platypus).

- ``base``: documento, margens, rodapé em canvas, ``build_nexus_pdf_bytes``
- ``styles``: paleta + ``base_paragraph_styles``
- ``formatters``: moeda, decimal, data, CNPJ, telefone, ``nobr`` / ``money_nobr``
- ``components``: cabeçalho, blocos de parte, condições, card de item, resumo financeiro, etc.
"""

from apps.core.pdf.base import build_nexus_pdf_bytes, default_page_content_width, page_content_width

__all__ = [
    'build_nexus_pdf_bytes',
    'default_page_content_width',
    'page_content_width',
]
