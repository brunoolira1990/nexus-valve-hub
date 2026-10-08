import api from './config';
import { buildListParams, type ListQueryParams } from '@/lib/apiList';
import type { ExpedicaoItem, ExpedicaoListResponse, ExpedicaoPayload, ExpedicaoResumo, StatusExpedicao } from '@/types/expedicao';

const path = 'expedicoes/';

export const expedicaoService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<ExpedicaoListResponse>(path, { params: buildListParams(params) });
    return response.data;
  },
  getById: async (id: number) => (await api.get<ExpedicaoItem>(`${path}${id}/`)).data,
  create: async (data: ExpedicaoPayload) => (await api.post<ExpedicaoItem>(path, data)).data,
  update: async (id: number, data: Partial<ExpedicaoPayload>) =>
    (await api.patch<ExpedicaoItem>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  resumo: async () => (await api.get<ExpedicaoResumo>(`${path}resumo/`)).data,
  alterarStatus: async (id: number, payload: { status: StatusExpedicao; ocorrencia_descricao?: string }) =>
    (await api.post<ExpedicaoItem>(`${path}${id}/alterar-status/`, payload)).data,
  cancelar: async (id: number, motivo?: string) =>
    (await api.post<ExpedicaoItem>(`${path}${id}/cancelar/`, { motivo: motivo || '' })).data,
  etiquetasPdf: async (id: number) =>
    (await api.post<Blob>(`${path}${id}/etiquetas-pdf/`, undefined, { responseType: 'blob' })).data,
};
