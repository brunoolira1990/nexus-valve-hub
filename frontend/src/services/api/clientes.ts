import api from './config';
import type { Cliente } from '@/types';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';

const path = 'clientes/';

export const clientesService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<Cliente>>(path, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<Cliente[] | PaginatedResponse<Cliente>>(path, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<Cliente>(`${path}${id}/`)).data,
  create: async (data: Omit<Cliente, 'id'>) => (await api.post<Cliente>(path, data)).data,
  update: async (id: number, data: Partial<Cliente>) =>
    (await api.patch<Cliente>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  search: async (term: string, limit = 20) => {
    const response = await api.get<Cliente[] | PaginatedResponse<Cliente>>(path, {
      params: { search: term, limit },
    });
    return unwrapListResults(response.data);
  },
};
