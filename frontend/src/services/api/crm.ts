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

const leadsPath = 'crm/leads/';
const oportunidadesPath = 'crm/oportunidades/';

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
