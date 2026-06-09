import api from './config';
import { buildListParams, type ListQueryParams, type PaginatedResponse, unwrapListResults } from '@/lib/apiList';

const base = 'nf-entradas-historicas-importadas/';

export type NFeEntradaHistoricaList = {
  id: number;
  numero: string;
  serie: string;
  chave_acesso: string;
  dh_emissao: string;
  valor_total_nf: number;
  emit_json?: Record<string, unknown>;
  fornecedor_nome: string;
  fornecedor_cnpj: string;
  fornecedor_id?: number | null;
};

export const nfeEntradaHistoricaImportadaService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<NFeEntradaHistoricaList>>(base, {
      params: buildListParams(params),
    });
    return response.data;
  },
  list: async (params?: ListQueryParams) => {
    const response = await api.get<NFeEntradaHistoricaList[] | PaginatedResponse<NFeEntradaHistoricaList>>(base, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
};
