import api from './config';
import type { Fornecedor } from '@/types';

const path = 'fornecedores/';
type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(payload: ListResponse<T>): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.results)) return payload.results;
  throw new Error('Resposta inesperada da API.');
}

export const fornecedoresService = {
  getAll: async () => unwrapList((await api.get<ListResponse<Fornecedor>>(path)).data),
  getById: async (id: number) => (await api.get<Fornecedor>(`${path}${id}/`)).data,
  create: async (data: Omit<Fornecedor, 'id'>) => (await api.post<Fornecedor>(path, data)).data,
  update: async (id: number, data: Partial<Fornecedor>) =>
    (await api.patch<Fornecedor>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  search: async (term: string, limit = 20) =>
    unwrapList((await api.get<ListResponse<Fornecedor>>(path, { params: { search: term, limit } })).data),
};
