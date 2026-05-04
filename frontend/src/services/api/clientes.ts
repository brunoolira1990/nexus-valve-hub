import api from './config';
import type { Cliente } from '@/types';

const path = 'clientes/';
type ListResponse<T> = T[] | { results?: T[] };

export const clientesService = {
  getAll: async () => {
    const response = await api.get<ListResponse<Cliente>>(path);
    const payload = response.data;
    if (Array.isArray(payload)) return payload;
    if (payload && Array.isArray(payload.results)) return payload.results;
    throw new Error('Resposta inesperada da API de clientes.');
  },
  getById: async (id: number) => (await api.get<Cliente>(`${path}${id}/`)).data,
  create: async (data: Omit<Cliente, 'id'>) => (await api.post<Cliente>(path, data)).data,
  update: async (id: number, data: Partial<Cliente>) =>
    (await api.patch<Cliente>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  search: async (term: string, limit = 20) => {
    const response = await api.get<ListResponse<Cliente>>(path, { params: { search: term, limit } });
    const payload = response.data;
    if (Array.isArray(payload)) return payload;
    if (payload && Array.isArray(payload.results)) return payload.results;
    throw new Error('Resposta inesperada da API de clientes.');
  },
};
