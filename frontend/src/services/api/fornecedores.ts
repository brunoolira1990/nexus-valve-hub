import api from './config';
import type { Fornecedor } from '@/types';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';

const path = 'fornecedores/';

export const fornecedoresService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<Fornecedor>>(path, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<Fornecedor[] | PaginatedResponse<Fornecedor>>(path, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<Fornecedor>(`${path}${id}/`)).data,
  create: async (data: Omit<Fornecedor, 'id'>) => (await api.post<Fornecedor>(path, data)).data,
  update: async (id: number, data: Partial<Fornecedor>) =>
    (await api.patch<Fornecedor>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  search: async (term: string, limit = 20) =>
    unwrapListResults(
      (await api.get<Fornecedor[] | PaginatedResponse<Fornecedor>>(path, { params: { search: term, limit } })).data,
    ),
};
