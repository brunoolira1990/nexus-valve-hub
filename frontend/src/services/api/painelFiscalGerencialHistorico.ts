import api from './config';

const base = 'painel-fiscal-gerencial-historico/';

type TotaisFaturamento = {
  faturamento_bruto: number;
  quantidade_notas: number;
  icms_valor: number;
  ipi_valor: number;
  pis_valor: number;
  cofins_valor: number;
  quantidade_clientes_vinculados: number;
};

type TotaisCompras = {
  valor_total_compras: number;
  quantidade_notas: number;
  icms_valor: number;
  ipi_valor: number;
  pis_valor: number;
  cofins_valor: number;
  quantidade_fornecedores_vinculados: number;
};

type TotaisFretes = {
  valor_total_fretes: number;
  quantidade_ctes: number;
  frete_medio: number;
  total_por_transportadora: { transportadora_nome: string; valor_total_frete: number }[];
};

export type LinhaSerieConsolidada = {
  ano_mes?: string;
  rotulo?: string;
  totais: {
    faturamento_bruto?: number;
    valor_total_compras?: number;
    valor_total_fretes?: number;
    quantidade_notas?: number;
    quantidade_ctes?: number;
  };
  indicadores_gerenciais: {
    carga_tributaria_media_total_observada_pct?: number | null;
  };
};

export type PainelFiscalGerencialHistoricoResponse = {
  origem_dados: string;
  periodo: Record<string, string | undefined>;
  filtros: Record<string, string | boolean | null>;
  bloco_faturamento: {
    totais: TotaisFaturamento;
    indicadores_gerenciais: { carga_tributaria_media_total_observada_pct: number | null };
    notas_canceladas_historico: number;
  };
  bloco_compras: {
    totais: TotaisCompras;
    indicadores_gerenciais: { carga_tributaria_media_total_observada_pct: number | null };
  };
  bloco_fretes: {
    totais: TotaisFretes;
    indicadores_gerenciais: { aliquota_efetiva_media_icms_sobre_frete_pct: number | null };
    ctes_cancelados_historico: number;
  };
  visao_comparativa: {
    faturamento: number;
    compras: number;
    fretes: number;
    diferenca_venda_compra: number;
    peso_frete_sobre_faturamento_pct: number | null;
    carga_tributaria_total_observada: number;
    peso_carga_tributaria_sobre_faturamento_pct: number | null;
  };
  series: {
    faturamento_mensal: LinhaSerieConsolidada[];
    faturamento_trimestral: LinhaSerieConsolidada[];
    compras_mensal: LinhaSerieConsolidada[];
    compras_trimestral: LinhaSerieConsolidada[];
    fretes_mensal: LinhaSerieConsolidada[];
    fretes_trimestral: LinhaSerieConsolidada[];
  };
};

export const painelFiscalGerencialHistoricoService = {
  get: async (query: URLSearchParams) =>
    (await api.get<PainelFiscalGerencialHistoricoResponse>(`${base}?${query.toString()}`)).data,
};
