import api from './config';
import type { Transportadora } from '@/types';

const path = 'transportadoras/';

export const transportadorasService = {
  getAll: async () => (await api.get<Transportadora[]>(path)).data,
  getById: async (id: number) => (await api.get<Transportadora>(`${path}${id}/`)).data,
  create: async (data: Omit<Transportadora, 'id'>) => (await api.post<Transportadora>(path, data)).data,
  update: async (id: number, data: Partial<Transportadora>) =>
    (await api.patch<Transportadora>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
