import api from './config';
import type {
  CenarioFiscalSaida,
  CenarioFiscalSaidaEscopo,
  MatrizEscopoFiscalSaida,
  RegraFiscalSaida,
} from '@/types';

const path = 'cenarios-fiscais-saida/';

type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(data: ListResponse<T> | null | undefined): T[] {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export const cenariosFiscaisSaidaService = {
  getAll: async () => unwrapList((await api.get<ListResponse<CenarioFiscalSaida>>(path)).data),
  getById: async (id: number) => (await api.get<CenarioFiscalSaida>(`${path}${id}/`)).data,
  getEscopos: async (cenarioId: number) =>
    unwrapList((await api.get<ListResponse<CenarioFiscalSaidaEscopo>>(`${path}${cenarioId}/escopos/`)).data),
  createEscopo: async (
    cenarioId: number,
    data: Pick<CenarioFiscalSaidaEscopo, 'tipo_escopo' | 'ncm' | 'produto_id' | 'ativo' | 'prioridade_escopo'>,
  ) => (await api.post<CenarioFiscalSaidaEscopo>(`${path}${cenarioId}/escopos/`, data)).data,
  getConfiguracoesEscopo: async (cenarioId: number, escopoId: number) =>
    unwrapList(
      (await api.get<ListResponse<RegraFiscalSaida>>(`${path}${cenarioId}/escopos/${escopoId}/configuracoes/`)).data,
    ),
  getMatrizEscopo: async (cenarioId: number, escopoId: number) =>
    (await api.get<MatrizEscopoFiscalSaida>(`${path}${cenarioId}/escopos/${escopoId}/matriz/`)).data,
};
