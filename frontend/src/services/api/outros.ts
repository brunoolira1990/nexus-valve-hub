import api from './config';
import { buildListParams, type ListQueryParams, type PaginatedResponse, unwrapListResults } from '@/lib/apiList';
import type {
  ApuracaoFiscalPayload,
  AtendimentoEstoqueItem,
  Balancete,
  ContaContabil,
  EstoqueItem,
  EstoqueSaldoItem,
  KardexEstoqueFiltros,
  KardexEstoqueResponse,
  SaldoConsolidadoProduto,
} from '@/types';

type ContaAPI = ContaContabil & {
  filhos?: Array<{
    id: number;
    codigo: string;
    nome: string;
    tipo: string;
    pai_id: number | null;
    filhos?: ContaAPI['filhos'];
  }>;
};

function flattenContas(rows: ContaAPI[]): ContaContabil[] {
  const map = new Map<number, ContaContabil>();
  const visit = (c: ContaAPI) => {
    if (!c?.id || map.has(c.id)) return;
    const { filhos, ...rest } = c;
    map.set(c.id, { ...rest, filhos: undefined });
    (filhos ?? []).forEach(visit);
  };
  rows.forEach(visit);
  return Array.from(map.values()).sort((a, b) => a.codigo.localeCompare(b.codigo, 'pt-BR'));
}

export const estoqueService = {
  getAll: async (): Promise<EstoqueItem[]> => (await api.get<EstoqueItem[]>('estoque/')).data,
  listSaldosPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<EstoqueSaldoItem>>('estoque/saldos/', {
      params: buildListParams(params),
    });
    return response.data;
  },
  getSaldos: async (params?: Record<string, string | number | boolean>) => {
    const q = { ...params } as Record<string, string | number | boolean>;
    if (!q.page) q.page = 1;
    const response = await api.get<EstoqueSaldoItem[] | PaginatedResponse<EstoqueSaldoItem>>('estoque/saldos/', {
      params: q,
    });
    return unwrapListResults(response.data);
  },
  getSaldosConsolidados: async (params?: { produto_id?: number }): Promise<SaldoConsolidadoProduto | SaldoConsolidadoProduto[]> =>
    (await api.get<SaldoConsolidadoProduto | SaldoConsolidadoProduto[]>('estoque/saldos-consolidados/', { params })).data,
  listKardexPaginated: async (params?: KardexEstoqueFiltros & { page?: number; page_size?: number }): Promise<KardexEstoqueResponse> =>
    (await api.get<KardexEstoqueResponse>('estoque/kardex/', { params })).data,
};

export type SugestaoAtendimentoConferencia = {
  atendimento_id: number;
  numero_nf_saida: string;
  cliente_id: number;
  cliente_nome: string;
  status: string;
  quantidade_pendente: string;
  quantidade_sugerida: string;
  dias_em_aberto: number;
  criado_em: string | null;
};

export type SugestoesAtendimentoResponse = {
  item_conferencia_id: number;
  produto_id: number;
  quantidade_nf: string;
  quantidade_disponivel: string;
  quantidade_alocada: string;
  sugestoes: SugestaoAtendimentoConferencia[];
  vinculos: VinculoAtendimentoConferencia[];
};

export type VinculoAtendimentoConferencia = {
  linha_id: number;
  atendimento_id: number;
  numero_nf_saida: string;
  cliente_nome: string;
  quantidade: string;
  status_atendimento: string;
};

export type LinhaConferenciaElegivel = {
  item_conferencia_id: number;
  conferencia_id: number;
  nf_numero: string;
  quantidade_nf: string;
  quantidade_disponivel: string;
  unidade_nf: string;
  corrida: string;
  lote: string;
};

export type VinculoAtendimentoResult = {
  atendimento: {
    id: number;
    status: string;
    quantidade_comprometida: string;
    quantidade_atendida: string;
    quantidade_pendente: string;
    numero_nf_saida: string;
    cliente_nome: string;
  };
  linha: { id: number; quantidade: string } | null;
  saldo_pendente_linha_conferencia: string;
  saldo_pendente_atendimento: string;
};

export const atendimentosEstoqueService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<AtendimentoEstoqueItem>>('atendimentos-estoque/', {
      params: buildListParams(params),
    });
    return response.data;
  },
  list: async (params?: Record<string, string | number | boolean>) => {
    const q = { ...params } as Record<string, string | number | boolean>;
    if (!q.page) q.page = 1;
    const response = await api.get<AtendimentoEstoqueItem[] | PaginatedResponse<AtendimentoEstoqueItem>>(
      'atendimentos-estoque/',
      { params: q },
    );
    return unwrapListResults(response.data);
  },
  sugestoes: async (itemConferenciaId: number): Promise<SugestoesAtendimentoResponse> =>
    (await api.get<SugestoesAtendimentoResponse>('atendimentos-estoque/sugestoes/', { params: { item_conferencia_id: itemConferenciaId } })).data,
  linhasConferenciaElegiveis: async (produtoId: number): Promise<LinhaConferenciaElegivel[]> =>
    (await api.get<LinhaConferenciaElegivel[]>('atendimentos-estoque/linhas-conferencia-elegiveis/', { params: { produto_id: produtoId } })).data,
  vincular: async (payload: { item_conferencia_id: number; atendimento_id: number; quantidade: string }) =>
    (await api.post<VinculoAtendimentoResult>('atendimentos-estoque/vincular/', payload)).data,
  desvincular: async (linhaId: number) =>
    (await api.post<VinculoAtendimentoResult>('atendimentos-estoque/desvincular/', { linha_id: linhaId })).data,
};

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const apuracaoService = {
  /** Não altera `params`; repassa ao axios como enviado pela tela. */
  get: async (
    params: Record<string, string | number | boolean>,
    opts?: { signal?: AbortSignal },
  ): Promise<ApuracaoFiscalPayload> =>
    (
      await api.get<ApuracaoFiscalPayload>('fiscal/apuracao/', {
        params,
        signal: opts?.signal,
        headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
      })
    ).data,

  exportCsvApuracao: async (params: Record<string, string | number | boolean>) => {
    const res = await api.get<Blob>('fiscal/apuracao/', {
      params: { ...params, formato: 'csv_apuracao' },
      responseType: 'blob',
      headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
    });
    downloadBlob(res.data, 'apuracao_fiscal.csv');
  },

  exportCsvAlertas: async (params: Record<string, string | number | boolean>) => {
    const res = await api.get<Blob>('fiscal/apuracao/', {
      params: { ...params, formato: 'csv_alertas' },
      responseType: 'blob',
      headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
    });
    downloadBlob(res.data, 'apuracao_fiscal_alertas.csv');
  },
};

export const contabilService = {
  getContas: async () => {
    const rows = (await api.get<ContaAPI[]>('contas/')).data;
    return flattenContas(rows);
  },
  createConta: async (data: Omit<ContaContabil, 'id'>) => {
    const { filhos: _f, ...rest } = data;
    return (await api.post<ContaContabil>('contas/', rest)).data;
  },
  updateConta: async (id: number, data: Partial<ContaContabil>) => {
    const { filhos: _f, ...rest } = data;
    return (await api.patch<ContaContabil>(`contas/${id}/`, rest)).data;
  },
  deleteConta: async (id: number) => {
    await api.delete(`contas/${id}/`);
  },
  getBalancete: async (mes: number, ano: number): Promise<Balancete[]> =>
    (await api.get<Balancete[]>('balancete/', { params: { mes, ano } })).data,
};
