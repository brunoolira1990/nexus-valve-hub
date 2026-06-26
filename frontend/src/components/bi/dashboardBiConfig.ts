import type { DashboardBIModulo } from '@/hooks/useDashboardBI';
import type { DashboardPeriodo, DashboardPermissoes } from '@/services/api/dashboard';

const MESES_PT = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
];

const ENGLISH_MONTH = /^(january|february|march|april|may|june|july|august|september|october|november|december)/i;

/** Garante label de período em pt-BR (fallback se backend antigo). */
export function formatPeriodoLabel(periodo?: DashboardPeriodo | null | undefined): string {
  if (!periodo) return '';
  const { label, periodo: tipo, data_inicio, data_fim } = periodo;
  if (label && !ENGLISH_MONTH.test(label) && !/^\d{4}-\d{2}-\d{2}/.test(label)) {
    return label;
  }
  if (tipo === 'ultimos_30_dias') return 'Últimos 30 dias';
  if (tipo === 'ultimos_7_dias') return 'Últimos 7 dias';
  if (tipo === 'hoje') return 'Hoje';
  if (tipo === 'mes_atual' && data_inicio) {
    const d = new Date(`${data_inicio}T12:00:00`);
    return `${MESES_PT[d.getMonth()]}/${d.getFullYear()}`;
  }
  if (data_inicio && data_fim) {
    const fmt = (iso: string) => {
      const [y, m, day] = iso.split('-');
      return `${day}/${m}/${y}`;
    };
    return `${fmt(data_inicio)} a ${fmt(data_fim)}`;
  }
  return label || 'Período';
}

export const MODULO_HERO_KPI: Record<DashboardBIModulo, string | null> = {
  comercial: 'valor_aberto',
  fiscal: 'nfe_auth_prod',
  estoque: 'produtos_cadastrados',
  compras: 'valor_aberto_compras',
  qualidade: 'cq_emitidos',
  financeiro: 'saldo_previsto',
};

export const DASHBOARD_NAV_ITEMS: {
  label: string;
  path: string;
  modulo: DashboardBIModulo | null;
  permKey: keyof DashboardPermissoes | null;
}[] = [
  { label: 'Visão geral', path: '/dashboard', modulo: null, permKey: null },
  { label: 'Comercial', path: '/dashboard/comercial', modulo: 'comercial', permKey: 'pode_ver_comercial' },
  { label: 'Fiscal', path: '/dashboard/fiscal', modulo: 'fiscal', permKey: 'pode_ver_fiscal' },
  { label: 'Estoque', path: '/dashboard/estoque', modulo: 'estoque', permKey: 'pode_ver_estoque' },
  { label: 'Compras', path: '/dashboard/compras', modulo: 'compras', permKey: 'pode_ver_compras' },
  { label: 'Qualidade', path: '/dashboard/qualidade', modulo: 'qualidade', permKey: 'pode_ver_qualidade' },
  { label: 'Financeiro', path: '/dashboard/financeiro', modulo: 'financeiro', permKey: 'pode_ver_financeiro' },
];

export function navItemsForPermissoes(perms: DashboardPermissoes | null) {
  if (!perms) return [DASHBOARD_NAV_ITEMS[0]];
  return DASHBOARD_NAV_ITEMS.filter((item) => {
    if (!item.permKey) return true;
    return Boolean(perms[item.permKey]);
  });
}
