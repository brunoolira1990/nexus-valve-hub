import api from './config';
import type { Transportadora } from '@/types';

const path = 'transportadoras/';
type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(payload: ListResponse<T>): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.results)) return payload.results;
  throw new Error('Resposta inesperada da API.');
}

export const transportadorasService = {
  getAll: async () => unwrapList((await api.get<ListResponse<Transportadora>>(path)).data),
  getById: async (id: number) => (await api.get<Transportadora>(`${path}${id}/`)).data,
  create: async (data: Omit<Transportadora, 'id'>) => (await api.post<Transportadora>(path, data)).data,
  update: async (id: number, data: Partial<Transportadora>) =>
    (await api.patch<Transportadora>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  search: async (term: string, limit = 20) =>
    unwrapList((await api.get<ListResponse<Transportadora>>(path, { params: { search: term, limit } })).data),
};
