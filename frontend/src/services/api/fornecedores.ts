import api from './config';
import type { Fornecedor } from '@/types';

const path = 'fornecedores/';

export const fornecedoresService = {
  getAll: async () => (await api.get<Fornecedor[]>(path)).data,
  getById: async (id: number) => (await api.get<Fornecedor>(`${path}${id}/`)).data,
  create: async (data: Omit<Fornecedor, 'id'>) => (await api.post<Fornecedor>(path, data)).data,
  update: async (id: number, data: Partial<Fornecedor>) =>
    (await api.patch<Fornecedor>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
