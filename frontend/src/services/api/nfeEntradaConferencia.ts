import api from './config';
import type { NFeEntradaConferencia } from '@/types';

const base = 'nf-entradas-historicas-importadas/';

export const nfeEntradaConferenciaService = {
  get: async (nfeHistoricaId: number) =>
    (await api.get<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/conferencia/`)).data,
  salvar: async (nfeHistoricaId: number, payload: Partial<NFeEntradaConferencia>) =>
    (await api.post<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/conferencia/`, payload)).data,
  prepararEstoque: async (nfeHistoricaId: number) =>
    (await api.post<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/preparar-estoque/`, {})).data,
};
