import api from './config';
import { buildListParams, type ListQueryParams, type PaginatedResponse, unwrapListResults } from '@/lib/apiList';
import type {
  CertificadoFornecedorEntrada,
  DadosTecnicosFornecedorResultado,
} from '@/types';

const base = 'certificados-fornecedor/';

export type PreencherPorNFeEntradaPayload = {
  nf_entrada_historica_id?: number;
  nf_entrada_operacional_id?: number;
};

export type PreencherPorNFeEntradaResponse = Partial<CertificadoFornecedorEntrada> & {
  mensagens?: string[];
};

export type BuscarDadosTecnicosFornecedorParams = {
  corrida?: string;
  lote?: string;
  produto?: number;
  codigo_produto?: string;
  descricao?: string;
  norma?: string;
  tipo_dados_tecnicos?: 'PADRAO_ITEM' | 'VALVULA_COMPONENTES';
  fornecedor?: number;
  nf_entrada?: string;
  certificado_fornecedor?: string;
  status?: 'rascunho' | 'registrado' | 'cancelado';
  include_rascunho?: boolean;
  /** Só o backend inclui `diagnostico` quando o utilizador é superuser e `debug=1`. */
  debug?: boolean;
};

export type BuscarDadosTecnicosFornecedorResponse = {
  resultados: DadosTecnicosFornecedorResultado[];
  dicas_busca: string[];
  diagnostico?: Record<string, unknown>;
};

const ORDEM_DICAS_BUSCA_FORNECEDOR = ['PRODUTO_VINCULADO_DIFERENTE', 'LOTE_DIVERGENTE', 'CERTIFICADO_RASCUNHO'] as const;

const MENSAGEM_DICA_BUSCA_FORNECEDOR: Record<(typeof ORDEM_DICAS_BUSCA_FORNECEDOR)[number], string> = {
  PRODUTO_VINCULADO_DIFERENTE:
    'Existe certificado fornecedor com esta corrida, mas vinculado a outro produto. Revise o vínculo do item no certificado fornecedor.',
  LOTE_DIVERGENTE:
    'Existe certificado fornecedor com esta corrida, mas o lote declarado é diferente.',
  CERTIFICADO_RASCUNHO:
    'Existe certificado fornecedor com esta corrida, mas ele está em rascunho. Registre o certificado fornecedor antes de usar os dados técnicos.',
};

/** Corrida/lote exibidos no item: campos do resultado ou, se faltar, valores nos componentes (válvula / CF parcial). */
export function corridaLoteEfetivosResultadoFornecedor(src: DadosTecnicosFornecedorResultado): { corrida: string; lote: string } {
  let corrida = (src.corrida || '').trim();
  let lote = (src.lote || '').trim();
  if (corrida && lote) return { corrida, lote };
  for (const cp of src.componentes || []) {
    if (!corrida) corrida = (cp.corrida || '').trim();
    if (!lote) lote = (cp.lote || '').trim();
    if (corrida && lote) break;
  }
  return { corrida, lote };
}

/** Mensagem prioritária quando a API devolve `dicas_busca` sem resultados (códigos estáveis). */
export function mensagemPrincipalBuscaDadosTecnicosFornecedor(dicas: string[] | undefined): string | null {
  if (!dicas?.length) return null;
  for (const code of ORDEM_DICAS_BUSCA_FORNECEDOR) {
    if (dicas.includes(code)) return MENSAGEM_DICA_BUSCA_FORNECEDOR[code];
  }
  return null;
}

function normalizaBuscaDadosTecnicosPayload(data: unknown): BuscarDadosTecnicosFornecedorResponse {
  if (Array.isArray(data)) {
    return { resultados: data as DadosTecnicosFornecedorResultado[], dicas_busca: [] };
  }
  const o = data as Record<string, unknown>;
  return {
    resultados: (Array.isArray(o.resultados) ? o.resultados : []) as DadosTecnicosFornecedorResultado[],
    dicas_busca: Array.isArray(o.dicas_busca) ? (o.dicas_busca as string[]) : [],
    diagnostico: o.diagnostico as Record<string, unknown> | undefined,
  };
}

export const certificadosFornecedorService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<CertificadoFornecedorEntrada>>(base, {
      params: buildListParams(params),
    });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<CertificadoFornecedorEntrada[] | PaginatedResponse<CertificadoFornecedorEntrada>>(
      base,
      { params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }) },
    );
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<CertificadoFornecedorEntrada>(`${base}${id}/`)).data,
  create: async (payload: Omit<CertificadoFornecedorEntrada, 'id' | 'criado_em' | 'atualizado_em'>) =>
    (await api.post<CertificadoFornecedorEntrada>(base, payload)).data,
  update: async (id: number, payload: Partial<CertificadoFornecedorEntrada>) =>
    (await api.patch<CertificadoFornecedorEntrada>(`${base}${id}/`, payload)).data,
  preencherPorNfeEntrada: async (payload: PreencherPorNFeEntradaPayload) =>
    (await api.post<PreencherPorNFeEntradaResponse>(`${base}preencher-por-nfe-entrada/`, payload)).data,
  buscarDadosTecnicos: async (params: BuscarDadosTecnicosFornecedorParams) => {
    const { debug, ...rest } = params;
    const query = {
      ...rest,
      ...(debug ? { debug: '1' as const } : {}),
    };
    const raw = (await api.get<unknown>(`${base}buscar-dados-tecnicos/`, { params: query })).data;
    return normalizaBuscaDadosTecnicosPayload(raw);
  },
};
