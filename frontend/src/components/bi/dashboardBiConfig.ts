import type { LucideIcon } from 'lucide-react';
import {
  DollarSign,
  FileText,
  LayoutDashboard,
  Package,
  ShieldCheck,
  ShoppingCart,
  Truck,
  Wallet,
} from 'lucide-react';
import type { DashboardBIModulo } from '@/hooks/useDashboardBI';
import type {
  BIKpi,
  DashboardPeriodo,
  DashboardPermissoes,
} from '@/services/api/dashboard';

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
  expedicao: 'exp_em_andamento',
  compras: 'valor_aberto_compras',
  qualidade: 'cq_rastreabilidade_pendente',
  financeiro: 'saldo_previsto',
};

export const DASHBOARD_NAV_ITEMS: {
  label: string;
  path: string;
  modulo: DashboardBIModulo | null;
  permKey: keyof DashboardPermissoes | null;
  icon: LucideIcon;
}[] = [
  { label: 'Visão geral', path: '/dashboard', modulo: null, permKey: null, icon: LayoutDashboard },
  { label: 'Comercial', path: '/dashboard/comercial', modulo: 'comercial', permKey: 'pode_ver_comercial', icon: DollarSign },
  { label: 'Compras', path: '/dashboard/compras', modulo: 'compras', permKey: 'pode_ver_compras', icon: ShoppingCart },
  { label: 'Estoque', path: '/dashboard/estoque', modulo: 'estoque', permKey: 'pode_ver_estoque', icon: Package },
  { label: 'Expedição', path: '/dashboard/expedicao', modulo: 'expedicao', permKey: 'pode_ver_expedicao', icon: Truck },
  { label: 'Fiscal', path: '/dashboard/fiscal', modulo: 'fiscal', permKey: 'pode_ver_fiscal', icon: FileText },
  { label: 'Qualidade', path: '/dashboard/qualidade', modulo: 'qualidade', permKey: 'pode_ver_qualidade', icon: ShieldCheck },
  { label: 'Financeiro', path: '/dashboard/financeiro', modulo: 'financeiro', permKey: 'pode_ver_financeiro', icon: Wallet },
];

export function navItemsForPermissoes(perms: DashboardPermissoes | null) {
  if (!perms) return [DASHBOARD_NAV_ITEMS[0]];
  return DASHBOARD_NAV_ITEMS.filter((item) => {
    if (!item.permKey) return true;
    return Boolean(perms[item.permKey]);
  });
}

/** Ícone do card-resumo de cada módulo. */
export const MODULO_ICONE: Record<DashboardBIModulo, LucideIcon> = {
  comercial: DollarSign,
  compras: ShoppingCart,
  estoque: Package,
  expedicao: Truck,
  fiscal: FileText,
  qualidade: ShieldCheck,
  financeiro: Wallet,
};

export const MODULO_ICONE_COR: Record<DashboardBIModulo, string> = {
  comercial: 'text-emerald-600',
  compras: 'text-cyan-600',
  estoque: 'text-nexus-orange',
  expedicao: 'text-violet-600',
  fiscal: 'text-nexus-blue',
  qualidade: 'text-blue-600',
  financeiro: 'text-emerald-600',
};

export type KpiTom = 'neutro' | 'positivo' | 'alerta' | 'erro';

/**
 * Tonalidade por `kpi.id` — os ids vêm de `_kpi(...)` em
 * `backend/nexus_erp/dashboard_bi_service.py`; há teste que falha se um id
 * mapeado aqui deixar de existir no backend.
 */
const KPI_POSITIVOS = new Set([
  'pedidos_faturados',
  'valor_faturado',
  'valor_aberto',
  'valor_aberto_compras',
  'propostas_convertidas',
  'nfe_auth_prod',
  'nfe_auth_homolog',
  'produtos_com_saldo',
  'pc_aprovados',
  'pc_recebidos',
  'cq_emitidos',
  'cf_registrados',
  'exp_entregue',
  'recebido_periodo',
  'pago_periodo',
]);

const KPI_ALERTAS = new Set([
  'pedidos_abertos',
  'pedidos_parciais',
  'propostas_abertas',
  'nfe_enviada_prod',
  'nfe_prontas',
  'nfe_rascunhos',
  'dfe_pendentes_entrada',
  'dfe_xml_pendente',
  'dfe_cte_pendentes',
  'produtos_sem_corrida',
  'sem_corrida_com_saldo',
  'produtos_sem_ncm',
  'sem_ncm_com_saldo',
  'estoque_baixo',
  'atendimentos_pendentes',
  'pc_abertos',
  'pc_parcial',
  'cq_rascunho',
  'cq_rastreabilidade_pendente',
  'itens_rastreabilidade_pendente',
  'cf_rascunho',
  'corridas_lotes',
  'pendencias_total',
  'exp_em_andamento',
  'exp_aguardando_separacao',
  'exp_aguardando_retirada',
  'exp_motorista_enviado',
  'exp_em_transito',
  'cr_aberto',
  'cp_aberto',
]);

const KPI_ERROS = new Set([
  'nfe_rej_prod',
  'nfe_rej_homolog',
  'nfe_erro_tx',
  'saldo_negativo',
  'cr_vencido',
  'cp_vencido',
  'exp_ocorrencia',
  'exp_cancelado',
]);

/**
 * Cor contextual de um KPI.
 *
 * Zerro perde a tonalidade: "Rejeitadas: 0" é informação, não sinal — pintar de
 * vermelho um card sem problema faria o painel parecer quebrado o dia inteiro.
 * Id fora das listas cai em `neutro` em vez de chutar uma cor.
 */
export function kpiTom(kpi: BIKpi): KpiTom {
  const n = Number(kpi.valor);
  if (Number.isFinite(n) && n === 0) return 'neutro';
  if (KPI_ERROS.has(kpi.id)) return 'erro';
  if (KPI_ALERTAS.has(kpi.id)) return 'alerta';
  if (KPI_POSITIVOS.has(kpi.id)) return 'positivo';
  return 'neutro';
}

