import { isAxiosError } from 'axios';
import api from './config';
import type {
  BuscaRegraFiscalSaida,
  ChecklistAtivacaoCenarioSaida,
  CoberturaPropostasFiscalSaida,
  ComparativoFiscalSaida,
  RegraFiscalSaida,
} from '@/types';

const path = 'regras-fiscais-saida/';

type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(data: ListResponse<T> | null | undefined): T[] {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export const regrasFiscaisSaidaService = {
  getAll: async (params?: { escopo_id?: number; cenario_id?: number }) => {
    const search = new URLSearchParams();
    if (params?.escopo_id != null) search.set('escopo_id', String(params.escopo_id));
    if (params?.cenario_id != null) search.set('cenario_id', String(params.cenario_id));
    const qs = search.toString();
    return unwrapList((await api.get<ListResponse<RegraFiscalSaida>>(`${path}${qs ? `?${qs}` : ''}`)).data);
  },
  getById: async (id: number) => (await api.get<RegraFiscalSaida>(`${path}${id}/`)).data,
  create: async (data: Partial<RegraFiscalSaida>) => (await api.post<RegraFiscalSaida>(path, data)).data,
  update: async (id: number, data: Partial<RegraFiscalSaida>) =>
    (await api.patch<RegraFiscalSaida>(`${path}${id}/`, data)).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  buscar: async (params: {
    ncm?: string;
    produto_id?: number;
    uf_origem: string;
    uf_destino: string;
    destinatario_contribuinte?: string;
    consumidor_final?: boolean;
    tipo_operacao?: string;
    cenario_id?: number;
  }): Promise<BuscaRegraFiscalSaida | null> => {
    const q: Record<string, string> = {
      uf_origem: params.uf_origem,
      uf_destino: params.uf_destino,
    };
    if (params.ncm) q.ncm = params.ncm;
    if (params.produto_id != null) q.produto_id = String(params.produto_id);
    if (params.destinatario_contribuinte) q.destinatario_contribuinte = params.destinatario_contribuinte;
    if (params.tipo_operacao) q.tipo_operacao = params.tipo_operacao;
    if (params.cenario_id != null) q.cenario_id = String(params.cenario_id);
    if (params.consumidor_final === true) q.consumidor_final = 'true';
    if (params.consumidor_final === false) q.consumidor_final = 'false';
    try {
      return (await api.get<BuscaRegraFiscalSaida>(`${path}buscar/`, { params: q })).data;
    } catch (e: unknown) {
      if (isAxiosError(e) && e.response?.status === 404) {
        const data = e.response.data as BuscaRegraFiscalSaida | undefined;
        if (data?.origem === 'NAO_ENCONTRADA') return data;
        return null;
      }
      throw e;
    }
  },
  comparar: async (params: {
    ncm?: string;
    produto_id?: number;
    uf_origem: string;
    uf_destino: string;
    destinatario_contribuinte?: string;
    consumidor_final?: boolean;
    tipo_operacao?: string;
    cenario_id?: number;
  }): Promise<ComparativoFiscalSaida> => {
    const q: Record<string, string> = {
      uf_origem: params.uf_origem,
      uf_destino: params.uf_destino,
    };
    if (params.ncm) q.ncm = params.ncm;
    if (params.produto_id != null) q.produto_id = String(params.produto_id);
    if (params.destinatario_contribuinte) q.destinatario_contribuinte = params.destinatario_contribuinte;
    if (params.tipo_operacao) q.tipo_operacao = params.tipo_operacao;
    if (params.cenario_id != null) q.cenario_id = String(params.cenario_id);
    if (params.consumidor_final === true) q.consumidor_final = 'true';
    if (params.consumidor_final === false) q.consumidor_final = 'false';
    return (await api.get<ComparativoFiscalSaida>(`${path}comparar/`, { params: q })).data;
  },
  coberturaPropostas: async (params?: {
    data_inicial?: string;
    data_final?: string;
    proposta_id?: number;
    cliente_id?: number;
    status_proposta?: string;
    ncm?: string;
    uf_origem?: string;
    uf_destino?: string;
    somente_divergentes?: boolean;
    somente_sem_cenario?: boolean;
    limite?: number;
    cenario_id?: number;
  }): Promise<CoberturaPropostasFiscalSaida> => {
    const q: Record<string, string> = {};
    if (params?.data_inicial) q.data_inicial = params.data_inicial;
    if (params?.data_final) q.data_final = params.data_final;
    if (params?.proposta_id != null) q.proposta_id = String(params.proposta_id);
    if (params?.cliente_id != null) q.cliente_id = String(params.cliente_id);
    if (params?.status_proposta) q.status_proposta = params.status_proposta;
    if (params?.ncm) q.ncm = params.ncm;
    if (params?.uf_origem) q.uf_origem = params.uf_origem;
    if (params?.uf_destino) q.uf_destino = params.uf_destino;
    if (params?.somente_divergentes) q.somente_divergentes = 'true';
    if (params?.somente_sem_cenario) q.somente_sem_cenario = 'true';
    if (params?.limite != null) q.limite = String(params.limite);
    if (params?.cenario_id != null) q.cenario_id = String(params.cenario_id);
    return (await api.get<CoberturaPropostasFiscalSaida>(`${path}cobertura-propostas/`, { params: q })).data;
  },
  checklistAtivacao: async (params?: {
    data_inicial?: string;
    data_final?: string;
    proposta_id?: number;
    cliente_id?: number;
    status_proposta?: string;
    ncm?: string;
    uf_origem?: string;
    uf_destino?: string;
    limite?: number;
    cenario_id?: number;
  }): Promise<ChecklistAtivacaoCenarioSaida> => {
    const q: Record<string, string> = {};
    if (params?.data_inicial) q.data_inicial = params.data_inicial;
    if (params?.data_final) q.data_final = params.data_final;
    if (params?.proposta_id != null) q.proposta_id = String(params.proposta_id);
    if (params?.cliente_id != null) q.cliente_id = String(params.cliente_id);
    if (params?.status_proposta) q.status_proposta = params.status_proposta;
    if (params?.ncm) q.ncm = params.ncm;
    if (params?.uf_origem) q.uf_origem = params.uf_origem;
    if (params?.uf_destino) q.uf_destino = params.uf_destino;
    if (params?.limite != null) q.limite = String(params.limite);
    if (params?.cenario_id != null) q.cenario_id = String(params.cenario_id);
    return (await api.get<ChecklistAtivacaoCenarioSaida>(`${path}checklist-ativacao/`, { params: q })).data;
  },
};
