import api from './config';
import { buildListParams, type ListQueryParams, type PaginatedResponse } from '@/lib/apiList';

const base = 'central-dfe/';

export type CentralDfeResumo = {
  total: number;
  pendentes_entrada: number;
  nfe_fornecedores: number;
  cte_transportadoras: number;
  divergentes: number;
  ignorados: number;
  ja_tratados: number;
};

export type CentralDfeDocumento = {
  id: number;
  tipo_documento: 'NFE_ENTRADA' | 'CTE';
  chave_resumida: string;
  chave_acesso: string;
  numero: string;
  serie: string;
  data_emissao: string | null;
  data_importacao: string | null;
  data_entrada?: string | null;
  emitente_nome: string;
  emitente_cnpj: string;
  uf: string;
  valor_total: string;
  status_entrada: string;
  status_entrada_label: string;
  tipo_label: string;
  detalhe_rota: string;
  empresa_id: number | null;
  xml_status?: 'PENDENTE' | 'DISPONIVEL' | 'ARMAZENADO' | 'ERRO';
  xml_status_label?: string;
  xml_armazenado?: boolean;
  manifestacao_aplicavel?: boolean;
};

export type ArmazenarXmlCentralResponse = {
  tipo_documento: string;
  chave_acesso?: string;
  xml_armazenado: boolean;
  xml_status: string;
  nf_entrada_historica_id?: number;
  cte_historico_id?: number;
  manifestacao_id?: number;
  duplicado?: boolean;
  mensagem?: string;
  detalhe_rota?: string;
  download_xml_url?: string;
  documento?: CentralDfeDocumento;
};

export type CentralDfeListResponse = PaginatedResponse<CentralDfeDocumento> & {
  resumo?: CentralDfeResumo;
  empresa?: { id: number; razao_social: string; cnpj: string };
};

export type CentralDfeCapturaResumo = {
  nfe_encontradas: number;
  nfe_encontradas_resumo?: number;
  nfe_novas: number;
  nfe_duplicadas: number;
  cte_encontrados: number;
  cte_encontrados_resumo?: number;
  cte_novos: number;
  cte_duplicados: number;
  pendentes_total: number;
};

export type CentralDfeSefazTipoResumo = {
  consultada: boolean;
  cstat: string;
  lotes_consultados: number;
  lotes_processados?: number;
  limite_lotes?: number;
  encontrados_xml: number;
  encontrados_resumo: number;
  novos: number;
  duplicados: number;
  ultimo_nsu_inicial?: number;
  ultimo_nsu_final?: number;
  max_nsu?: number;
  ainda_tem_nsu_pendente?: boolean;
  parou_por_limite_lotes?: boolean;
};

export type CentralDfeNsuTipo = {
  ultimo_nsu_inicial?: number;
  ultimo_nsu_final?: number;
  ultimo_nsu?: number;
  max_nsu?: number;
  ainda_tem_nsu_pendente?: boolean;
  parou_por_limite_lotes?: boolean;
  lotes_processados?: number;
};

export type CentralDfeCapturaResponse = {
  sucesso: boolean;
  sefaz_consultada?: boolean;
  ainda_tem_nsu_pendente?: boolean;
  parou_por_limite_lotes?: boolean;
  lotes_processados?: number;
  limite_lotes?: number;
  empresa?: { id: number; razao_social: string; cnpj: string };
  tipos_processados?: string[];
  resumo?: CentralDfeCapturaResumo;
  mensagens?: string[];
  avisos?: string[];
  erros?: string[];
  nsu_por_tipo?: Record<string, CentralDfeNsuTipo>;
  sefaz_por_tipo?: Record<string, CentralDfeSefazTipoResumo>;
};

export const centralDfeService = {
  async listPaginated(params?: ListQueryParams): Promise<CentralDfeListResponse> {
    const { data } = await api.get<CentralDfeListResponse>(base, { params: buildListParams(params) });
    return data;
  },

  async capturarSefaz(payload: {
    empresa_id: number;
    tipos?: ('NFE' | 'CTE')[];
    modo?: 'incremental';
    limite_lotes?: number;
  }): Promise<CentralDfeCapturaResponse> {
    const { data } = await api.post<CentralDfeCapturaResponse>('dfe-recebidos/capturar/', payload);
    return data;
  },

  /** Armazena XML NF-e na Base NF-e Entrada Importada — ação manual explícita. */
  async armazenarXmlNfe(
    documentoId: number,
    payload: { empresa_id: number; confirmacao_explicita: boolean; chave_acesso?: string },
  ): Promise<ArmazenarXmlCentralResponse> {
    const { data } = await api.post<ArmazenarXmlCentralResponse>(
      `${base}${documentoId}/armazenar-xml-nfe/`,
      payload,
    );
    return data;
  },

  /** Confirma/armazena XML CT-e na Base CT-e Importada — ação manual explícita. */
  async armazenarXmlCte(
    documentoId: number,
    payload: { empresa_id: number; confirmacao_explicita: boolean },
  ): Promise<ArmazenarXmlCentralResponse> {
    const { data } = await api.post<ArmazenarXmlCentralResponse>(
      `${base}${documentoId}/armazenar-xml-cte/`,
      payload,
    );
    return data;
  },
};
