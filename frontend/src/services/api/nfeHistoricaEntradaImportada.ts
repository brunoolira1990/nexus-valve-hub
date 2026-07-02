import api from './config';
import { buildListParams, type ListQueryParams, type PaginatedResponse, unwrapListResults } from '@/lib/apiList';
import { fetchAuthenticatedPdfBlob } from '@/lib/fetchPdfBlob';

import type { NFeXmlImportFalhaApi } from '@/utils/nfeXmlImportDiagnostico';

const base = 'nf-entradas-historicas-importadas/';

export type NFeEntradaHistoricaImportResultado = {
  importadas: { arquivo: string; id: number; chave_acesso: string; numero: string; serie: string }[];
  duplicadas: { arquivo: string; chave_acesso: string; mensagem: string }[];
  erros: NFeXmlImportFalhaApi[];
  resumo: { total_arquivos: number; importadas: number; duplicadas: number; erros: number };
};

export type NFeEntradaHistoricaList = {
  id: number;
  chave_acesso: string;
  numero: string;
  serie: string;
  dh_emissao: string;
  conferencia_data_entrada?: string | null;
  valor_total_nf: number;
  valor_produtos: number;
  v_frete: number;
  v_desc: number;
  nat_op: string;
  cstat: string;
  protocolo: string;
  empresa_destinataria: number | null;
  empresa_id: number | null;
  empresa_nome: string;
  fornecedor_emitente: number | null;
  fornecedor_nome: string;
  papel_empresa: string;
  papel_empresa_no_documento: string;
  nome_arquivo: string;
  importado_em: string;
  importada: boolean;
  origem_externa: boolean;
  historica: boolean;
  conferencia_status?: string | null;
  conferencia_preparado_em?: string | null;
  conferencia_estoque_aplicado_em?: string | null;
  tp_amb?: string;
  tem_xml_conteudo?: boolean;
  classificacao_dfe?: {
    categoria?: string;
    homologacao?: boolean;
    pode_entrar_apuracao?: boolean;
    pode_alimentar_precificacao?: boolean;
    pode_gerar_efeito_operacional?: boolean;
    badges?: string[];
  };
};

export type TotaisConsolidadoNFeEntradaHist = {
  valor_total_compras: number;
  valor_produtos: number;
  frete: number;
  desconto: number;
  icms_base: number;
  icms_valor: number;
  ipi_valor: number;
  pis_valor: number;
  cofins_valor: number;
  quantidade_notas: number;
  quantidade_fornecedores_vinculados: number;
  notas_sem_bloco_icmstot: number;
  notas_com_reforma_e_outros_json: number;
};

export type IndicadoresGerenciaisEntradaNFeHist = {
  aliquota_efetiva_media_icms_sobre_compras_pct: number | null;
  aliquota_efetiva_media_pis_sobre_compras_pct: number | null;
  aliquota_efetiva_media_cofins_sobre_compras_pct: number | null;
  carga_tributaria_media_total_observada_pct: number | null;
};

export type ResumoFiscalNFeEntradaHistResponse = {
  origem_dados: string;
  tipo_fluxo?: string;
  escopo?: string;
  periodo: Record<string, string | undefined>;
  filtros: Record<string, string | boolean | null | undefined>;
  totais: TotaisConsolidadoNFeEntradaHist;
  indicadores_gerenciais: IndicadoresGerenciaisEntradaNFeHist;
};

export type ApuracaoMensalNFeEntradaHistResponse = {
  origem_dados: string;
  tipo_fluxo?: string;
  periodo: Record<string, string | undefined>;
  meses: {
    ano_mes: string;
    totais: TotaisConsolidadoNFeEntradaHist;
    indicadores_gerenciais: IndicadoresGerenciaisEntradaNFeHist;
  }[];
};

export type NFeEntradaHistoricaDetalhe = NFeEntradaHistoricaList & {
  modelo: string;
  tp_amb: string;
  tp_nf: string;
  versao_layout: string;
  xmotivo: string;
  v_seg: number;
  v_outro: number;
  emit_json: Record<string, unknown>;
  dest_json: Record<string, unknown>;
  totais_json: Record<string, unknown>;
  reforma_e_outros_json: Record<string, unknown>;
  prot_json: Record<string, unknown>;
  itens: { id: number; n_item: number; prod_json: Record<string, unknown>; imposto_json: Record<string, unknown> }[];
};

