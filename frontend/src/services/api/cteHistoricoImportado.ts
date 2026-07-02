import type { ClassificacaoDfe } from '@/components/fiscal/DfeClassificacaoBadges';
import type { FornecedorEntradaStatus } from '@/types';
import api from './config';
import { buildListParams, type ListQueryParams, type PaginatedResponse, unwrapListResults } from '@/lib/apiList';
import { fetchAuthenticatedPdfBlob } from '@/lib/fetchPdfBlob';

const base = 'cte-historicos-importados/';

export type CTeHistImportResumo = {
  total_arquivos: number;
  importados: number;
  duplicados: number;
  erros: number;
};

export type CTeHistImportResultado = {
  importados: { arquivo: string; id: number; chave_acesso: string; numero: string; serie: string }[];
  duplicados: { arquivo: string; chave_acesso: string; mensagem: string }[];
  erros: { arquivo: string; mensagem: string }[];
  resumo: CTeHistImportResumo;
};

export type CTeHistoricoList = {
  id: number;
  chave_acesso: string;
  numero: string;
  serie: string;
  dh_emissao: string;
  valor_total_servico: number;
  valor_receber: number;
  icms_base: number;
  icms_aliquota: number;
  icms_valor: number;
  modal: string;
  tipo_servico: string;
  municipio_inicio: string;
  uf_inicio: string;
  municipio_fim: string;
  uf_fim: string;
  cstat: string;
  protocolo: string;
  transportadora: number | null;
  transportadora_nome: string;
  empresa_tomadora: number | null;
  empresa_tomadora_nome: string;
  empresa_destinataria: number | null;
  empresa_recebedora: number | null;
  fornecedor_remetente: number | null;
  fornecedor_remetente_nome: string;
  empresa_id: number | null;
  empresa_nome: string;
  papel_empresa: string;
  papel_empresa_no_documento: string;
  cancelado: boolean;
  status_documento: string;
  data_cancelamento: string | null;
  protocolo_cancelamento: string;
  motivo_cancelamento: string;
  status_visual: string;
  cstat_visual: string;
  motivo_visual: string;
  nome_arquivo: string;
  importado_em: string;
  importado: boolean;
  origem_externa: boolean;
  historico: boolean;
  tp_amb?: string;
  classificacao_dfe?: ClassificacaoDfe;
  status_conferencia?: string;
  apto_operacional?: boolean;
  conferido_em?: string | null;
  ignorado_operacionalmente?: boolean;
  tem_xml_conteudo?: boolean;
};

export type CTeConferenciaResposta = {
  id: number;
  status_conferencia: string;
  apto_operacional: boolean;
  conferido_em: string | null;
  conferido_por: string;
  observacao_conferencia: string;
  divergencia_motivo: string;
  classificacao_dfe: ClassificacaoDfe;
};

export type CTeDocumentoVinculadoResumo = {
  chave_acesso: string;
  localizada: boolean;
  origem: string;
  origem_label: string;
  documento_id: number | null;
  status_encontrada: string;
};

export type CTeHistoricoDetalhe = CTeHistoricoList & {
  fornecedor?: FornecedorEntradaStatus | null;
  modelo: string;
  tp_amb: string;
  nat_op: string;
  cfop: string;
  versao_layout: string;
  xmotivo: string;
  componentes_frete_json: unknown[];
  emit_json: Record<string, unknown>;
  rem_json: Record<string, unknown>;
  dest_json: Record<string, unknown>;
  exped_json: Record<string, unknown>;
  receb_json: Record<string, unknown>;
  tomador_json: Record<string, unknown>;
  totais_json: Record<string, unknown>;
  imposto_json: Record<string, unknown>;
  prot_json: Record<string, unknown>;
  reforma_e_outros_json: Record<string, unknown>;
  chaves_nfe_vinculadas: string[];
  observacao_conferencia?: string;
  divergencia_motivo?: string;
  checklist_conferencia_json?: Record<string, boolean>;
  documentos_vinculados_resumo?: CTeDocumentoVinculadoResumo[];
  eventos: {
    id: number;
    chave_acesso: string;
    tipo_evento: string;
    protocolo_evento: string;
    id_evento: string;
    sequencial_evento: number;
    data_evento: string | null;
    evento_json: Record<string, unknown>;
    nome_arquivo: string;
    importado_em: string;
  }[];
};

export type CTeResumoGerencial = {
  totais: {
    valor_total_fretes: number;
    quantidade_ctes: number;
    frete_medio: number;
  };
  indicadores_gerenciais: {
    peso_frete_sobre_faturamento_pct: number | null;
    peso_frete_sobre_compras_pct: number | null;
    frete_medio_observado: number;
  };
  base_comparativa: {
    faturamento: number;
    compras: number;
  };
};

