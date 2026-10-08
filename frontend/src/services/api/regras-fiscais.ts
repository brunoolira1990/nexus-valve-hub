import { isAxiosError } from 'axios';
import api from './config';
import type { RegraFiscal } from '@/types';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';

const path = 'regras-fiscais/';

export const regrasFiscaisService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<RegraFiscal>>(path, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<RegraFiscal[] | PaginatedResponse<RegraFiscal>>(path, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 500 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<RegraFiscal>(`${path}${id}/`)).data,
  create: async (data: Omit<RegraFiscal, 'id'>) => (await api.post<RegraFiscal>(path, data)).data,
  update: async (id: number, data: Partial<RegraFiscal>) =>
    (await api.patch<RegraFiscal>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  buscar: async (params: { ncm: string; uf_origem: string; uf_destino: string; operacao: string }) => {
    try {
      return (await api.get<RegraFiscal>(`${path}buscar/`, { params })).data;
    } catch (e: unknown) {
      if (isAxiosError(e) && e.response?.status === 404) return null;
      throw e;
    }
  },
  checklistProducao: async () =>
    (await api.get<{
      checklist_fiscal?: { item: string; ok: boolean; nota?: string }[];
      checklist_saida?: { item: string; ok: boolean; nota?: string }[];
      checklist_entrada?: { item: string; ok: boolean; nota?: string }[];
      metricas?: Record<string, number | string | boolean>;
      criticos?: { mensagem: string }[];
      avisos?: { mensagem: string }[];
      avisos_entrada?: { mensagem: string }[];
      bloqueios_por_fluxo?: { nfe_entrada?: string[] };
    }>(`${path}checklist-producao/`)).data,
};