export const nfeHistoricaEntradaImportadaService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<NFeEntradaHistoricaList>>(base, {
      params: buildListParams(params),
    });
    return response.data;
  },
  list: async (query?: URLSearchParams) => {
    const q = query?.toString();
    const url = q ? `${base}?${q}` : base;
    const response = await api.get<NFeEntradaHistoricaList[] | PaginatedResponse<NFeEntradaHistoricaList>>(url, {
      params: q ? undefined : buildListParams({ limit: 100 }),
    });
    return unwrapListResults(response.data);
  },
  resumoFiscalEntrada: async (query: URLSearchParams) =>
    (await api.get<ResumoFiscalNFeEntradaHistResponse>(`${base}resumo-fiscal-entrada/?${query.toString()}`)).data,
  apuracaoMensalEntrada: async (query: URLSearchParams) =>
    (await api.get<ApuracaoMensalNFeEntradaHistResponse>(`${base}apuracao-mensal-entrada/?${query.toString()}`)).data,
  getById: async (id: number) => (await api.get<NFeEntradaHistoricaDetalhe>(`${base}${id}/`)).data,
  downloadXml: async (id: number) => {
    const response = await api.get<Blob>(`${base}${id}/download-xml/`, { responseType: 'blob' });
    return response.data;
  },
  danfeBlob: async (id: number) =>
    fetchAuthenticatedPdfBlob(
      `${base}${id}/danfe/`,
      'Não foi possível gerar o DANFE desta NF-e de entrada.',
      `DANFE_NFe_Entrada_${id}.pdf`,
    ),
  importarXmls: async (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append('arquivos', f));
    return (
      await api.post<NFeEntradaHistoricaImportResultado>(`${base}importar-xml/`, fd, {
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
  previewContasPagar: async (id: number) =>
    (await api.get<NFeGerarContasPagarPreview>(`${base}${id}/financeiro/preview-contas-pagar/`)).data,
  gerarContasPagar: async (id: number, payload: NFeGerarContasPagarPayload) =>
    (
      await api.post<NFeGerarContasPagarResponse>(`${base}${id}/financeiro/gerar-contas-pagar/`, payload)
    ).data,
  contasPagarVinculadas: async (id: number) =>
    (await api.get<NFeContasPagarVinculadasResponse>(`${base}${id}/financeiro/contas-pagar/`)).data,
};

export type NFeGerarContasPagarParcela = {
  numero_parcela: number;
  vencimento: string;
  valor: string;
  observacoes?: string;
};

export type NFeGerarContasPagarPreview = {
  financeiro_gerado: boolean;
  pode_gerar_contas_pagar: boolean;
  motivo_bloqueio_financeiro: string;
  possui_pendencias_operacionais?: boolean;
  pode_gerar_com_pendencias?: boolean;
  aviso_pendencias_operacionais?: string;
  aviso_pendencias_wizard?: string;
  motivos_pendencias_operacionais?: string[];
  contas_pagar_vinculadas: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
  nfe_entrada_cancelada_com_financeiro?: boolean;
  fornecedor: { id: number; nome: string; cnpj: string };
  origem: {
    tipo: string;
    id: number;
    numero: string;
    serie: string;
    chave_acesso: string;
    data_emissao: string | null;
    data_importacao: string | null;
    descricao: string;
    valor_total: string;
    pedido_compra_id: number | null;
    pedido_compra_numero: string;
  };
  parcelas: NFeGerarContasPagarParcela[];
  quantidade_parcelas_sugeridas: number;
  origem_parcelas?: 'XML' | 'PEDIDO' | 'EMISSAO';
  aviso_origem_parcelas?: string;
  parcelas_do_xml?: boolean;
  categoria_sugerida_id: number | null;
};

export type NFeGerarContasPagarPayload = {
  parcelas: NFeGerarContasPagarParcela[];
  categoria?: number | null;
  centro_custo?: number | null;
  forma_pagamento_prevista_codigo?: string;
  conta_financeira_prevista?: number | null;
  observacoes?: string;
  confirmar_pendencias_operacionais?: boolean;
};

export type NFeGerarContasPagarResponse = {
  mensagem: string;
  titulo: import('@/services/api/financeiro').TituloFinanceiro;
  financeiro_gerado: boolean;
  pode_gerar_contas_pagar: boolean;
  motivo_bloqueio_financeiro: string;
  contas_pagar_vinculadas: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
};

export type NFeContasPagarVinculadasResponse = {
  financeiro_gerado: boolean;
  pode_gerar_contas_pagar: boolean;
  motivo_bloqueio_financeiro: string;
  contas_pagar_vinculadas: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
  contas_pagar: import('@/services/api/financeiro').TituloFinanceiro[];
};

