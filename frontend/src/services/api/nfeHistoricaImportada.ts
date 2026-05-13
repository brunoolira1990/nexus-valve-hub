import type { NFeXmlImportFalhaApi } from '@/utils/nfeXmlImportDiagnostico';
import api from './config';

const base = 'nf-saidas-historicas-importadas/';

export type NFeHistoricaImportResumo = {
  total_arquivos: number;
  importadas: number;
  importadas_com_advertencia?: number;
  ja_existiam?: number;
  duplicadas: number;
  eventos_aplicados: number;
  eventos_duplicados: number;
  eventos_pendentes?: number;
  erros: number;
  falhas?: number;
};

export type { NFeXmlImportFalhaApi as NFeHistoricaImportFalha } from '@/utils/nfeXmlImportDiagnostico';

export type NFeHistoricaImportResultado = {
  importadas: {
    arquivo: string;
    id: number;
    chave_acesso: string;
    numero: string;
    serie: string;
    tipo_documento?: string;
  }[];
  duplicadas: { arquivo: string; chave_acesso: string; mensagem: string; tipo_documento?: string }[];
  eventos_aplicados: {
    arquivo: string;
    id_nota: number;
    chave_acesso: string;
    tipo_evento: string;
    protocolo_evento: string;
    tipo_documento: 'evento';
    origem?: string;
  }[];
  eventos_duplicados: {
    arquivo: string;
    chave_acesso: string;
    tipo_evento: string;
    mensagem: string;
  }[];
  eventos_pendentes?: {
    id: number;
    arquivo: string;
    chave_nfe: string;
    tipo_evento: string;
    descricao_evento?: string;
    sequencia_evento?: number;
    data_evento?: string | null;
    protocolo?: string;
    protocolo_evento?: string;
    mensagem: string;
    acao_sugerida?: string;
    situacao?: string;
    status?: string;
  }[];
  erros: NFeXmlImportFalhaApi[];
  resumo: NFeHistoricaImportResumo;
};

export type NFeEventoPendenteApi = {
  id: number;
  chave_nfe: string;
  tipo_evento: string;
  descricao_evento: string;
  sequencia_evento: number;
  data_evento: string | null;
  protocolo_evento: string;
  id_evento: string;
  justificativa: string;
  nome_arquivo: string;
  direcao: string;
  status: string;
  mensagem: string;
  nf: number | null;
  criado_em: string;
  atualizado_em: string;
};

export type ReprocessarEventosPendentesResponse = {
  aplicados: number;
  permanecem_pendentes: number;
  detalhes: { chave_nfe: string; resultado: string; id_nota?: number; motivo?: string; detalhe?: string }[];
};

export type NFeSaidaHistoricaList = {
  id: number;
  chave_acesso: string;
  numero: string;
  serie: string;
  dh_emissao: string;
  valor_total_nf: number;
  valor_produtos: number;
  v_frete: number;
  v_desc: number;
  nat_op: string;
  cstat: string;
  protocolo: string;
  empresa_emitente: number | null;
  empresa_emitente_nome: string;
  cliente: number | null;
  cliente_nome: string;
  icms_valor_lido_xml: number;
  tem_reforma_e_outros_json: boolean;
  sem_bloco_icmstot: boolean;
  nome_arquivo: string;
  importado_em: string;
  importada: boolean;
  origem_externa: boolean;
  historica: boolean;
  cancelada: boolean;
  status_documento: string;
  data_cancelamento: string | null;
  protocolo_evento: string;
  tipo_evento: string;
  status_visual: string;
  cstat_visual: string;
  motivo_visual: string;
  protocolo_cancelamento: string;
  empresa_id: number | null;
  empresa_nome: string;
  papel_empresa: string;
  papel_empresa_no_documento: string;
};

export type TotaisConsolidadoNFeHist = {
  faturamento_bruto: number;
  valor_produtos: number;
  frete: number;
  desconto: number;
  icms_base: number;
  icms_valor: number;
  ipi_valor: number;
  pis_valor: number;
  cofins_valor: number;
  quantidade_notas: number;
  quantidade_clientes_vinculados: number;
  notas_sem_bloco_icmstot: number;
  notas_com_reforma_e_outros_json: number;
};

