import api from './config';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
} from '@/lib/apiList';

export type Notificacao = {
  id: number;
  modulo: string;
  modulo_label: string;
  tipo: string;
  tipo_label: string;
  prioridade: string;
  prioridade_label: string;
  titulo: string;
  mensagem: string;
  url_destino: string;
  objeto_tipo: string;
  objeto_id: number | null;
  lida: boolean;
  arquivada: boolean;
  criado_em: string;
  lida_em: string | null;
  arquivada_em: string | null;
};

export type NotificacaoListParams = ListQueryParams & {
  modulo?: string;
  tipo?: string;
  prioridade?: string;
  lida?: 'true' | 'false';
  incluir_arquivadas?: 'true';
  busca?: string;
};

const notificacoesPath = 'notificacoes/';

export const notificacoesService = {
  listPaginated: async (params?: NotificacaoListParams) => {
    const query = { ...(params || {}) };
    if (!query.busca && query.search) query.busca = query.search;
    delete query.search;
    return (await api.get<PaginatedResponse<Notificacao>>(notificacoesPath, {
      params: buildListParams(query),
    })).data;
  },

  countNaoLidas: async () =>
    (await api.get<{ count: number }>(`${notificacoesPath}nao-lidas-count/`)).data.count,

  marcarLida: async (id: number) =>
    (await api.post<Notificacao>(`${notificacoesPath}${id}/marcar-lida/`)).data,

  marcarTodasLidas: async () =>
    (await api.post<{ atualizadas: number; count: number }>(`${notificacoesPath}marcar-todas-lidas/`)).data,

  arquivar: async (id: number) =>
    (await api.post<Notificacao>(`${notificacoesPath}${id}/arquivar/`)).data,
};
