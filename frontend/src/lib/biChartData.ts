import type { BIChart, BIChartPonto } from '@/services/api/dashboard';

export function safeNumber(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function normalizeChartData(chart?: BIChart | null): BIChartPonto[] {
  if (!chart?.dados?.length) return [];
  return chart.dados.map((d) => ({
    label: String(d?.label ?? '').trim() || 'Sem classificação',
    valor: safeNumber(d?.valor),
  }));
}

export function chartRowsFromChart(chart: BIChart) {
  return normalizeChartData(chart).map((d) => ({
    name: d.label,
    value: d.valor,
  }));
}

export function hasChartData(rows: { value: number }[]): boolean {
  return rows.length > 0 && rows.some((r) => r.value > 0);
}
