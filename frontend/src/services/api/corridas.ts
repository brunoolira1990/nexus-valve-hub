import api from './config';
import type { Corrida } from '@/types';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';

const path = 'corridas/';

function stripReadOnly(c: Partial<Corrida>): Record<string, unknown> {
  const x: Record<string, unknown> = { ...c };
  delete x.id;
  delete x.produto_nome;
  delete x.fornecedor_nome;
  return x;
}

export const corridasService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<Corrida>>(path, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<Corrida[] | PaginatedResponse<Corrida>>(path, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<Corrida>(`${path}${id}/`)).data,
  create: async (data: Omit<Corrida, 'id'>) => (await api.post<Corrida>(path, stripReadOnly(data))).data,
  update: async (id: number, data: Partial<Corrida>) =>
    (await api.patch<Corrida>(`${path}${id}/`, stripReadOnly(data))).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
