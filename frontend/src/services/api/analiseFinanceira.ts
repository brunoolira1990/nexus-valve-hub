import api from './config';

export type CondicaoAnalise = {
  texto: string;
  dias: number[];
  quantidade_parcelas: number;
  modalidade: string;
  maior_prazo_dias: number;
};

export type AnaliseFinanceiraPermissoes = {
  pode_solicitar?: boolean;
  pode_decidir?: boolean;
  pode_ver_detalhe_financeiro?: boolean;
};

export type AnaliseFinanceiraProposta = {
  id: number;
  proposta: number;
  proposta_numero?: string;
  cliente: number;
  cliente_nome?: string;
  status: string;
  versao: number;
  solicitada_em: string;
  valor_solicitado: string;
  valor_maximo_aprovado?: string | null;
  valida_ate?: string | null;
  observacao_vendedor?: string;
  justificativa_decisao?: string;
  condicao_solicitada?: CondicaoAnalise;
  condicao_aprovada?: CondicaoAnalise;
  snapshot_indicadores?: Record<string, unknown>;
  snapshot_proposta?: Record<string, unknown>;
  solicitada_por_nome?: string | null;
  decidida_por_nome?: string | null;
  permissoes?: AnaliseFinanceiraPermissoes;
};

export type SituacaoAnaliseFinanceira = {
  situacao: {
    avaliacao: {
      exige_liberacao: boolean;
      a_vista: boolean;
      valida: boolean;
      motivo_codigo: string;
      motivo: string;
      condicao_atual: CondicaoAnalise | null;
      analise_id: number | null;
    };
    ultima_analise_id: number | null;
    ultima_analise_status: string | null;
    analise_ativa_id: number | null;
    reanalise_necessaria: boolean;
    permissoes?: AnaliseFinanceiraPermissoes;
  };
  ultima: AnaliseFinanceiraProposta | null;
  historico: AnaliseFinanceiraProposta[];
};

const propostasPath = 'propostas/';
const analisesPath = 'analises-financeiras/';

export const analiseFinanceiraService = {
  situacaoProposta: async (propostaId: number) =>
    (await api.get<SituacaoAnaliseFinanceira>(`${propostasPath}${propostaId}/analise-financeira/`)).data,
  solicitar: async (propostaId: number, observacao_vendedor = '') =>
    (
      await api.post<AnaliseFinanceiraProposta>(`${propostasPath}${propostaId}/analise-financeira/solicitar/`, {
        observacao_vendedor,
      })
    ).data,
  list: async (params?: Record<string, string | number | undefined>) =>
    (await api.get<{ count: number; results: AnaliseFinanceiraProposta[] }>(analisesPath, { params })).data,
  getById: async (id: number) => (await api.get<AnaliseFinanceiraProposta>(`${analisesPath}${id}/`)).data,
  iniciar: async (id: number) => (await api.post<AnaliseFinanceiraProposta>(`${analisesPath}${id}/iniciar/`)).data,
  aprovar: async (id: number, payload?: { valida_ate?: string; valor_maximo_aprovado?: string }) =>
    (await api.post<AnaliseFinanceiraProposta>(`${analisesPath}${id}/aprovar/`, payload || {})).data,
  aprovarComAjuste: async (
    id: number,
    payload: {
      dias_aprovados: number[];
      justificativa: string;
      valida_ate?: string;
      valor_maximo_aprovado?: string;
    },
  ) => (await api.post<AnaliseFinanceiraProposta>(`${analisesPath}${id}/aprovar-com-ajuste/`, payload)).data,
  devolver: async (id: number, justificativa: string) =>
    (await api.post<AnaliseFinanceiraProposta>(`${analisesPath}${id}/devolver/`, { justificativa })).data,
  naoAprovar: async (id: number, justificativa: string) =>
    (await api.post<AnaliseFinanceiraProposta>(`${analisesPath}${id}/nao-aprovar/`, { justificativa })).data,
  capacidadeIntegracoes: async () =>
    (await api.get<CapacidadeIntegracoesCredito>(`${analisesPath}integracoes/capacidade/`)).data,
  listConsultasExternas: async (analiseId: number) =>
    (
      await api.get<{ count?: number; results?: ConsultaExternaAnaliseFinanceira[] } | ConsultaExternaAnaliseFinanceira[]>(
        `${analisesPath}${analiseId}/consultas-externas/`,
      )
    ).data,
};

export type CapacidadeBlocoIntegracao = {
  configurado: boolean;
  disponivel: boolean;
  provider: string | null;
  produto: string | null;
  permite_consulta: boolean;
  motivo: string;
};

export type CapacidadeIntegracoesCredito = {
  cadastral: CapacidadeBlocoIntegracao;
  buro: CapacidadeBlocoIntegracao;
  decisao_financeira: 'MANUAL' | string;
};

export type ConsultaExternaAnaliseFinanceira = {
  id: number;
  tipo: 'CADASTRAL' | 'BURO' | string;
  status: string;
  cnpj_mascarado?: string;
  resultado_normalizado?: Record<string, unknown>;
  erro_sanitizado?: string;
};
