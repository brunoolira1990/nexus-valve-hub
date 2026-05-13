import api from './config';
import type { ApuracaoFiscalPayload, Balancete, ContaContabil, EstoqueItem, EstoqueSaldoItem } from '@/types';

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
  getSaldos: async (params?: Record<string, string | number | boolean>): Promise<EstoqueSaldoItem[]> =>
    (await api.get<EstoqueSaldoItem[]>('estoque/saldos/', { params })).data,
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
