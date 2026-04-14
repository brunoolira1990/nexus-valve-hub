import api from './config';
import type { Corrida } from '@/types';

const path = 'corridas/';

function stripReadOnly(c: Partial<Corrida>): Record<string, unknown> {
  const x: Record<string, unknown> = { ...c };
  delete x.id;
  delete x.produto_nome;
  delete x.fornecedor_nome;
  return x;
}

export const corridasService = {
  getAll: async () => (await api.get<Corrida[]>(path)).data,
  getById: async (id: number) => (await api.get<Corrida>(`${path}${id}/`)).data,
  create: async (data: Omit<Corrida, 'id'>) => (await api.post<Corrida>(path, stripReadOnly(data))).data,
  update: async (id: number, data: Partial<Corrida>) =>
    (await api.patch<Corrida>(`${path}${id}/`, stripReadOnly(data))).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
