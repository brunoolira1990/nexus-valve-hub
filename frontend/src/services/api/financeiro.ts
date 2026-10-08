import api from './config';
import {
  buildListParams,
  isPaginatedResponse,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';

export type FinanceiroResumoMetrica = {
  valor: string;
  quantidade: number;
};

export type FinanceiroResumoBloco = {
  hoje: FinanceiroResumoMetrica;
  vencido: FinanceiroResumoMetrica;
  proximos_7_dias: FinanceiroResumoMetrica;
  em_aberto: FinanceiroResumoMetrica;
  recebido_periodo: FinanceiroResumoMetrica;
  pago_periodo: FinanceiroResumoMetrica;
};

export type FinanceiroResumoAlerta = {
  codigo: string;
  mensagem: string;
  quantidade: number;
  acao: string;
};

export type FinanceiroResumoConta = {
  conta_id: number;
  conta_nome: string;
  a_receber_em_aberto: string;
  a_pagar_em_aberto: string;
  saldo_previsto: string;
};

export type FinanceiroResumoCategoriaItem = {
  categoria_id: number | null;
  categoria_nome: string;
  valor: string;
};

export type FinanceiroResumo = {
  periodo?: string;
  data_inicio?: string;
  data_fim?: string;
  referencia_data: string;
  receber: FinanceiroResumoBloco;
  pagar: FinanceiroResumoBloco;
  saldo_previsto: { em_aberto: string; proximos_7_dias: string };
  alertas: FinanceiroResumoAlerta[];
  por_conta: FinanceiroResumoConta[];
  por_categoria: { receitas: FinanceiroResumoCategoriaItem[]; despesas: FinanceiroResumoCategoriaItem[] };
  creditos: {
    clientes: { quantidade: number; valor_disponivel: string };
    fornecedores: { quantidade: number; valor_disponivel: string };
    total_disponivel: string;
  };
  a_receber_hoje?: string;
  a_receber_vencido?: string;
  a_pagar_hoje?: string;
  a_pagar_vencido?: string;
  recebido_mes?: string;
  pago_mes?: string;
};

export type RelatorioPeriodo = {
  periodo: string;
  data_inicio: string;
  data_fim: string;
};

export type RelatorioMetrica = {
  valor: string;
  quantidade: number;
  data?: string | null;
};

export type RelatorioLinhaTitulo = {
  id: number;
  vencimento: string;
  vencimento_exibicao?: string | null;
  vencimento_label?: string | null;
  vencimento_ausente?: string | null;
  emissao: string;
  cliente_nome?: string | null;
  fornecedor_nome?: string | null;
  descricao?: string | null;
  tipo_lancamento?: string | null;
  tipo_lancamento_label?: string | null;
  documento: string;
  origem: string;
  origem_tipo: string;
  valor_original: string;
  valor_baixado: string;
  saldo: string;
  status: string;
  status_label: string;
  categoria_nome?: string | null;
  centro_custo_nome?: string | null;
  conta_prevista_nome?: string | null;
  origem_fiscal_cancelada: boolean;
  pode_baixar: boolean;
  cliente_id?: number | null;
  fornecedor_id?: number | null;
};

export type RelatorioAgrupamento = {
  chave: string;
  titulo: string;
  quantidade: number;
  valor_original: string;
  saldo: string;
};

export type RelatorioContasReceberPagar = {
  tipo: 'contas_receber' | 'contas_pagar';
  periodo: RelatorioPeriodo;
  aviso_historico?: string | null;
  cards: {
    total_aberto: RelatorioMetrica;
    total_vencido: RelatorioMetrica;
    recebido_periodo?: RelatorioMetrica;
    pago_periodo?: RelatorioMetrica;
    total_parcial: RelatorioMetrica;
    total_tributos?: RelatorioMetrica;
    quantidade_titulos: number;
  };
  linhas: RelatorioLinhaTitulo[];
  agrupamentos: RelatorioAgrupamento[];
};

export type RelatorioFluxoPrevisto = {
  tipo: 'fluxo_previsto';
  nota: string;
  periodo: RelatorioPeriodo;
  cards: {
    total_receber: RelatorioMetrica;
    total_pagar: RelatorioMetrica;
    saldo_previsto: RelatorioMetrica;
    maior_entrada: RelatorioMetrica;
    maior_saida: RelatorioMetrica;
  };
  linhas: {
    data: string;
    a_receber: string;
    a_pagar: string;
    saldo_dia: string;
    saldo_acumulado: string;
  }[];
};

export type RelatorioCategoriaLinha = {
  categoria_id: number | null;
  categoria_nome: string;
  tipo: string;
  quantidade: number;
  valor_original: string;
  em_aberto: string;
  baixado_periodo: string;
  total_considerado: string;
  baixado?: string;
  total?: string;
};

export type RelatorioCategorias = {
  tipo: 'categorias';
  periodo: RelatorioPeriodo;
  aviso_historico?: string | null;
  cards: {
    total_receitas: RelatorioMetrica;
    total_despesas: RelatorioMetrica;
    diferenca_prevista: RelatorioMetrica;
    sem_classificacao: { receitas: number; despesas: number };
  };
  receitas: RelatorioCategoriaLinha[];
  despesas: RelatorioCategoriaLinha[];
  linhas: RelatorioCategoriaLinha[];
};

export type RelatorioContraparteResumo = {
  cliente_id?: number | null;
  fornecedor_id?: number | null;
  cliente_nome?: string;
  fornecedor_nome?: string;
  total_aberto: string;
  total_vencido: string;
  recebido_periodo?: string;
  pago_periodo?: string;
  quantidade_titulos: number;
  ultimo_recebimento?: string | null;
  ultimo_pagamento?: string | null;
};

export type RelatorioClientes = {
  tipo: 'clientes';
  periodo: RelatorioPeriodo;
  aviso_historico?: string | null;
  detalhe_cliente_id?: number;
  resumo: RelatorioContraparteResumo[];
  linhas: RelatorioLinhaTitulo[];
};

export type RelatorioFornecedores = {
  tipo: 'fornecedores';
  periodo: RelatorioPeriodo;
  aviso_historico?: string | null;
  detalhe_fornecedor_id?: number;
  resumo: RelatorioContraparteResumo[];
  linhas: RelatorioLinhaTitulo[];
};

export type RelatorioQueryParams = Record<string, string | number | undefined>;

export type ContaFinanceira = {
  id: number;
  nome: string;
  tipo: string;
  tipo_label?: string;
  banco?: string;
  agencia?: string;
  conta?: string;
  ativo: boolean;
  observacoes?: string;
};

export type FormaPagamentoFixa = {
  codigo: string;
  label: string;
};

export type CentroCusto = {
  id: number;
  nome: string;
  ativo: boolean;
  observacoes?: string;
};

export type CategoriaFinanceira = {
  id: number;
  nome: string;
  tipo: string;
  tipo_label?: string;
  categoria_pai?: number | null;
  ativo: boolean;
  observacoes?: string;
};

export type ParcelaFinanceira = {
  id: number;
  numero_parcela: number;
  data_vencimento: string;
  valor_original: string;
  valor_aberto: string;
  valor_baixado: string;
  status: string;
  status_label?: string;
  observacoes?: string;
};

export type BaixaFinanceira = {
  id: number;
  titulo: number;
  parcela?: number | null;
  data_baixa: string;
  valor: string;
  conta_financeira: number;
  conta_financeira_nome?: string;
  forma_pagamento_codigo: string;
  forma_pagamento_label?: string;
  forma_pagamento_nome?: string;
  tipo_movimento?: string;
  tipo_movimento_label?: string;
  juros?: string;
  multa?: string;
  desconto?: string;
  tarifa?: string;
  observacoes?: string;
  estornada: boolean;
  motivo_estorno?: string;
  estornada_em?: string | null;
  pode_estornar?: boolean;
  criado_em?: string;
};

export type FinanceiroEvento = {
  id: number;
  acao: string;
  acao_label?: string;
  descricao: string;
  dados_anteriores?: Record<string, unknown> | null;
  dados_novos?: Record<string, unknown> | null;
  usuario_nome?: string;
  criado_em: string;
};

export type ParcelaDefinidaPayload = {
  numero_parcela?: number;
  data_vencimento: string;
  valor: string | number;
  observacoes?: string;
};

export type TituloFinanceiro = {
  id: number;
  tipo: 'RECEBER' | 'PAGAR';
  numero: string;
  cliente?: number | null;
  cliente_nome?: string;
  cliente_cnpj?: string;
  fornecedor?: number | null;
  fornecedor_nome?: string;
  fornecedor_cnpj?: string;
  tipo_lancamento?: string;
  tipo_lancamento_label?: string;
  descricao?: string;
  competencia?: string | null;
  tipo_tributo?: string;
  tipo_tributo_label?: string;
  periodo_apuracao?: string;
  numero_guia?: string;
  codigo_receita?: string;
  titulo_resumo?: string;
  categoria_nome?: string;
  documento_origem?: string;
  origem_tipo: string;
  origem_id?: number | null;
  origem_descricao?: string;
  origem_numero?: string;
  origem_data?: string | null;
  origem_exibicao?: string;
  origem_nfe_detalhe?: {
    nfe_id: number;
    numero_nfe: string;
    serie_nfe: string;
    chave_acesso: string;
    data_autorizacao: string | null;
    pedido_venda_numero: string;
    faturamento_numero: string;
    origem_cancelada: boolean;
    alerta_origem_cancelada: string;
  } | null;
  origem_nfe_entrada_detalhe?: {
    nfe_entrada_id: number;
    numero_nfe: string;
    serie_nfe: string;
    chave_acesso: string;
    data_emissao: string | null;
    data_importacao: string | null;
    fornecedor_nome: string;
    pedido_compra_numero: string;
    origem_cancelada: boolean;
    alerta_origem_cancelada: string;
  } | null;
  alerta_origem_cancelada?: string;
  data_emissao: string;
  data_vencimento: string;
  valor_original: string;
  valor_aberto: string;
  valor_baixado: string;
  status: string;
  status_label?: string;
  forma_pagamento_prevista_codigo?: string;
  conta_financeira_prevista?: number | null;
  categoria?: number | null;
  centro_custo?: number | null;
  observacoes?: string;
  cancelado?: boolean;
  motivo_cancelamento?: string;
  cancelado_em?: string | null;
  parcelas?: ParcelaFinanceira[];
  baixas?: BaixaFinanceira[];
  eventos?: FinanceiroEvento[];
  pode_editar?: boolean;
  pode_baixar?: boolean;
  pode_cancelar?: boolean;
  possui_baixa_ativa?: boolean;
  pode_estornar_baixa?: boolean;
  pode_abater?: boolean;
  pode_aplicar_credito?: boolean;
  possui_credito_aplicado?: boolean;
  possui_abatimento?: boolean;
  pode_excluir?: boolean;
  origem_manual?: boolean;
  possui_movimento_financeiro?: boolean;
  possui_movimento_financeiro_ativo?: boolean;
  possui_apenas_movimentos_estornados?: boolean;
  possui_vinculo_origem?: boolean;
  motivo_bloqueio_exclusao?: string;
  saldo_integral_reaberto?: boolean;
  valor_movimentado_ativo_zero?: boolean;
  criado_em?: string;
  atualizado_em?: string;
};

export type TituloCreatePayload = {
  cliente?: number | null;
  fornecedor?: number | null;
  tipo_lancamento?: string;
  descricao?: string;
  competencia?: string | null;
  tipo_tributo?: string;
  periodo_apuracao?: string;
  numero_guia?: string;
  codigo_receita?: string;
  numero?: string;
  documento_origem?: string;
  data_emissao: string;
  data_vencimento: string;
  valor_original: string | number;
  forma_pagamento_prevista_codigo?: string;
  conta_financeira_prevista?: number | null;
  categoria?: number | null;
  centro_custo?: number | null;
  observacoes?: string;
  gerar_parcelas?: boolean;
  quantidade_parcelas?: number;
  intervalo_dias?: number;
  primeiro_vencimento_dias?: number;
  parcelas?: ParcelaDefinidaPayload[];
};

export type BaixaPayload = {
  data_baixa: string;
  valor: string | number;
  conta_financeira?: number;
  forma_pagamento_codigo: string;
  parcela?: number | null;
  juros?: string | number;
  multa?: string | number;
  desconto?: string | number;
  tarifa?: string | number;
  observacoes?: string;
};

export type CreditoFinanceiroEvento = {
  id: number;
  acao: string;
  acao_label?: string;
  descricao: string;
  valor?: string | null;
  titulo_numero?: string;
  baixa_id?: number | null;
  usuario_nome?: string;
  criado_em: string;
};

export type CreditoFinanceiro = {
  id: number;
  tipo: 'CLIENTE' | 'FORNECEDOR';
  tipo_label?: string;
  cliente?: number | null;
  cliente_nome?: string;
  cliente_cnpj?: string;
  fornecedor?: number | null;
  fornecedor_nome?: string;
  fornecedor_cnpj?: string;
  contraparte_nome?: string;
  valor_original: string;
  valor_utilizado: string;
  saldo: string;
  status: string;
  status_label?: string;
  origem_tipo: string;
  origem_tipo_label?: string;
  origem_descricao?: string;
  origem_numero?: string;
  data_credito: string;
  motivo: string;
  observacoes?: string;
  cancelado?: boolean;
  motivo_cancelamento?: string;
  cancelado_em?: string | null;
  pode_aplicar?: boolean;
  pode_cancelar?: boolean;
  pode_editar?: boolean;
  pode_editar_completo?: boolean;
  pode_excluir?: boolean;
  possui_movimento?: boolean;
  possui_movimento_ativo?: boolean;
  possui_apenas_movimentos_estornados?: boolean;
  possui_aplicacao?: boolean;
  possui_aplicacao_ativa?: boolean;
  possui_estorno?: boolean;
  possui_vinculo_origem?: boolean;
  motivo_bloqueio_exclusao?: string;
  saldo_integral_reaberto?: boolean;
  movimentos?: BaixaFinanceira[];
  eventos?: CreditoFinanceiroEvento[];
  criado_em?: string;
  atualizado_em?: string;
};

export type CreditoUpdatePayload = {
  cliente?: number | null;
  fornecedor?: number | null;
  valor_original?: string | number;
  origem_tipo?: string;
  origem_numero?: string;
  origem_descricao?: string;
  data_credito?: string;
  motivo?: string;
  observacoes?: string;
};

export type CreditoCreatePayload = {
  tipo: 'CLIENTE' | 'FORNECEDOR';
  cliente?: number | null;
  fornecedor?: number | null;
  valor_original: string | number;
  data_credito: string;
  motivo: string;
  origem_tipo?: string;
  origem_descricao?: string;
  origem_numero?: string;
  observacoes?: string;
};

export type AplicarCreditoPayload = {
  titulo: number;
  valor: string | number;
  data: string;
  parcela?: number | null;
  motivo?: string;
  observacoes?: string;
};

export type AbatimentoPayload = {
  data: string;
  valor: string | number;
  motivo: string;
  parcela?: number | null;
  observacoes?: string;
  documento_referencia?: string;
};

const creditosPath = 'financeiro/creditos/';
const contasPath = 'financeiro/contas/';
const categoriasPath = 'financeiro/categorias/';
const centrosPath = 'financeiro/centros-custo/';
const receberPath = 'financeiro/contas-receber/';
const pagarPath = 'financeiro/contas-pagar/';
const baixasPath = 'financeiro/baixas/';

async function listAll<T>(path: string, params?: ListQueryParams): Promise<PaginatedResponse<T>> {
  const response = await api.get<PaginatedResponse<T> | T[]>(path, { params: buildListParams(params) });
  const data = response.data;
  if (isPaginatedResponse<T>(data)) {
    return data;
  }
  const results = unwrapListResults(data);
  return {
    count: results.length,
    page: 1,
    page_size: results.length || 20,
    total_pages: results.length ? 1 : 0,
    next: null,
    previous: null,
    results,
  };
}

export const financeiroService = {
  getResumo: async (params?: { periodo?: string; data_inicio?: string; data_fim?: string }) =>
    (await api.get<FinanceiroResumo>('financeiro/resumo/', { params })).data,

  listContas: (params?: ListQueryParams) => listAll<ContaFinanceira>(contasPath, params),
  createConta: async (data: Partial<ContaFinanceira>) =>
    (await api.post<ContaFinanceira>(contasPath, data)).data,
  updateConta: async (id: number, data: Partial<ContaFinanceira>) =>
    (await api.patch<ContaFinanceira>(`${contasPath}${id}/`, data)).data,
  deleteConta: async (id: number) => {
    await api.delete(`${contasPath}${id}/`);
  },

  listCategorias: (params?: ListQueryParams) => listAll<CategoriaFinanceira>(categoriasPath, params),
  createCategoria: async (data: Partial<CategoriaFinanceira>) =>
    (await api.post<CategoriaFinanceira>(categoriasPath, data)).data,
  updateCategoria: async (id: number, data: Partial<CategoriaFinanceira>) =>
    (await api.patch<CategoriaFinanceira>(`${categoriasPath}${id}/`, data)).data,
  deleteCategoria: async (id: number) => {
    await api.delete(`${categoriasPath}${id}/`);
  },

  listCentrosCusto: (params?: ListQueryParams) => listAll<CentroCusto>(centrosPath, params),
  createCentroCusto: async (data: Partial<CentroCusto>) =>
    (await api.post<CentroCusto>(centrosPath, data)).data,
  updateCentroCusto: async (id: number, data: Partial<CentroCusto>) =>
    (await api.patch<CentroCusto>(`${centrosPath}${id}/`, data)).data,
  deleteCentroCusto: async (id: number) => {
    await api.delete(`${centrosPath}${id}/`);
  },

  listContasReceber: (params?: ListQueryParams) => listAll<TituloFinanceiro>(receberPath, params),
  getContaReceber: async (id: number) => (await api.get<TituloFinanceiro>(`${receberPath}${id}/`)).data,
  createContaReceber: async (data: TituloCreatePayload) =>
    (await api.post<TituloFinanceiro>(receberPath, data)).data,
  patchContaReceber: async (id: number, data: Partial<TituloFinanceiro>) =>
    (await api.patch<TituloFinanceiro>(`${receberPath}${id}/`, data)).data,
  baixarReceber: async (id: number, data: BaixaPayload) =>
    (
      await api.post<{ titulo: TituloFinanceiro; baixa: BaixaFinanceira }>(
        `${receberPath}${id}/baixar/`,
        data,
      )
    ).data,

  listContasPagar: (params?: ListQueryParams) => listAll<TituloFinanceiro>(pagarPath, params),
  getContaPagar: async (id: number) => (await api.get<TituloFinanceiro>(`${pagarPath}${id}/`)).data,
  createContaPagar: async (data: TituloCreatePayload) =>
    (await api.post<TituloFinanceiro>(pagarPath, data)).data,
  patchContaPagar: async (id: number, data: Partial<TituloFinanceiro>) =>
    (await api.patch<TituloFinanceiro>(`${pagarPath}${id}/`, data)).data,
  baixarPagar: async (id: number, data: BaixaPayload) =>
    (
      await api.post<{ titulo: TituloFinanceiro; baixa: BaixaFinanceira }>(
        `${pagarPath}${id}/baixar/`,
        data,
      )
    ).data,

  cancelarTitulo: async (tipo: 'RECEBER' | 'PAGAR', id: number, motivo: string) => {
    const base = tipo === 'RECEBER' ? receberPath : pagarPath;
    return (
      await api.post<{ mensagem: string; titulo: TituloFinanceiro }>(`${base}${id}/cancelar/`, {
        motivo,
      })
    ).data;
  },

  excluirTitulo: async (tipo: 'RECEBER' | 'PAGAR', id: number, motivo: string) => {
    const base = tipo === 'RECEBER' ? receberPath : pagarPath;
    return (await api.post<{ mensagem: string }>(`${base}${id}/excluir/`, { motivo })).data;
  },

  estornarBaixa: async (baixaId: number, motivo: string) =>
    (
      await api.post<{ titulo?: TituloFinanceiro; baixa: BaixaFinanceira; credito?: CreditoFinanceiro }>(
        `${baixasPath}${baixaId}/estornar/`,
        { motivo },
      )
    ).data,

  listCreditos: (params?: ListQueryParams) => listAll<CreditoFinanceiro>(creditosPath, params),
  getCredito: async (id: number) => (await api.get<CreditoFinanceiro>(`${creditosPath}${id}/`)).data,
  createCredito: async (data: CreditoCreatePayload) =>
    (await api.post<CreditoFinanceiro>(creditosPath, data)).data,
  cancelarCredito: async (id: number, motivo: string) =>
    (await api.post<CreditoFinanceiro>(`${creditosPath}${id}/cancelar/`, { motivo })).data,
  patchCredito: async (id: number, data: CreditoUpdatePayload) =>
    (await api.patch<CreditoFinanceiro>(`${creditosPath}${id}/`, data)).data,
  excluirCredito: async (id: number, motivo: string) =>
    (await api.post<{ mensagem: string }>(`${creditosPath}${id}/excluir/`, { motivo })).data,
  aplicarCredito: async (creditoId: number, data: AplicarCreditoPayload) =>
    (
      await api.post<{ titulo: TituloFinanceiro; baixa: BaixaFinanceira; credito: CreditoFinanceiro }>(
        `${creditosPath}${creditoId}/aplicar/`,
        data,
      )
    ).data,
  abaterDevolucaoReceber: async (tituloId: number, data: AbatimentoPayload) =>
    (
      await api.post<{ titulo: TituloFinanceiro; baixa: BaixaFinanceira }>(
        `${receberPath}${tituloId}/abater-devolucao/`,
        data,
      )
    ).data,
  abaterDevolucaoPagar: async (tituloId: number, data: AbatimentoPayload) =>
    (
      await api.post<{ titulo: TituloFinanceiro; baixa: BaixaFinanceira }>(
        `${pagarPath}${tituloId}/abater-devolucao/`,
        data,
      )
    ).data,

  listContasAtivas: async () => {
    const data = await listAll<ContaFinanceira>(contasPath, { ativo: 'true', limit: 200 });
    return unwrapListResults(data);
  },

  listFormasFixas: async () =>
    (await api.get<{ formas_pagamento: FormaPagamentoFixa[]; tipos_movimento: FormaPagamentoFixa[] }>(
      'financeiro/formas-fixas/',
    )).data,

  /** Compatível com telas legadas — retorna apenas formas com movimentação real (exclui sem movimentação). */
  listFormasAtivas: async () => {
    const data = await api.get<{ formas_pagamento: FormaPagamentoFixa[] }>('financeiro/formas-fixas/');
    return data.data.formas_pagamento.filter((f) => f.codigo !== 'SEM_MOVIMENTACAO_FINANCEIRA');
  },

  relatorioContasReceber: async (params?: RelatorioQueryParams) =>
    (await api.get<RelatorioContasReceberPagar>('financeiro/relatorios/contas-receber/', { params })).data,

  relatorioContasPagar: async (params?: RelatorioQueryParams) =>
    (await api.get<RelatorioContasReceberPagar>('financeiro/relatorios/contas-pagar/', { params })).data,

  relatorioFluxoPrevisto: async (params?: RelatorioQueryParams) =>
    (await api.get<RelatorioFluxoPrevisto>('financeiro/relatorios/fluxo-previsto/', { params })).data,

  relatorioCategorias: async (params?: RelatorioQueryParams) =>
    (await api.get<RelatorioCategorias>('financeiro/relatorios/categorias/', { params })).data,

  relatorioClientes: async (params?: RelatorioQueryParams) =>
    (await api.get<RelatorioClientes>('financeiro/relatorios/clientes/', { params })).data,

  relatorioFornecedores: async (params?: RelatorioQueryParams) =>
    (await api.get<RelatorioFornecedores>('financeiro/relatorios/fornecedores/', { params })).data,
};
