import api from './config';

export type ApuracaoPersistidaStatus = 'RASCUNHO' | 'FECHADO';

export type ApuracaoPersistidaLog = {
  id: number;
  acao: string;
  timestamp: string;
  detalhe?: Record<string, unknown>;
  usuario?: number | null;
  usuario_username?: string | null;
};

export type ApuracaoPersistida = {
  id: number;
  empresa: number;
  empresa_nome?: string;
  data_inicio: string;
  data_fim: string;
  status: ApuracaoPersistidaStatus;
  tipo: string;
  fonte: string;
  valor_entradas?: number | string;
  valor_saidas?: number | string;
  icms_debito?: number | string;
  icms_credito?: number | string;
  icms_st_debito?: number | string;
  difal_valor?: number | string;
  ipi_debito?: number | string;
  ipi_credito?: number | string;
  pis_debito?: number | string;
  pis_credito?: number | string;
  cofins_debito?: number | string;
  cofins_credito?: number | string;
  /** Snapshot ICMS próprio (saída − entrada) no momento do rascunho/fecho */
  saldo_icms?: number | string;
  /** Σ impactos dos ajustes (débito +, crédito/estorno −) */
  ajustes_liquido?: number | string;
  /** saldo_icms + ajustes_liquido */
  saldo_final?: number | string;
  quantidade_ajustes?: number;
  totais_json?: Record<string, unknown>;
  filtros_json?: Record<string, unknown>;
  versao_api_apuracao?: string;
  criado_em?: string;
  atualizado_em?: string;
  criado_por?: number | null;
  criado_por_username?: string | null;
  fechado_em?: string | null;
  fechado_por?: number | null;
  fechado_por_username?: string | null;
  quantidade_itens?: number;
  logs?: ApuracaoPersistidaLog[];
};

export type ApuracaoAjusteTipo = 'DEBITO' | 'CREDITO' | 'ESTORNO';

export type ApuracaoAjusteManual = {
  id: number;
  apuracao: number;
  tipo: ApuracaoAjusteTipo;
  valor: number | string;
  motivo: string;
  usuario?: number | null;
  usuario_username?: string | null;
  criado_em?: string;
  impacto?: number;
};

export type ApuracaoAjustesPayload = {
  ajustes: ApuracaoAjusteManual[];
  ajustes_liquido: number;
  saldo_icms_snapshot: number;
  saldo_final: number;
  quantidade: number;
};

export type ApuracaoAjusteMutationResponse = {
  ajuste?: ApuracaoAjusteManual;
  ajuste_id?: number;
  detail?: string;
  ajustes_liquido: number;
  saldo_icms_snapshot: number;
  saldo_final: number;
};

export type ApuracaoPeriodoStatus = {
  empresa_id: number;
  data_inicio: string;
  data_fim: string;
  periodo_fechado: boolean;
  pode_reabrir: boolean;
  apuracao: ApuracaoPersistida | null;
};

export type CriarRascunhoPayload = {
  empresa_id: number;
  data_inicio: string;
  data_fim: string;
  tipo?: string;
  fonte?: string;
  status?: string;
  cliente_id?: number | null;
  fornecedor_id?: number | null;
  cfop?: string;
  ncm?: string;
  modelo_documento?: string;
  incluir_canceladas?: boolean;
};

export const apuracaoPersistidaService = {
  list: async (params: Record<string, string | number | boolean>) =>
    (await api.get<ApuracaoPersistida[]>('fiscal/apuracoes/', { params })).data,

  get: async (id: number) => (await api.get<ApuracaoPersistida>(`fiscal/apuracoes/${id}/`)).data,

  periodo: async (params: { empresa_id: number | string; data_inicio: string; data_fim: string }) =>
    (await api.get<ApuracaoPeriodoStatus>('fiscal/apuracoes/periodo/', { params })).data,

  criarRascunho: async (body: CriarRascunhoPayload) =>
    (await api.post<ApuracaoPersistida>('fiscal/apuracoes/', body)).data,

  fechar: async (id: number) =>
    (await api.post<ApuracaoPersistida>(`fiscal/apuracoes/${id}/fechar/`, {})).data,

  reabrir: async (id: number, motivo: string) =>
    (await api.post<ApuracaoPersistida>(`fiscal/apuracoes/${id}/reabrir/`, { motivo })).data,

  listarAjustes: async (apuracaoId: number) =>
    (await api.get<ApuracaoAjustesPayload>(`fiscal/apuracoes/${apuracaoId}/ajustes/`)).data,

  criarAjuste: async (
    apuracaoId: number,
    body: { tipo: ApuracaoAjusteTipo; valor: number | string; motivo: string },
  ) =>
    (await api.post<ApuracaoAjusteMutationResponse>(`fiscal/apuracoes/${apuracaoId}/ajustes/`, body))
      .data,

  removerAjuste: async (apuracaoId: number, ajusteId: number) =>
    (
      await api.delete<ApuracaoAjusteMutationResponse>(
        `fiscal/apuracoes/${apuracaoId}/ajustes/${ajusteId}/`,
      )
    ).data,

  baixarSpedEfdIcmsIpi: async (apuracaoId: number) => {
    const res = await api.get<Blob>(`fiscal/apuracoes/${apuracaoId}/sped-efd-icms-ipi/`, {
      responseType: 'blob',
    });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = `efd_icms_ipi_previa_ap${apuracaoId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  },
};
