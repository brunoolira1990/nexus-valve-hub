import api from './config';
import type { Usuario } from '@/types';

const path = 'usuarios/';
type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(payload: ListResponse<T>): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.results)) return payload.results;
  throw new Error('Resposta inesperada da API de usuários.');
}

export const usuariosService = {
  getAll: async (params?: { search?: string; limit?: number; ativo?: boolean }) => {
    const query: Record<string, string | number> = {};
    if (params?.search?.trim()) query.search = params.search.trim();
    if (params?.limit) query.limit = params.limit;
    if (params?.ativo === false) query.ativo = 'false';
    const response = await api.get<ListResponse<Usuario>>(path, { params: query });
    return unwrapList(response.data);
  },
  search: async (term: string, limit = 25) => usuariosService.getAll({ search: term, limit }),
};
