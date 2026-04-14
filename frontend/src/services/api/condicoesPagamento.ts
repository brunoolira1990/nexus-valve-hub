import api from './config';
import type { CondicaoPagamento } from '@/types';

const path = 'condicoes-pagamento/';

export const condicoesPagamentoService = {
  getAll: async () => (await api.get<CondicaoPagamento[]>(path)).data,
  getById: async (id: number) => (await api.get<CondicaoPagamento>(`${path}${id}/`)).data,
  create: async (data: Omit<CondicaoPagamento, 'id'>) =>
    (await api.post<CondicaoPagamento>(path, data)).data,
  update: async (id: number, data: Partial<Omit<CondicaoPagamento, 'id'>>) =>
    (await api.patch<CondicaoPagamento>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