export type CTeTransportadoraGerencial = {
  transportadora_nome: string;
  quantidade_ctes: number;
  valor_total_fretes: number;
  frete_medio: number;
  participacao_pct: number | null;
};

export type CTeSerieGerencial = {
  ano_mes?: string;
  ano?: number;
  trimestre?: number;
  rotulo?: string;
  totais: {
    valor_total_fretes: number;
    quantidade_ctes: number;
    frete_medio: number;
  };
  peso_frete_sobre_faturamento_pct: number | null;
  faturamento_periodo: number;
};

export const cteHistoricoImportadoService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<CTeHistoricoList>>(base, { params: buildListParams(params) });
    return response.data;
  },
  list: async (params?: ListQueryParams) => {
    const response = await api.get<CTeHistoricoList[] | PaginatedResponse<CTeHistoricoList>>(base, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<CTeHistoricoDetalhe>(`${base}${id}/`)).data,
  downloadXml: async (id: number) => {
    const response = await api.get<Blob>(`${base}${id}/download-xml/`, { responseType: 'blob' });
    return response.data;
  },
  dacteBlob: async (id: number) =>
    fetchAuthenticatedPdfBlob(
      `${base}${id}/dacte/`,
      'Não foi possível gerar o DACTE deste CT-e.',
      `DACTE_CTe_${id}.pdf`,
    ),
  importarXmls: async (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append('arquivos', f));
    return (
      await api.post<CTeHistImportResultado>(`${base}importar-xml/`, fd, {
        transformRequest: [
          (data, headers) => {
            if (headers && typeof headers === 'object' && 'Content-Type' in headers) {
              delete (headers as Record<string, unknown>)['Content-Type'];
            }
            return data as FormData;
          },
        ],
      })
    ).data;
  },
  resumoGerencial: async (query?: URLSearchParams) => {
    const q = query?.toString();
    const url = q ? `${base}resumo-gerencial-fretes/?${q}` : `${base}resumo-gerencial-fretes/`;
    return (await api.get<CTeResumoGerencial>(url)).data;
  },
  transportadorasGerencial: async (query?: URLSearchParams) => {
    const q = query?.toString();
    const url = q ? `${base}transportadoras-gerencial/?${q}` : `${base}transportadoras-gerencial/`;
    return (await api.get<{ transportadoras: CTeTransportadoraGerencial[] }>(url)).data;
  },
  serieMensalGerencial: async (query?: URLSearchParams) => {
    const q = query?.toString();
    const url = q ? `${base}serie-mensal-gerencial/?${q}` : `${base}serie-mensal-gerencial/`;
    return (await api.get<{ meses: CTeSerieGerencial[] }>(url)).data;
  },
  serieTrimestralGerencial: async (query?: URLSearchParams) => {
    const q = query?.toString();
    const url = q ? `${base}serie-trimestral-gerencial/?${q}` : `${base}serie-trimestral-gerencial/`;
    return (await api.get<{ trimestres: CTeSerieGerencial[] }>(url)).data;
  },
  conferir: async (
    id: number,
    payload: {
      observacao?: string;
      confirmar_tomador: boolean;
      confirmar_transportadora: boolean;
      confirmar_valores: boolean;
      confirmar_documentos_referenciados: boolean;
    },
  ) => (await api.post<CTeConferenciaResposta>(`${base}${id}/conferir/`, payload)).data,
  marcarDivergente: async (id: number, payload: { motivo: string; observacao?: string }) =>
    (await api.post<CTeConferenciaResposta>(`${base}${id}/marcar-divergente/`, payload)).data,
  ignorarOperacional: async (id: number, payload: { motivo: string; observacao?: string }) =>
    (await api.post<CTeConferenciaResposta>(`${base}${id}/ignorar-operacional/`, payload)).data,
  vincularFornecedor: async (id: number, fornecedorId: number) =>
    (await api.post<{ cte: CTeHistoricoDetalhe; fornecedor: FornecedorEntradaStatus }>(
      `${base}${id}/fornecedor/vincular/`,
      { fornecedor_id: fornecedorId },
    )).data,
  cadastrarVincularFornecedor: async (id: number, payload: Record<string, unknown>) =>
    (await api.post<{ cte: CTeHistoricoDetalhe; fornecedor: FornecedorEntradaStatus }>(
      `${base}${id}/fornecedor/cadastrar-vincular/`,
      payload,
    )).data,
};

