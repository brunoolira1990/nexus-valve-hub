import api from './config';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';

export type CrmLead = {
  id: number;
  nome: string;
  cnpj: string;
  nome_contato: string;
  email: string;
  telefone: string;
  cidade: string;
  uf: string;
  origem: string;
  status: string;
  responsavel_id: number | null;
  responsavel_nome: string;
  cliente_id: number | null;
  cliente_nome: string;
  observacoes: string;
  criado_em: string;
  atualizado_em: string;
};

export type CrmOportunidade = {
  id: number;
  titulo: string;
  status: string;
  etapa: string;
  lead_id: number | null;
  lead_nome: string;
  cliente_id: number | null;
  cliente_nome: string;
  responsavel_id: number | null;
  responsavel_nome: string;
  valor_estimado: string;
  probabilidade: number;
  previsao_fechamento: string | null;
  proxima_acao: string | null;
  motivo_perda: string;
  observacoes: string;
  criado_em: string;
  atualizado_em: string;
};

export type CrmLeadPayload = Partial<Omit<CrmLead, 'id' | 'responsavel_nome' | 'cliente_nome' | 'criado_em' | 'atualizado_em'>>;
export type CrmOportunidadePayload = Partial<Omit<CrmOportunidade, 'id' | 'lead_nome' | 'cliente_nome' | 'responsavel_nome' | 'criado_em' | 'atualizado_em'>>;

export type CrmAtividade = {
  id: number;
  titulo: string;
  tipo: string;
  status: string;
  lead_id: number | null;
  lead_nome: string;
  oportunidade_id: number | null;
  oportunidade_titulo: string;
  responsavel_id: number | null;
  responsavel_nome: string;
  descricao: string;
  agendada_para: string | null;
  concluida_em: string | null;
  criado_em: string;
  atualizado_em: string;
};

export type CrmAtividadePayload = Partial<Omit<CrmAtividade, 'id' | 'lead_nome' | 'oportunidade_titulo' | 'responsavel_nome' | 'criado_em' | 'atualizado_em'>>;

export type CrmHistoricoLead = {
  id: number;
  lead_id: number;
  lead_nome: string;
  evento: string;
  titulo: string;
  descricao: string;
  atividade_id: number | null;
  realizado_por_id: number | null;
  realizado_por_nome: string;
  dados: Record<string, unknown>;
  criado_em: string;
};

export type CrmLeadListParams = ListQueryParams & {
  status?: string;
  origem?: string;
  responsavel_id?: number | string;
};

export type CrmOportunidadeListParams = ListQueryParams & {
  status?: string;
  etapa?: string;
  responsavel_id?: number | string;
  cliente_id?: number | string;
};

export type CrmAtividadeListParams = ListQueryParams & {
  status?: string;
  tipo?: string;
  lead_id?: number | string;
  oportunidade_id?: number | string;
  responsavel_id?: number | string;
};

export type CrmHistoricoLeadListParams = ListQueryParams & {
  lead_id?: number | string;
  evento?: string;
};

const leadsPath = 'crm/leads/';
const oportunidadesPath = 'crm/oportunidades/';
const atividadesPath = 'crm/atividades/';
const historicoLeadsPath = 'crm/historico-leads/';

export const crmService = {
  leads: {
    listPaginated: async (params?: CrmLeadListParams) =>
      (await api.get<PaginatedResponse<CrmLead>>(leadsPath, { params: buildListParams(params) })).data,
    getAll: async (params?: CrmLeadListParams) =>
      unwrapListResults(await api.get<CrmLead[] | PaginatedResponse<CrmLead>>(leadsPath, { params: { ...buildListParams(params), limit: params?.limit ?? 100 } }).then((response) => response.data)),
    create: async (payload: CrmLeadPayload) => (await api.post<CrmLead>(leadsPath, payload)).data,
    update: async (id: number, payload: CrmLeadPayload) =>
      (await api.patch<CrmLead>(`${leadsPath}${id}/`, payload)).data,
    delete: async (id: number) => {
      await api.delete(`${leadsPath}${id}/`);
    },
  },
  atividades: {
    listPaginated: async (params?: CrmAtividadeListParams) =>
      (await api.get<PaginatedResponse<CrmAtividade>>(atividadesPath, { params: buildListParams(params) })).data,
    getAll: async (params?: CrmAtividadeListParams) =>
      unwrapListResults(await api.get<CrmAtividade[] | PaginatedResponse<CrmAtividade>>(atividadesPath, { params: { ...buildListParams(params), limit: params?.limit ?? 100 } }).then((response) => response.data)),
    create: async (payload: CrmAtividadePayload) =>
      (await api.post<CrmAtividade>(atividadesPath, payload)).data,
    update: async (id: number, payload: CrmAtividadePayload) =>
      (await api.patch<CrmAtividade>(`${atividadesPath}${id}/`, payload)).data,
    delete: async (id: number) => {
      await api.delete(`${atividadesPath}${id}/`);
    },
  },
  historicoLeads: {
    listPaginated: async (params?: CrmHistoricoLeadListParams) =>
      (await api.get<PaginatedResponse<CrmHistoricoLead>>(historicoLeadsPath, { params: buildListParams(params) })).data,
  },
  oportunidades: {
    listPaginated: async (params?: CrmOportunidadeListParams) =>
      (await api.get<PaginatedResponse<CrmOportunidade>>(oportunidadesPath, { params: buildListParams(params) })).data,
    getAll: async (params?: CrmOportunidadeListParams) =>
      unwrapListResults(await api.get<CrmOportunidade[] | PaginatedResponse<CrmOportunidade>>(oportunidadesPath, { params: { ...buildListParams(params), limit: params?.limit ?? 100 } }).then((response) => response.data)),
    create: async (payload: CrmOportunidadePayload) =>
      (await api.post<CrmOportunidade>(oportunidadesPath, payload)).data,
    update: async (id: number, payload: CrmOportunidadePayload) =>
      (await api.patch<CrmOportunidade>(`${oportunidadesPath}${id}/`, payload)).data,
    delete: async (id: number) => {
      await api.delete(`${oportunidadesPath}${id}/`);
    },
  },
};
