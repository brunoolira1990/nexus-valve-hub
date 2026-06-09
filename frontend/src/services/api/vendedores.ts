import api from './config';
import type { Vendedor } from '@/types';

const path = 'vendedores/';
type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(payload: ListResponse<T>): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.results)) return payload.results;
  throw new Error('Resposta inesperada da API de vendedores.');
}

export const vendedoresService = {
  getById: async (id: number) => (await api.get<Vendedor>(`${path}${id}/`)).data,
  create: async (data: Omit<Vendedor, 'id' | 'criado_em' | 'atualizado_em'>) =>
    (await api.post<Vendedor>(path, data)).data,
  update: async (id: number, data: Partial<Vendedor>) =>
    (await api.patch<Vendedor>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  search: async (term: string, limit = 20) => {
    const response = await api.get<ListResponse<Vendedor>>(path, { params: { search: term, limit, ativo: true } });
    return unwrapList(response.data);
  },
  getVinculado: async (): Promise<Vendedor | null> => {
    const response = await api.get<Vendedor | null>(`${path}vinculado/`);
    const data = response.data;
    if (!data || typeof data !== 'object' || !('id' in data)) return null;
    return data;
  },
};