export type IndicadoresGerenciaisNFeHist = {
  aliquota_efetiva_media_icms_sobre_faturamento_pct: number | null;
  aliquota_efetiva_media_pis_sobre_faturamento_pct: number | null;
  aliquota_efetiva_media_cofins_sobre_faturamento_pct: number | null;
  carga_tributaria_media_total_observada_pct: number | null;
};

export type ResumoFiscalNFeHistResponse = {
  origem_dados: string;
  tipo_fluxo?: string;
  escopo_faturamento?: string;
  periodo: Record<string, string | undefined>;
  filtros: {
    cliente_id: string | null;
    empresa_emitente_id: string | null;
    incluir_canceladas: boolean;
    apenas_faturamento_emitente_erp?: boolean;
  };
  totais: TotaisConsolidadoNFeHist;
  indicadores_gerenciais: IndicadoresGerenciaisNFeHist;
  irpj_csll: { observacao: string };
  reforma_tributaria: { observacao: string };
};

export type ApuracaoMensalNFeHistResponse = {
  origem_dados: string;
  tipo_fluxo?: string;
  periodo: Record<string, string | undefined>;
  meses: {
    ano_mes: string;
    totais: TotaisConsolidadoNFeHist;
    indicadores_gerenciais: IndicadoresGerenciaisNFeHist;
  }[];
};

export type ApuracaoTrimestralNFeHistResponse = {
  origem_dados: string;
  tipo_fluxo?: string;
  periodo: Record<string, string | undefined>;
  trimestres: {
    ano: number;
    trimestre: number;
    rotulo: string;
    totais: TotaisConsolidadoNFeHist;
    indicadores_gerenciais: IndicadoresGerenciaisNFeHist;
  }[];
};

export type NFeSaidaHistoricaDetalhe = NFeSaidaHistoricaList & {
  modelo: string;
  tp_amb: string;
  tp_nf: string;
  versao_layout: string;
  xmotivo: string;
  valor_produtos: number;
  v_frete: number;
  v_seg: number;
  v_desc: number;
  v_outro: number;
  emit_json: Record<string, unknown>;
  dest_json: Record<string, unknown>;
  totais_json: Record<string, unknown>;
  reforma_e_outros_json: Record<string, unknown>;
  prot_json: Record<string, unknown>;
  empresa_emitente: number | null;
  cliente: number | null;
  evento_cancelamento_json: Record<string, unknown>;
  evento_cancelamento_id: string;
  itens: { id: number; n_item: number; prod_json: Record<string, unknown>; imposto_json: Record<string, unknown> }[];
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

export const nfeHistoricaImportadaService = {
  list: async (query?: URLSearchParams) => {
    const q = query?.toString();
    const url = q ? `${base}?${q}` : base;
    return (await api.get<NFeSaidaHistoricaList[]>(url)).data;
  },
  getById: async (id: number) => (await api.get<NFeSaidaHistoricaDetalhe>(`${base}${id}/`)).data,
  resumoFiscal: async (query: URLSearchParams) =>
    (await api.get<ResumoFiscalNFeHistResponse>(`${base}resumo-fiscal/?${query.toString()}`)).data,
  apuracaoMensal: async (query: URLSearchParams) =>
    (await api.get<ApuracaoMensalNFeHistResponse>(`${base}apuracao-mensal/?${query.toString()}`)).data,
  apuracaoTrimestral: async (query: URLSearchParams) =>
    (await api.get<ApuracaoTrimestralNFeHistResponse>(`${base}apuracao-trimestral/?${query.toString()}`)).data,
  importarXmls: async (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append('arquivos', f));
    return (
      await api.post<NFeHistoricaImportResultado>(`${base}importar-xml/`, fd, {
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
  eventosPendentes: async (limit = 500) =>
    (await api.get<NFeEventoPendenteApi[]>(`${base}eventos-pendentes/`, { params: { limit } })).data,
  reprocessarEventosPendentes: async () =>
    (await api.post<ReprocessarEventosPendentesResponse>(`${base}reprocessar-eventos-pendentes/`)).data,
};
