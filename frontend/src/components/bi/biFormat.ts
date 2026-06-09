import type { BIKpi } from '@/services/api/dashboard';

export function formatBiMoeda(value: string | number | undefined) {
  const n = Number(value ?? 0);
  if (Number.isNaN(n)) return String(value ?? '—');
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function formatBiNumero(value: string | number | undefined) {
  const n = Number(value ?? 0);
  if (Number.isNaN(n)) return String(value ?? '—');
  return n.toLocaleString('pt-BR');
}

export function formatKpiValor(kpi: BIKpi) {
  if (kpi.formato === 'moeda') return formatBiMoeda(kpi.valor);
  if (kpi.formato === 'numero') return formatBiNumero(kpi.valor);
  return String(kpi.valor ?? '—');
}

export function formatRankingValor(valor: string, formato?: string) {
  if (formato === 'moeda') return formatBiMoeda(valor);
  const n = Number(valor);
  if (!Number.isNaN(n) && /^\d+(\.\d+)?$/.test(String(valor).trim())) {
    return formatBiNumero(n);
  }
  return valor;
}

export const BI_CHART_COLORS = [
  'hsl(var(--primary))',
  'hsl(210 70% 52%)',
  'hsl(160 55% 42%)',
  'hsl(38 92% 50%)',
  'hsl(280 55% 55%)',
  'hsl(0 72% 55%)',
  'hsl(195 65% 45%)',
  'hsl(25 80% 52%)',
];
