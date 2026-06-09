import api from './config';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';
import type { FamiliaProduto, Polegada, Produto, RoscaConexao, ScheduleEspessura } from '@/types';

const path = 'produtos/';
const famPath = 'familias-produto/';
const roscaPath = 'roscas-conexao/';
const schedPath = 'schedules-espessura/';
const polPath = 'polegadas/';
const famPolPath = 'familias-produto-polegadas-permitidas/';
const famRoscaPath = 'familias-produto-roscas-permitidas/';
const famSchedPath = 'familias-produto-schedules-permitidos/';
const ncmPath = 'ncms/';

type ListResponse<T> = T[] | { results?: T[] };

function unwrapList<T>(payload: ListResponse<T>): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.results)) return payload.results;
  throw new Error('Resposta inesperada da API.');
}

function stripReadOnly(p: Partial<Produto>): Record<string, unknown> {
  const x: Record<string, unknown> = { ...p };
  delete x.id;
  if (p.modo_codigo !== 'MANUAL') delete x.codigo_completo;
  return x;
}

export type PreviewCodigoPayload = {
  familia_id: number;
  rosca_conexao_id?: number | null;
  schedule_ref_id?: number | null;
  polegada_principal_ref_id?: number | null;
  polegada_secundaria_ref_id?: number | null;
  od_mm?: number | null;
  espessura_mm?: number | null;
  comprimento_mm?: number | null;
  dim_espessura_mm?: number | null;
  dim_largura_mm?: number | null;
  dim_comprimento_mm?: number | null;
  dim_altura_mm?: number | null;
  dim_furo_mm?: number | null;
  dim_aba_mm?: number | null;
  dim_aba_polegada_ref_id?: number | null;
  dim_espessura_polegada_ref_id?: number | null;
  dimensao_codigo?: string;
  dimensao_descricao?: string;
  dimensoes_json?: Record<string, number | string | null>;
};

export type PreviewCodigoResponse = {
  codigo: string;
  descricao_sugerida: string;
  mensagem: string;
  ncm_efetivo?: string;
  unidade_efetiva?: string;
  origem_ncm?: 'familia' | 'produto';
  origem_unidade?: 'familia' | 'produto';
  mensagens?: string[];
};

export type ConverterMedidaPayload = {
  produto_id: number;
  quantidade: number | string;
  unidade_origem: string;
  unidade_destino: string;
};

export type ConverterMedidaResponse = {
  produto_id: number;
  quantidade_origem: string;
  unidade_origem: string;
  quantidade_destino: string;
  unidade_destino: string;
  peso_kg?: string | null;
  metros?: string | null;
  barras?: string | null;
  unidade_estoque?: string | null;
  mensagem?: string;
};

export type ProdutosListParams = ListQueryParams & {
  sem_ncm?: string;
  material?: string;
};

