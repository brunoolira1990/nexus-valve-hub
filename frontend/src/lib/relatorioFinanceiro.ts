import type { TituloFiltrosState } from '@/components/financeiro/TituloFinanceiroFiltrosPanel';

export const RELATORIOS_HUB = [
  {
    id: 'contas-receber',
    titulo: 'Contas a Receber',
    descricao: 'Títulos a receber, vencimentos e recebimentos no período.',
    path: '/financeiro/relatorios/contas-receber',
  },
  {
    id: 'contas-pagar',
    titulo: 'Contas a Pagar',
    descricao: 'Despesas, tributos e pagamentos previstos por fornecedor.',
    path: '/financeiro/relatorios/contas-pagar',
  },
  {
    id: 'fluxo-previsto',
    titulo: 'Fluxo previsto',
    descricao: 'Entradas e saídas previstas por data (não é conciliação bancária).',
    path: '/financeiro/relatorios/fluxo-previsto',
  },
  {
    id: 'categorias',
    titulo: 'Receitas e despesas por categoria',
    descricao: 'Composição de receitas e despesas por classificação.',
    path: '/financeiro/relatorios/categorias',
  },
  {
    id: 'clientes',
    titulo: 'Por cliente',
    descricao: 'Cobrança e acompanhamento de recebíveis por cliente.',
    path: '/financeiro/relatorios/clientes',
  },
  {
    id: 'fornecedores',
    titulo: 'Por fornecedor',
    descricao: 'Pagamentos e despesas agrupados por fornecedor.',
    path: '/financeiro/relatorios/fornecedores',
  },
] as const;

export type RelatorioFiltrosExtras = {
  periodo?: string;
  periodo_emissao?: string;
  periodo_baixa?: string;
  agrupamento?: string;
  cliente?: string;
  fornecedor?: string;
  data_inicio?: string;
  data_fim?: string;
  emissao_de?: string;
  emissao_ate?: string;
  incluir_quitados?: string;
  incluir_cancelados?: string;
  incluir_sem_saldo?: string;
};

export type RelatorioFiltrosState = TituloFiltrosState & RelatorioFiltrosExtras;

const EXTRA_KEYS: (keyof RelatorioFiltrosExtras)[] = [
  'periodo',
  'periodo_emissao',
  'periodo_baixa',
  'agrupamento',
  'cliente',
  'fornecedor',
  'data_inicio',
  'data_fim',
  'emissao_de',
  'emissao_ate',
  'incluir_quitados',
  'incluir_cancelados',
  'incluir_sem_saldo',
];

export const EMPTY_STATE_RELATORIO: Record<string, string> = {
  'contas-receber': 'Nenhum título a receber encontrado para os filtros selecionados.',
  'contas-pagar': 'Nenhuma conta a pagar encontrada para os filtros selecionados.',
  clientes: 'Nenhum cliente com saldo ou recebimento no período selecionado.',
  fornecedores: 'Nenhum fornecedor com saldo ou pagamento no período selecionado.',
  categorias: 'Nenhuma categoria financeira encontrada para os filtros selecionados.',
  'fluxo-previsto': 'Nenhum movimento previsto para o período selecionado.',
};

export function linkVerTitulosRelatorio(
  modo: 'receber' | 'pagar',
  filtros: RelatorioFiltrosState,
  contraparteId?: number | null,
): string {
  const base =
    modo === 'receber'
      ? '/financeiro/relatorios/contas-receber'
      : '/financeiro/relatorios/contas-pagar';
  const q = { ...relatorioFiltrosToQuery(filtros) };
  if (contraparteId) {
    if (modo === 'receber') q.cliente = String(contraparteId);
    else q.fornecedor = String(contraparteId);
  }
  const sp = new URLSearchParams(q).toString();
  return sp ? `${base}?${sp}` : base;
}

export function relatorioFiltrosFromSearchParams(sp: URLSearchParams): RelatorioFiltrosState {
  const base: RelatorioFiltrosState = {
    status: sp.get('status') || '',
    vencimento: sp.get('vencimento') || '',
    origem_tipo: sp.get('origem_tipo') || sp.get('origem') || '',
    tipo_lancamento: sp.get('tipo_lancamento') || '',
    categoria: sp.get('categoria') || '',
    centro_custo: sp.get('centro_custo') || '',
    conta_prevista: sp.get('conta_prevista') || sp.get('conta_financeira_prevista') || '',
    origem_fiscal_cancelada: sp.get('origem_fiscal_cancelada') || '',
    com_saldo_aberto: sp.get('com_saldo_aberto') || '',
    sem_categoria: sp.get('sem_categoria') || '',
    sem_conta_prevista: sp.get('sem_conta_prevista') || '',
    periodo: sp.get('periodo') || '',
    periodo_emissao: sp.get('periodo_emissao') || sp.get('emissao') || '',
    periodo_baixa: sp.get('periodo_baixa') || '',
    agrupamento: sp.get('agrupamento') || '',
    cliente: sp.get('cliente') || sp.get('cliente_id') || '',
    fornecedor: sp.get('fornecedor') || sp.get('fornecedor_id') || '',
    data_inicio: sp.get('data_inicio') || sp.get('vencimento_de') || '',
    data_fim: sp.get('data_fim') || sp.get('vencimento_ate') || '',
    emissao_de: sp.get('emissao_de') || sp.get('emissao_inicio') || '',
    emissao_ate: sp.get('emissao_ate') || sp.get('emissao_fim') || '',
    incluir_quitados: sp.get('incluir_quitados') || '',
    incluir_cancelados: sp.get('incluir_cancelados') || '',
    incluir_sem_saldo: sp.get('incluir_sem_saldo') || '',
  };
  return base;
}

export function relatorioFiltrosToQuery(f: RelatorioFiltrosState): Record<string, string> {
  const q: Record<string, string> = {};
  const allKeys = [
    'status',
    'vencimento',
    'origem_tipo',
    'tipo_lancamento',
    'categoria',
    'centro_custo',
    'conta_prevista',
    'origem_fiscal_cancelada',
    'com_saldo_aberto',
    'sem_categoria',
    'sem_conta_prevista',
    ...EXTRA_KEYS,
  ] as const;
  allKeys.forEach((k) => {
    const v = f[k];
    if (v) q[k] = v;
  });
  return q;
}

export function relatorioFiltrosTemAlgum(f: RelatorioFiltrosState): boolean {
  return Object.values(f).some(Boolean);
}
