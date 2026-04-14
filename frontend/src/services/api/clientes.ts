import api from './config';
import type { Cliente } from '@/types';

const path = 'clientes/';

export const clientesService = {
  getAll: async () => (await api.get<Cliente[]>(path)).data,
  getById: async (id: number) => (await api.get<Cliente>(`${path}${id}/`)).data,
  create: async (data: Omit<Cliente, 'id'>) => (await api.post<Cliente>(path, data)).data,
  update: async (id: number, data: Partial<Cliente>) =>
    (await api.patch<Cliente>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
