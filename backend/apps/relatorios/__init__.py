"""
Motor central de relatórios PDF do Nexus (gerencial/operacional).

IMPORTANTE: Este pacote é independente do motor fiscal/DANFE.
Não importar apps.fiscal.danfe_render, BrazilFiscalReport nem templates de DANFE.
PDFs fiscais continuam no fluxo fiscal próprio (BFR).
"""

from apps.relatorios.definitions import (
    ReportColumn,
    ReportData,
    ReportDefinition,
    ReportFilterLine,
    ReportMetric,
)
from apps.relatorios.export_service import ReportExportService

__all__ = [
    'ReportColumn',
    'ReportData',
    'ReportDefinition',
    'ReportExportService',
    'ReportFilterLine',
    'ReportMetric',
]
