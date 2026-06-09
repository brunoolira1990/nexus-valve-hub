import api from './config';
import type { RegraFiscalEntrada } from '@/types';

const path = 'regras-fiscais-entrada/';

export const regrasFiscaisEntradaService = {
  getAll: async (params?: { escopo_id?: number; cenario_id?: number }) =>
    (await api.get<RegraFiscalEntrada[]>(path, { params })).data,
  getById: async (id: number) => (await api.get<RegraFiscalEntrada>(`${path}${id}/`)).data,
  create: async (data: Omit<RegraFiscalEntrada, 'id' | 'criado_em' | 'atualizado_em'>) =>
    (await api.post<RegraFiscalEntrada>(path, data)).data,
  update: async (id: number, data: Partial<RegraFiscalEntrada>) =>
    (await api.patch<RegraFiscalEntrada>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  duplicar: async (
    id: number,
    data: {
      uf_origem?: string;
      uf_destino?: string;
      cfop_origem?: string;
      cfop_entrada?: string;
      sobrescrever?: boolean;
    },
  ) => (await api.post<RegraFiscalEntrada>(`${path}${id}/duplicar/`, data)).data,
};
