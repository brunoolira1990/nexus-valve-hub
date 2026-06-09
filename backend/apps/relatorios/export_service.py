"""
Serviço de exportação PDF de relatórios operacionais.

O motor de relatórios PDF é independente do motor fiscal/DANFE.
"""

from __future__ import annotations

import logging

from apps.relatorios.definitions import ReportDefinition
from apps.relatorios.renderer import ReportPdfRenderer

logger = logging.getLogger(__name__)


class ReportExportService:
    """Gera PDF sob demanda a partir de uma definição de relatório."""

    def __init__(self, renderer: ReportPdfRenderer | None = None):
        self._renderer = renderer or ReportPdfRenderer()

    def export_pdf(self, definition: ReportDefinition) -> bytes:
        logger.info(
            'relatorio_pdf_gerado module=%s report_id=%s filename=%s',
            definition.module,
            definition.report_id,
            definition.filename,
        )
        return self._renderer.render(definition)
