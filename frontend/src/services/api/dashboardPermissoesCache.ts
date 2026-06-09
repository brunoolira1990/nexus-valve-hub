import type { DashboardPermissoes } from './dashboard';

export const EMPTY_DASHBOARD_PERMISSOES: DashboardPermissoes = {
  pode_ver_comercial: false,
  pode_ver_fiscal: false,
  pode_ver_estoque: false,
  pode_ver_compras: false,
  pode_ver_qualidade: false,
  pode_ver_financeiro: false,
  pode_ver_consolidado: false,
};

let cached: DashboardPermissoes | null = null;
let inflight: Promise<DashboardPermissoes> | null = null;

export function getDashboardPermissoesCached() {
  return cached;
}

export function setDashboardPermissoesCached(p: DashboardPermissoes | null) {
  cached = p;
}

export function getDashboardPermissoesInflight() {
  return inflight;
}

export function setDashboardPermissoesInflight(p: Promise<DashboardPermissoes> | null) {
  inflight = p;
}

export function clearDashboardPermissoesCache() {
  cached = null;
  inflight = null;
}