export const produtosService = {
  listPaginated: async (params?: ProdutosListParams) => {
    const response = await api.get<PaginatedResponse<Produto>>(path, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ProdutosListParams) => {
    const response = await api.get<ListResponse<Produto>>(path, {
      params: buildListParams(
        params?.page ? params : { ...params, limit: params?.limit ?? (params?.search ? 50 : 100) },
      ),
    });
    return unwrapList(response.data);
  },
  getById: async (id: number) => (await api.get<Produto>(`${path}${id}/`)).data,
  create: async (data: Omit<Produto, 'id'>) => (await api.post<Produto>(path, stripReadOnly(data))).data,
  update: async (id: number, data: Partial<Produto>) =>
    (await api.patch<Produto>(`${path}${id}/`, stripReadOnly(data))).data,
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
  previewCodigo: async (body: PreviewCodigoPayload) =>
    (await api.post<PreviewCodigoResponse>(`${path}preview-codigo/`, body)).data,
  converterMedida: async (body: ConverterMedidaPayload) =>
    (await api.post<ConverterMedidaResponse>(`${path}converter-medida/`, body)).data,
  search: async (term: string, limit = 50) => {
    const response = await api.get<ListResponse<Produto>>(path, { params: { search: term, limit } });
    return unwrapList(response.data);
  },
};

export const familiasProdutoService = {
  getAll: async (params?: { search?: string; apenas_ativas?: string }) => {
    const response = await api.get<ListResponse<FamiliaProduto>>(famPath, { params });
    return unwrapList(response.data);
  },
  create: async (data: Omit<FamiliaProduto, 'id'>) => (await api.post<FamiliaProduto>(famPath, data)).data,
  update: async (id: number, data: Partial<FamiliaProduto>) =>
    (await api.patch<FamiliaProduto>(`${famPath}${id}/`, data)).data,
  search: async (term: string, limit = 20) => {
    const response = await api.get<ListResponse<FamiliaProduto>>(famPath, { params: { search: term, limit, apenas_ativas: '1' } });
    return unwrapList(response.data);
  },
};

export const roscasConexaoService = {
  getAll: async () => {
    const response = await api.get<ListResponse<RoscaConexao>>(roscaPath, { params: { apenas_ativas: '1' } });
    return unwrapList(response.data);
  },
  search: async (term: string, limit = 20) => {
    const response = await api.get<ListResponse<RoscaConexao>>(roscaPath, {
      params: { search: term, limit, apenas_ativas: '1' },
    });
    return unwrapList(response.data);
  },
};

export const schedulesEspessuraService = {
  getAll: async () => {
    const response = await api.get<ListResponse<ScheduleEspessura>>(schedPath, { params: { apenas_ativas: '1' } });
    return unwrapList(response.data);
  },
  search: async (term: string, limit = 20) => {
    const response = await api.get<ListResponse<ScheduleEspessura>>(schedPath, {
      params: { search: term, limit, apenas_ativas: '1' },
    });
    return unwrapList(response.data);
  },
};

export const polegadasService = {
  getAll: async () => {
    const response = await api.get<ListResponse<Polegada>>(polPath);
    return unwrapList(response.data);
  },
  search: async (term: string, limit = 20, tipo_medida?: 'NPS' | 'OD') => {
    const response = await api.get<ListResponse<Polegada>>(polPath, {
      params: { search: term, limit, tipo_medida: tipo_medida || undefined },
    });
    return unwrapList(response.data);
  },
  create: async (data: Partial<Polegada>) => (await api.post<Polegada>(polPath, data)).data,
  getById: async (id: number) => (await api.get<Polegada>(`${polPath}${id}/`)).data,
};

export const polegadasApiService = polegadasService;

export type NcmItem = { id: number; codigo: string; descricao: string };

export const ncmApiService = {
  search: async (term: string, limit = 20) => {
    const response = await api.get<ListResponse<NcmItem>>(ncmPath, {
      params: { search: term, limit },
    });
    return unwrapList(response.data);
  },
  getById: async (id: number) => (await api.get<NcmItem>(`${ncmPath}${id}/`)).data,
};

export const familiaVariacoesService = {
  addPolegadaPermitida: async (payload: { familia: number; polegada: number; tipo: 'principal' | 'secundaria' | 'ambas'; ordem?: number; ativo?: boolean }) =>
    (await api.post(famPolPath, payload)).data,
  removePolegadaPermitida: async (permitidaId: number) => {
    await api.delete(`${famPolPath}${permitidaId}/`);
  },
  addRoscaPermitida: async (payload: { familia: number; rosca_conexao: number; padrao_da_familia?: boolean; ativo?: boolean }) =>
    (await api.post(famRoscaPath, payload)).data,
  addSchedulePermitido: async (payload: { familia: number; schedule: number; padrao_da_familia?: boolean; ativo?: boolean }) =>
    (await api.post(famSchedPath, payload)).data,
  removeSchedulePermitido: async (permitidoId: number) => {
    await api.delete(`${famSchedPath}${permitidoId}/`);
  },
};
