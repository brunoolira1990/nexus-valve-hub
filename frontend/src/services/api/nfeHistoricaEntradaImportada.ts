import api from './config';

const base = 'nf-entradas-historicas-importadas/';

export type NFeEntradaHistoricaImportResultado = {
  importadas: { arquivo: string; id: number; chave_acesso: string; numero: string; serie: string }[];
  duplicadas: { arquivo: string; chave_acesso: string; mensagem: string }[];
  erros: { arquivo: string; mensagem: string }[];
  resumo: { total_arquivos: number; importadas: number; duplicadas: number; erros: number };
};

export type NFeEntradaHistoricaList = {
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
  list: async (query?: URLSearchParams) => {
    const q = query?.toString();
    const url = q ? `${base}?${q}` : base;
    return (await api.get<NFeEntradaHistoricaList[]>(url)).data;
  },
  resumoFiscalEntrada: async (query: URLSearchParams) =>
    (await api.get<ResumoFiscalNFeEntradaHistResponse>(`${base}resumo-fiscal-entrada/?${query.toString()}`)).data,
  apuracaoMensalEntrada: async (query: URLSearchParams) =>
    (await api.get<ApuracaoMensalNFeEntradaHistResponse>(`${base}apuracao-mensal-entrada/?${query.toString()}`)).data,
  getById: async (id: number) => (await api.get<NFeEntradaHistoricaDetalhe>(`${base}${id}/`)).data,
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
};

