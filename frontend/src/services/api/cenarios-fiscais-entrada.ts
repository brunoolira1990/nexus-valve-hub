import api from './config';
import type {
  CenarioFiscalEntrada,
  CenarioFiscalEntradaEscopo,
  DestinoCopiaConfiguracaoFiscal,
  MatrizEscopoFiscalEntrada,
  RegraFiscalEntrada,
  ResultadoCopiaConfiguracaoFiscal,
} from '@/types';

const path = 'cenarios-fiscais-entrada/';

type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(data: ListResponse<T> | null | undefined): T[] {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export const cenariosFiscaisEntradaService = {
  getAll: async () => unwrapList((await api.get<ListResponse<CenarioFiscalEntrada>>(path)).data),
  getById: async (id: number) => (await api.get<CenarioFiscalEntrada>(`${path}${id}/`)).data,
  getEscopos: async (cenarioId: number) =>
    unwrapList((await api.get<ListResponse<CenarioFiscalEntradaEscopo>>(`${path}${cenarioId}/escopos/`)).data),
  createEscopo: async (
    cenarioId: number,
    data: Pick<CenarioFiscalEntradaEscopo, 'tipo_escopo' | 'ncm' | 'produto_id' | 'ativo' | 'prioridade_escopo'>,
  ) => (await api.post<CenarioFiscalEntradaEscopo>(`${path}${cenarioId}/escopos/`, data)).data,
  getConfiguracoesEscopo: async (cenarioId: number, escopoId: number) =>
    unwrapList(
      (await api.get<ListResponse<RegraFiscalEntrada>>(`${path}${cenarioId}/escopos/${escopoId}/configuracoes/`)).data,
    ),
  getMatrizEscopo: async (cenarioId: number, escopoId: number) =>
    (await api.get<MatrizEscopoFiscalEntrada>(`${path}${cenarioId}/escopos/${escopoId}/matriz/`)).data,
  copiarConfiguracao: async (
    cenarioId: number,
    escopoId: number,
    data: {
      origem_regra_id: number;
      destinos: DestinoCopiaConfiguracaoFiscal[];
      sobrescrever?: boolean;
    },
  ) =>
    (
      await api.post<ResultadoCopiaConfiguracaoFiscal>(
        `${path}${cenarioId}/escopos/${escopoId}/copiar-configuracao/`,
        data,
      )
    ).data,
};
