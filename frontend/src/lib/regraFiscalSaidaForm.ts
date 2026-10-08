import {
  emptyRecomendacoesNfe,
  type RecomendacoesNfeForm,
} from '@/lib/recomendacoesNfeSaida';
import {
  emptyReformaTributaria,
  type ReformaTributariaForm,
} from '@/lib/regrasFiscaisSaidaHelpers';
import type { RegraFiscalSaida } from '@/types';

export type AbaFormRegraFiscalSaida =
  | 'cfop'
  | 'icms'
  | 'ipi'
  | 'pis'
  | 'cofins'
  | 'reforma'
  | 'efeitos'
  | 'recomendacoes_nfe';

export type FormRegraFiscalSaida = Omit<
  RegraFiscalSaida,
  'id' | 'criado_em' | 'atualizado_em' | 'label_configuracao' | 'status_configuracao' | 'resumo_impostos'
> & {
    icms_st_aplicavel: '' | 'sim' | 'nao';
    difal_aplicavel: '' | 'sim' | 'nao';
    fcp_aplicavel: '' | 'sim' | 'nao';
  consumidor_final_tri: '' | 'sim' | 'nao';
  reforma_tributaria: ReformaTributariaForm;
  recomendacoes_nfe: RecomendacoesNfeForm;
};

export const emptyFormRegraFiscalSaida: FormRegraFiscalSaida = {
  nome: '',
  codigo: '',
  ativo: true,
  prioridade: 10,
  uf_origem: '',
  uf_destino: '',
  destinatario_contribuinte: 'QUALQUER',
  consumidor_final_tri: '',
  consumidor_final: null,
  cfop_venda: '',
  cfop_venda_st: '',
  tipo_operacao: '',
  descricao_cenario: '',
  cst_icms: '',
  csosn: '',
  modalidade_bc_icms: '',
  aliquota_icms: '',
  reducao_bc_icms: '',
  motivo_desoneracao_icms: '',
  codigo_beneficio_icms: '',
  icms_st_aplicavel: '',
  cst_icms_st: '',
  aliquota_icms_st: '',
  mva_st: '',
  reducao_bc_st: '',
  difal_aplicavel: '',
  aliquota_icms_interestadual: '',
  aliquota_icms_interna_destino: '',
  fcp_aplicavel: '',
  aliquota_fcp: '',
  aliquota_fcp_st: '',
  reducao_bc_fcp: '',
  valor_fcp_unidade: '',
  reforma_tributaria: emptyReformaTributaria(),
  recomendacoes_nfe: emptyRecomendacoesNfe(),
  cst_ipi: '',
  tipo_calculo_ipi: '',
  aliquota_ipi: '',
  valor_ipi_unidade: '',
  enquadramento_ipi: '',
  cst_pis: '',
  tipo_calculo_pis: '',
  aliquota_pis: '',
  reducao_base_pis: '',
  valor_minimo_pis_unidade: '',
  aliquota_pis_st: '',
  deduzir_icms_base_pis: false,
  cst_cofins: '',
  tipo_calculo_cofins: '',
  aliquota_cofins: '',
  reducao_base_cofins: '',
  valor_minimo_cofins_unidade: '',
  aliquota_cofins_st: '',
  deduzir_icms_base_cofins: false,
  movimenta_estoque: true,
  gera_financeiro: true,
  informacoes_complementares: '',
  observacoes: '',
};

export const ABAS_FORM_REGRA_FISCAL_SAIDA: { id: AbaFormRegraFiscalSaida; label: string }[] = [
  { id: 'cfop', label: 'CFOP' },
  { id: 'icms', label: 'ICMS' },
  { id: 'ipi', label: 'IPI' },
  { id: 'pis', label: 'PIS' },
  { id: 'cofins', label: 'COFINS' },
  { id: 'reforma', label: 'Reforma Tributária' },
  { id: 'efeitos', label: 'Efeitos' },
  { id: 'recomendacoes_nfe', label: 'Recomendações NF-e/DANFE' },
];
