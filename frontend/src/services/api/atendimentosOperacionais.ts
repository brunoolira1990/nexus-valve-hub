import api from './config';
import { buildListParams, type ListQueryParams } from '@/lib/apiList';
import type {
  AtendimentoOperacionalItem,
  AtendimentosOperacionaisKpis,
  AtendimentosOperacionaisListResponse,
} from '@/types/atendimentosOperacionais';

const base = 'atendimentos-operacionais/';

export const atendimentosOperacionaisService = {
  listPaginated: async (
    params?: ListQueryParams & Record<string, string | number | boolean>,
  ): Promise<AtendimentosOperacionaisListResponse> => {
    const response = await api.get<AtendimentosOperacionaisListResponse>(base, {
      params: buildListParams({ ...params, incluir_kpis: true }),
    });
    return response.data;
  },

  get: async (id: number): Promise<AtendimentoOperacionalItem> =>
    (await api.get<AtendimentoOperacionalItem>(`${base}${id}/`)).data,

  kpis: async (params?: Record<string, string | number | boolean>) =>
    (await api.get<AtendimentosOperacionaisKpis>(`${base}kpis/`, { params })).data,
};
