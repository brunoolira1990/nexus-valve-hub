import api from './config';
import type { Colaborador, ColaboradorFuncao } from '@/types';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';

const path = 'colaboradores/';

export type ColaboradorListParams = ListQueryParams & {
  funcao?: ColaboradorFuncao | '';
  ativo?: boolean | 'all';
};

export const colaboradoresService = {
  listPaginated: async (params?: ColaboradorListParams) => {
    const q = buildListParams(params);
    if (params?.ativo === true) q.ativo = 'true';
    if (params?.ativo === false) q.ativo = 'false';
    if (params?.funcao) q.funcao = params.funcao;
    const response = await api.get<PaginatedResponse<Colaborador>>(path, { params: q });
    return response.data;
  },
  getAll: async (params?: ColaboradorListParams) => {
    const q = buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 });
    if (params?.ativo === true) q.ativo = 'true';
    if (params?.funcao) q.funcao = params.funcao;
    const response = await api.get<Colaborador[] | PaginatedResponse<Colaborador>>(path, { params: q });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<Colaborador>(`${path}${id}/`)).data,
  create: async (data: Omit<Colaborador, 'id' | 'vendedor_id' | 'criado_em' | 'atualizado_em' | 'usuario_login'>) =>
    (await api.post<Colaborador>(path, data)).data,
  update: async (id: number, data: Partial<Colaborador>) =>
    (await api.patch<Colaborador>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  search: async (term: string, options?: { limit?: number; funcao?: ColaboradorFuncao; ativo?: boolean }) => {
    const params: Record<string, string | number> = { search: term, limit: options?.limit ?? 25 };
    if (options?.funcao) params.funcao = options.funcao;
    if (options?.ativo !== false) params.ativo = 'true';
    const response = await api.get<Colaborador[] | PaginatedResponse<Colaborador>>(path, { params });
    return unwrapListResults(response.data);
  },
  getVinculado: async (): Promise<Colaborador | null> => {
    const response = await api.get<Colaborador | null>(`${path}vinculado/`);
    const data = response.data;
    if (!data || typeof data !== 'object' || !('id' in data)) return null;
    return data;
  },
  criarUsuario: async (
    id: number,
    payload: {
      email: string;
      nome: string;
      perfil: string;
      ativo?: boolean;
      senha: string;
      confirmar_senha: string;
    },
  ) => (await api.post<Colaborador>(`${path}${id}/criar-usuario/`, payload)).data,
  redefinirSenha: async (
    id: number,
    payload: { nova_senha: string; confirmar_senha: string },
  ) => (await api.post<Colaborador & { mensagem?: string }>(`${path}${id}/redefinir-senha/`, payload)).data,
  vincularUsuario: async (id: number, payload: { usuario_id: number; perfil?: string }) =>
    (await api.post<Colaborador>(`${path}${id}/vincular-usuario/`, payload)).data,
  definirPerfil: async (id: number, perfil: string) =>
    (await api.post<Colaborador>(`${path}${id}/definir-perfil-acesso/`, { perfil })).data,
  desativarAcesso: async (id: number, motivo?: string) =>
    (await api.post<Colaborador & { mensagem?: string }>(`${path}${id}/desativar-acesso/`, { motivo: motivo || '' }))
      .data,
  editarAcesso: async (
    id: number,
    payload: {
      ativo?: boolean;
      email?: string;
      perfil?: string;
      is_staff?: boolean;
      is_superuser?: boolean;
    },
  ) => (await api.patch<Colaborador>(`${path}${id}/acesso/`, payload)).data,
  reenviarConvite: async (id: number) =>
    (await api.post<{ mensagem?: string; redefinicao_senha?: { uid: string; token: string } }>(
      `${path}${id}/reenviar-convite/`,
      {},
    )).data,
  listPerfisAcesso: async () =>
    (await api.get<{ value: string; label: string }[]>(`${path}perfis-acesso/`)).data,
};
