/**
 * Service para o endpoint /api/materiais/ (Material — Sprint 3.5A).
 */

import api from './config';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
} from '@/lib/apiList';
import type { Material, MaterialFormState } from '@/types/material';

const path = 'materiais/';

type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(payload: ListResponse<T>): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.results)) return payload.results;
  throw new Error('Resposta inesperada da API.');
}

export type MateriaisListParams = ListQueryParams & {
  categoria?: string;
  ativo?: string;
};

export const materiaisService = {
  listPaginated: async (params?: MateriaisListParams) => {
    const response = await api.get<PaginatedResponse<Material>>(path, {
      params: buildListParams(params),
    });
    return response.data;
  },

  getAll: async (params?: MateriaisListParams) => {
    const response = await api.get<ListResponse<Material>>(path, {
      params: buildListParams({ limit: 200, ...params }),
    });
    return unwrapList(response.data);
  },

  getById: async (id: number) =>
    (await api.get<Material>(`${path}${id}/`)).data,

  create: async (data: MaterialFormState) =>
    (await api.post<Material>(path, data)).data,

  update: async (id: number, data: Partial<MaterialFormState>) =>
    (await api.patch<Material>(`${path}${id}/`, data)).data,

  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },

  search: async (term: string, limit = 30) => {
    const response = await api.get<ListResponse<Material>>(path, {
      params: buildListParams({ search: term, limit }),
    });
    return unwrapList(response.data);
  },
};
