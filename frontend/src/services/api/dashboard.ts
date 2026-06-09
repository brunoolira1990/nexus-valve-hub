import api from './config';

export type DashboardAlerta = {
  tipo: string;
  severidade: 'info' | 'aviso' | 'critico';
  mensagem: string;
  link: string;
  data?: string;
};

export type DashboardResumo = {
  comercial: {
    pedidos_abertos: number;
    pedidos_parcialmente_faturados: number;
    pedidos_faturados_mes: number;
    valor_aberto_faturar: string;
    valor_faturado_mes: string;
    ultimos_pedidos: {
      id: number;
      numero: string;
      cliente: string;
      data: string;
      valor_total: string;
      status: string;
      link: string;
    }[];
  };
  fiscal: {
    nfe_saida_rascunhos: number;
    nfe_saida_prontas_emissao: number;
    nfe_saida_autorizadas_homologacao: number;
    nfe_saida_rejeitadas_homologacao: number;
    nfe_saida_erro_transmissao: number;
    nfe_saida_canceladas: number;
    nfe_entrada_total: number;
    ultimas_nfe_saida: {
      id: number;
      titulo: string;
      subtitulo: string;
      cliente: string;
      status: string;
      cstat: string;
      valor_total: string;
      link: string;
    }[];
    ultimas_nfe_entrada: {
      id: number;
      numero: string;
      fornecedor: string;
      chave: string;
      status: string;
      valor_total: string;
      link: string;
    }[];
    sefaz_ultimo_status: {
      cstat: string;
      xmotivo: string;
      ambiente: string;
      consultado_em: string;
      empresa: string;
    } | null;
  };
  financeiro: {
    modulo: string;
    mensagem: string;
    contas_receber_aberto: string;
    contas_receber_vencidas: string;
    recebido_mes: string;
    contas_pagar_aberto: string;
    contas_pagar_vencidas: string;
    pago_mes: string;
    saldo_previsto: string;
  };
  estoque: {
    produtos_cadastrados: number;
    produtos_sem_ncm: number;
    produtos_estoque_baixo: number;
    alertas_estoque: {
      produto_id: number;
      codigo: string;
      descricao: string;
      saldo: string;
      minimo: string;
      link: string;
    }[];
  };
  alertas: DashboardAlerta[];
  cards_principais: {
    valor_a_faturar: string;
    pedidos_abertos: number;
    nfe_pendentes_rejeitadas: number;
    estoque_baixo: number;
  };
  gerado_em: string;
};

export type DashboardPeriodo = {
  data_inicio: string;
  data_fim: string;
  label: string;
  periodo: string;
  empresa_id: number | null;
  status: string | null;
};

export type DashboardPermissoes = {
  pode_ver_comercial: boolean;
  pode_ver_fiscal: boolean;
  pode_ver_estoque: boolean;
  pode_ver_compras: boolean;
  pode_ver_qualidade: boolean;
  pode_ver_financeiro: boolean;
  pode_ver_consolidado: boolean;
};

export type BIKpi = {
  id: string;
  titulo: string;
  valor: string | number;
  formato?: 'numero' | 'moeda' | string;
  link?: string | null;
  subtitulo?: string;
};

export type BIChartPonto = {
  label: string;
  valor: number;
};

export type BIChart = {
  id: string;
  titulo: string;
  tipo: 'bar' | 'line' | 'donut' | string;
  dados: BIChartPonto[];
};

export type BIRankingItem = {
  label: string;
  valor: string;
  link?: string;
};

export type BIRanking = {
  id: string;
  titulo: string;
  itens: BIRankingItem[];
};

export type BIAlert = {
  modulo: string;
  severidade: 'info' | 'aviso' | 'critico';
  titulo: string;
  mensagem: string;
  link: string;
};

export type BIUltimo = {
  tipo: string;
  titulo: string;
  subtitulo: string;
  valor: string;
  status: string;
  data: string;
  link: string;
};

export type BILink = {
  id: string;
  titulo: string;
  descricao: string;
  link: string;
};

export type DashboardModuloBI = {
  modulo: string;
  periodo: DashboardPeriodo;
  kpis: BIKpi[];
  graficos: BIChart[];
  rankings: BIRanking[];
  alertas: BIAlert[];
  ultimos: BIUltimo[];
  links: BILink[];
  em_preparacao?: boolean;
  mensagem?: string;
};

export type DashboardModuloHome = {
  modulo: string;
  titulo: string;
  kpis: BIKpi[];
  alerta_principal: BIAlert | null;
  link_bi: string;
};

export type DashboardHome = {
  periodo: DashboardPeriodo;
  permissoes: DashboardPermissoes;
  modulos: DashboardModuloHome[];
  alertas: BIAlert[];
  nenhum_modulo: boolean;
  gerado_em: string;
};

export type DashboardQueryParams = {
  periodo?: string;
  data_inicio?: string;
  data_fim?: string;
  empresa_id?: string | number;
  status?: string;
};

function buildParams(params?: DashboardQueryParams) {
  const q: Record<string, string> = {};
  if (!params) return q;
  if (params.periodo) q.periodo = params.periodo;
  if (params.data_inicio) q.data_inicio = params.data_inicio;
  if (params.data_fim) q.data_fim = params.data_fim;
  if (params.empresa_id != null && params.empresa_id !== '') q.empresa_id = String(params.empresa_id);
  if (params.status) q.status = params.status;
  return q;
}

export const dashboardService = {
  getPermissoes: async () =>
    (await api.get<DashboardPermissoes>('dashboard/permissoes/')).data,

  getResumo: async () => (await api.get<DashboardResumo>('dashboard/resumo/')).data,

  getHome: async (params?: DashboardQueryParams) =>
    (await api.get<DashboardHome>('dashboard/home/', { params: buildParams(params) })).data,

  getComercial: async (params?: DashboardQueryParams) =>
    (await api.get<DashboardModuloBI>('dashboard/comercial/', { params: buildParams(params) })).data,

  getFiscal: async (params?: DashboardQueryParams) =>
    (await api.get<DashboardModuloBI>('dashboard/fiscal/', { params: buildParams(params) })).data,

  getEstoque: async (params?: DashboardQueryParams) =>
    (await api.get<DashboardModuloBI>('dashboard/estoque/', { params: buildParams(params) })).data,

  getCompras: async (params?: DashboardQueryParams) =>
    (await api.get<DashboardModuloBI>('dashboard/compras/', { params: buildParams(params) })).data,

  getQualidade: async (params?: DashboardQueryParams) =>
    (await api.get<DashboardModuloBI>('dashboard/qualidade/', { params: buildParams(params) })).data,

  getFinanceiro: async (params?: DashboardQueryParams) =>
    (await api.get<DashboardModuloBI>('dashboard/financeiro/', { params: buildParams(params) })).data,
};
