import type { DashboardModuloBI, DashboardPeriodo } from '@/services/api/dashboard';

export const EMPTY_DASHBOARD_PERIODO: DashboardPeriodo = {
  data_inicio: '',
  data_fim: '',
  label: '',
  periodo: 'mes_atual',
  empresa_id: null,
  status: null,
};

export const EMPTY_DASHBOARD_MODULO: DashboardModuloBI = {
  modulo: '',
  periodo: EMPTY_DASHBOARD_PERIODO,
  kpis: [],
  graficos: [],
  rankings: [],
  alertas: [],
  ultimos: [],
  links: [],
};
