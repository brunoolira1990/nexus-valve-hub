import api from './config';
import type { Transportadora } from '@/types';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';

const path = 'transportadoras/';

export const transportadorasService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<Transportadora>>(path, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<Transportadora[] | PaginatedResponse<Transportadora>>(path, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<Transportadora>(`${path}${id}/`)).data,
  create: async (data: Omit<Transportadora, 'id'>) => (await api.post<Transportadora>(path, data)).data,
  update: async (id: number, data: Partial<Transportadora>) =>
    (await api.patch<Transportadora>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  search: async (term: string, limit = 20) =>
    unwrapListResults(
      (await api.get<Transportadora[] | PaginatedResponse<Transportadora>>(path, { params: { search: term, limit } }))
        .data,
    ),
};
