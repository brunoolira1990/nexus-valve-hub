import api from './config';
import type { RegraFiscal } from '@/types';

const path = 'regras-fiscais/';

export const regrasFiscaisService = {
  getAll: async () => (await api.get<RegraFiscal[]>(path)).data,
  getById: async (id: number) => (await api.get<RegraFiscal>(`${path}${id}/`)).data,
  create: async (data: Omit<RegraFiscal, 'id'>) => (await api.post<RegraFiscal>(path, data)).data,
  update: async (id: number, data: Partial<RegraFiscal>) =>
    (await api.patch<RegraFiscal>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
