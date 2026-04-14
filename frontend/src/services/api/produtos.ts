import api from './config';
import type { Produto } from '@/types';

const path = 'produtos/';

function stripReadOnly(p: Partial<Produto>): Record<string, unknown> {
  const x: Record<string, unknown> = { ...p };
  delete x.id;
  delete x.codigo_completo;
  return x;
}

export const produtosService = {
  getAll: async () => (await api.get<Produto[]>(path)).data,
  getById: async (id: number) => (await api.get<Produto>(`${path}${id}/`)).data,
  create: async (data: Omit<Produto, 'id'>) => (await api.post<Produto>(path, stripReadOnly(data))).data,
  update: async (id: number, data: Partial<Produto>) =>
    (await api.patch<Produto>(`${path}${id}/`, stripReadOnly(data))).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
