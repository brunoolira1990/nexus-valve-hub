"""Definições de relatório operacional — ERP 4.0.14.7 (sem persistência em banco)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReportFilterLine:
    label: str
    value: str


@dataclass
class ReportMetric:
    label: str
    value: str


@dataclass
class ReportColumn:
    key: str
    title: str
    align: str = 'left'  # left | right | center
    width_mm: float | None = None


@dataclass
class ReportData:
    """Linhas da tabela principal (valores já formatados para exibição)."""

    rows: list[dict[str, str]] = field(default_factory=list)
    totals: dict[str, str] | None = None


@dataclass
class ReportDefinition:
    """Contrato único para renderização PDF em qualquer módulo."""

    module: str
    report_id: str
    title: str
    description: str = ''
    company_name: str = ''
    environment_label: str | None = None
    period_label: str | None = None
    filters: list[ReportFilterLine] = field(default_factory=list)
    metrics: list[ReportMetric] = field(default_factory=list)
    columns: list[ReportColumn] = field(default_factory=list)
    data: ReportData = field(default_factory=ReportData)
    notes: list[str] = field(default_factory=list)
    orientation: str = 'portrait'  # portrait | landscape
    filename: str = 'relatorio.pdf'
    generated_by: str = ''
    aviso_historico: str | None = None
