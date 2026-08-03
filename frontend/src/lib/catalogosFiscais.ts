/** Catálogos para UX do editor fiscal (valores persistidos como no backend). */

export type OpcaoCatalogo = { value: string; label: string };

export const OPCAO_VAZIA: OpcaoCatalogo = { value: '', label: '— Não informado —' };

export const CST_ICMS_OPCOES: OpcaoCatalogo[] = [
  { value: '00', label: '00 — Tributada integralmente' },
  { value: '10', label: '10 — Tributada com cobrança de ICMS ST' },
  { value: '20', label: '20 — Com redução de base de cálculo' },
  { value: '30', label: '30 — Isenta ou não tributada com ICMS ST' },
  { value: '40', label: '40 — Isenta' },
  { value: '41', label: '41 — Não tributada' },
  { value: '50', label: '50 — Suspensão' },
  { value: '51', label: '51 — Diferimento' },
  { value: '60', label: '60 — ICMS cobrado anteriormente por ST' },
  { value: '70', label: '70 — Redução de BC e ICMS ST' },
  { value: '90', label: '90 — Outras' },
];

export const CSOSN_OPCOES: OpcaoCatalogo[] = [
  { value: '101', label: '101 — Tributada com permissão de crédito' },
  { value: '102', label: '102 — Tributada sem permissão de crédito' },
  { value: '103', label: '103 — Isenção para faixa de receita' },
  { value: '201', label: '201 — Tributada com ST e crédito' },
  { value: '202', label: '202 — Tributada com ST sem crédito' },
  { value: '203', label: '203 — Isenção com ST' },
  { value: '300', label: '300 — Imune' },
  { value: '400', label: '400 — Não tributada' },
  { value: '500', label: '500 — ICMS cobrado anteriormente por ST' },
  { value: '900', label: '900 — Outros' },
];

export const MODALIDADE_BC_ICMS_OPCOES: OpcaoCatalogo[] = [
  { value: '0', label: '0 — Margem Valor Agregado' },
  { value: '1', label: '1 — Pauta' },
  { value: '2', label: '2 — Preço tabelado máximo' },
  { value: '3', label: '3 — Valor da operação' },
];

export const CBENEF_SEM_CODIGO_LITERAL = 'SEM CBENEF';

/** Marcadores de UI legados — nunca devem ir no XML como cBenef. */
export function ehMarcadorCbenefNaoFiscal(val: string | null | undefined): boolean {
  const raw = (val ?? '').trim();
  if (!raw) return false;
  const compact = raw.toUpperCase().split(/\s+/).filter(Boolean).join(' ');
  const markers = new Set([
    'SEM CBENEF',
    'SEM BENEFICIO',
    'SEM BENEFÍCIO',
    'SEM CODIGO',
    'SEM CÓDIGO',
    'N/A',
    'NA',
    '-',
    '—',
  ]);
  if (markers.has(compact)) return true;
  const nospace = compact.replace(/\s+/g, '').replace(/[ÍÓ]/g, (c) => (c === 'Í' ? 'I' : 'O'));
  return ['SEMCBENEF', 'SEMBENEFICIO', 'SEMCODIGO'].includes(nospace) || compact.includes(' ');
}

/**
 * Opções do seletor: vazio = omitir tag cBenef no XML.
 * O literal SEM CBENEF foi removido da lista — era serializado e rejeitado (cStat 946).
 */
export const CODIGO_BENEFICIO_ICMS_OPCOES: OpcaoCatalogo[] = [
  { value: '', label: '— Não informar (omite cBenef no XML) —' },
];

export const MOTIVO_DESONERACAO_ICMS_OPCOES: OpcaoCatalogo[] = [
  { value: '1', label: '1 — Táxi' },
  { value: '3', label: '3 — Produtor agropecuário' },
  { value: '4', label: '4 — Frotista/locadora' },
  { value: '5', label: '5 — Diplomático/consular' },
  { value: '6', label: '6 — Utilitários e motocicletas da Amazônia' },
  { value: '7', label: '7 — SUFRAMA' },
  { value: '8', label: '8 — Venda a órgão público' },
  { value: '9', label: '9 — Outros' },
  { value: '10', label: '10 — Deficiente condutor' },
  { value: '11', label: '11 — Deficiente não condutor' },
  { value: '12', label: '12 — Órgão de fomento e desenvolvimento agropecuário' },
  { value: '16', label: '16 — Olimpíadas Rio 2016' },
  { value: '90', label: '90 — Solicitado pelo Fisco' },
];

export const TIPO_CALCULO_TRIBUTO_OPCOES: OpcaoCatalogo[] = [
  { value: 'PCT', label: 'Percentual sobre base' },
  { value: 'UNID', label: 'Valor por unidade' },
  { value: 'SEM', label: 'Sem cálculo' },
];

export const CST_IPI_OPCOES: OpcaoCatalogo[] = [
  { value: '00', label: '00 — Entrada com recuperação de crédito' },
  { value: '49', label: '49 — Outras entradas' },
  { value: '50', label: '50 — Saída tributada' },
  { value: '51', label: '51 — Saída tributada com alíquota zero' },
  { value: '52', label: '52 — Saída isenta' },
  { value: '53', label: '53 — Saída não tributada' },
  { value: '54', label: '54 — Saída imune' },
  { value: '55', label: '55 — Saída com suspensão' },
  { value: '99', label: '99 — Outras saídas' },
];

export const CST_PIS_COFINS_OPCOES: OpcaoCatalogo[] = [
  { value: '01', label: '01 — Operação tributável (alíquota básica)' },
  { value: '02', label: '02 — Operação tributável (alíquota diferenciada)' },
  { value: '03', label: '03 — Operação tributável (alíquota por unidade)' },
  { value: '04', label: '04 — Operação tributável (monofásica — revenda a zero)' },
  { value: '05', label: '05 — Operação tributável (ST)' },
  { value: '06', label: '06 — Operação tributável (alíquota zero)' },
  { value: '07', label: '07 — Operação isenta' },
  { value: '08', label: '08 — Operação sem incidência' },
  { value: '09', label: '09 — Operação com suspensão' },
  { value: '49', label: '49 — Outras operações de saída' },
  { value: '50', label: '50 — Crédito vinculado a receita tributada' },
  { value: '51', label: '51 — Crédito vinculado a receita não tributada' },
  { value: '52', label: '52 — Crédito vinculado a exportação' },
  { value: '53', label: '53 — Crédito vinculado a receitas diversas' },
  { value: '54', label: '54 — Crédito presumido' },
  { value: '55', label: '55 — Crédito presumido — exportação' },
  { value: '56', label: '56 — Crédito presumido — outras operações' },
  { value: '60', label: '60 — Crédito presumido — aquisição vinculada a receita tributada' },
  { value: '61', label: '61 — Crédito presumido — aquisição vinculada a receita não tributada' },
  { value: '62', label: '62 — Crédito presumido — aquisição vinculada a exportação' },
  { value: '63', label: '63 — Crédito presumido — aquisição vinculada a receitas diversas' },
  { value: '64', label: '64 — Crédito presumido — outras operações' },
  { value: '65', label: '65 — Crédito presumido — aquisição ST' },
  { value: '66', label: '66 — Crédito presumido — outras ST' },
  { value: '67', label: '67 — Crédito presumido — exportação ST' },
  { value: '70', label: '70 — Operação de aquisição sem direito a crédito' },
  { value: '71', label: '71 — Operação de aquisição com isenção' },
  { value: '72', label: '72 — Operação de aquisição com suspensão' },
  { value: '73', label: '73 — Operação de aquisição a alíquota zero' },
  { value: '74', label: '74 — Operação de aquisição sem incidência' },
  { value: '75', label: '75 — Operação de aquisição por ST' },
  { value: '98', label: '98 — Outras operações de entrada' },
  { value: '99', label: '99 — Outras operações' },
];

export const BOOL_TRI_OPCOES: { value: '' | 'sim' | 'nao'; label: string }[] = [
  { value: '', label: 'Não configurado' },
  { value: 'sim', label: 'Sim' },
  { value: 'nao', label: 'Não' },
];

export const CONSUMIDOR_FINAL_OPCOES: { value: '' | 'sim' | 'nao'; label: string }[] = [
  { value: '', label: 'Indiferente' },
  { value: 'sim', label: 'Sim' },
  { value: 'nao', label: 'Não' },
];

export const REFORMA_TRIBUTARIA_LABELS_SAIDA: Record<string, string> = {
  cst_ibs_cbs: 'CST IBS/CBS',
  classificacao_tributaria: 'Classificação tributária',
  aliquota_cbs: 'Alíquota CBS (%)',
  aliquota_ibs_estadual: 'Alíquota IBS estadual (%)',
  aliquota_ibs_municipal: 'Alíquota IBS municipal (%)',
  reducao_cbs: 'Redução CBS (%)',
  reducao_ibs: 'Redução IBS (%)',
  diferimento_cbs: 'Diferimento CBS (%)',
  diferimento_ibs: 'Diferimento IBS (%)',
  credito_presumido_cbs: 'Crédito presumido CBS (%)',
  credito_presumido_ibs: 'Crédito presumido IBS (%)',
  modo_base_ibs_cbs: 'Modo base IBS/CBS',
  deduzir_icms_base_ibs_cbs: 'Deduzir ICMS da base',
  deduzir_pis_base_ibs_cbs: 'Deduzir PIS da base',
  deduzir_cofins_base_ibs_cbs: 'Deduzir COFINS da base',
  deduzir_ipi_base_ibs_cbs: 'Deduzir IPI da base',
  deduzir_iss_base_ibs_cbs: 'Deduzir ISS da base',
  fonte_regra_base_ibs_cbs: 'Fonte da regra de base',
  observacoes: 'Observações',
};

export const MODO_BASE_IBS_CBS_OPCOES: OpcaoCatalogo[] = [
  { value: 'BASE_CHEIA_OPERACAO', label: 'Base cheia da operação (vProd)' },
  { value: 'BASE_SEM_ICMS', label: 'Base sem ICMS (vProd - vICMS)' },
  { value: 'BASE_SEM_ICMS_PIS_COFINS', label: 'Base sem ICMS, PIS e COFINS' },
  { value: 'BASE_SEM_ICMS_PIS_COFINS_IPI', label: 'Base sem ICMS, PIS, COFINS e IPI' },
  { value: 'BASE_OFICIAL_2026', label: 'Base oficial 2026 (referência NT 2025.002)' },
  { value: 'BASE_CUSTOMIZADA', label: 'Base customizada (flags manuais)' },
];

export const FONTE_REGRA_BASE_IBS_CBS_OPCOES: OpcaoCatalogo[] = [
  { value: 'pendente', label: 'Pendente de confirmação' },
  { value: 'oficial', label: 'Nota Técnica / XSD oficial' },
  { value: 'contador', label: 'Orientação contábil' },
  { value: 'comparativo_erp', label: 'Comparativo ERP externo' },
  { value: 'manual', label: 'Manual / interno' },
];

export const CST_IBS_CBS_OPCOES: OpcaoCatalogo[] = [
  { value: '000', label: '000 — Tributação integral' },
  { value: '010', label: '010 — Tributação com alíquotas uniformes' },
  { value: '011', label: '011 — Tributação com alíquotas uniformes reduzidas' },
  { value: '200', label: '200 — Alíquota reduzida' },
  { value: '210', label: '210 — Redução de alíquota com redutor de base' },
  { value: '220', label: '220 — Alíquota fixa' },
  { value: '400', label: '400 — Isenção' },
  { value: '410', label: '410 — Imunidade e não incidência' },
  { value: '510', label: '510 — Diferimento' },
  { value: '550', label: '550 — Suspensão' },
  { value: '620', label: '620 — Tributação monofásica' },
  { value: '800', label: '800 — Transferência de crédito' },
  { value: '810', label: '810 — Ajustes' },
  { value: '900', label: '900 — Outros' },
];

export const CLASSIFICACAO_TRIBUTARIA_OPCOES: OpcaoCatalogo[] = [
  {
    value: '000001',
    label: '000001 — Situações tributadas integralmente pelo IBS e CBS',
  },
];

export const AVISO_REFORMA_TRIBUTARIA_SAIDA =
  'Campos da Reforma Tributária são preparatórios e parametrizáveis. Revise com a contabilidade antes de ativar o cenário.';

export const HINT_EXCECAO_REFORMA_ESCOPO =
  'Exceções por NCM ou produto devem ser configuradas criando escopos específicos no cenário fiscal.';

export const REFORMA_CAMPOS_IBS = [
  'aliquota_ibs_estadual',
  'aliquota_ibs_municipal',
  'reducao_ibs',
  'diferimento_ibs',
  'credito_presumido_ibs',
] as const;

export const REFORMA_CAMPOS_CBS = [
  'aliquota_cbs',
  'reducao_cbs',
  'diferimento_cbs',
  'credito_presumido_cbs',
] as const;

export const HINT_EDITOR_FISCAL_SAIDA = [
  'Campos vazios não serão enviados como regra fiscal.',
  'Revise CST, CFOP e alíquotas com o contador antes de ativar o cenário.',
  'Presets são auxiliares e não substituem validação fiscal.',
] as const;

export const AVISO_PRESET_APLICADO = 'Revise os valores antes de salvar.';

/** Campos da aba ICMS afetados por presets. */
export const CAMPOS_ICMS_PRESET = [
  'cst_icms',
  'csosn',
  'modalidade_bc_icms',
  'aliquota_icms',
  'reducao_bc_icms',
  'motivo_desoneracao_icms',
  'icms_st_aplicavel',
  'cst_icms_st',
  'aliquota_icms_st',
  'mva_st',
  'reducao_bc_st',
  'fcp_aplicavel',
  'aliquota_fcp',
] as const;

export type PatchPresetIcms = Partial<Record<(typeof CAMPOS_ICMS_PRESET)[number], string>>;

export type PresetIcmsSaida = {
  id: string;
  label: string;
  descricao: string;
  patch: PatchPresetIcms;
};

export const PRESETS_ICMS_SAIDA: PresetIcmsSaida[] = [
  {
    id: 'op_padrao_tributada',
    label: 'Operação padrão tributada',
    descricao: 'Venda/revenda com ICMS integral',
    patch: {
      cst_icms: '00',
      modalidade_bc_icms: '3',
      aliquota_icms: '18',
      icms_st_aplicavel: 'nao',
      fcp_aplicavel: 'nao',
    },
  },
  {
    id: 'reducao_bc',
    label: 'Redução de base de cálculo',
    descricao: 'CST 20 com redução de BC',
    patch: {
      cst_icms: '20',
      modalidade_bc_icms: '3',
      reducao_bc_icms: '20',
      icms_st_aplicavel: 'nao',
    },
  },
  {
    id: 'cf_contribuinte',
    label: 'Consumidor final contribuinte',
    descricao: 'Perfil contribuinte — ajuste destinatário na aba CFOP',
    patch: {
      cst_icms: '00',
      modalidade_bc_icms: '3',
      aliquota_icms: '18',
    },
  },
  {
    id: 'cf_nao_contribuinte',
    label: 'Consumidor final não contribuinte',
    descricao: 'Perfil não contribuinte — ajuste destinatário na aba CFOP',
    patch: {
      cst_icms: '00',
      modalidade_bc_icms: '3',
      aliquota_icms: '18',
    },
  },
  {
    id: 'simples_nacional',
    label: 'Simples Nacional',
    descricao: 'CSOSN 102 — tributada sem permissão de crédito',
    patch: {
      csosn: '102',
      cst_icms: '',
      modalidade_bc_icms: '3',
      icms_st_aplicavel: 'nao',
    },
  },
  {
    id: 'origem_estrangeira',
    label: 'Mercadoria de origem estrangeira',
    descricao: 'Referência para importação/repasse — revise alíquotas',
    patch: {
      cst_icms: '00',
      modalidade_bc_icms: '3',
      aliquota_icms: '4',
      icms_st_aplicavel: 'sim',
    },
  },
];

export function valorNoCatalogo(value: string, opcoes: OpcaoCatalogo[]): boolean {
  if (!value) return true;
  return opcoes.some((o) => o.value === value);
}

export function opcoesComValorAtual(value: string, opcoes: OpcaoCatalogo[]): OpcaoCatalogo[] {
  if (!value || valorNoCatalogo(value, opcoes)) return opcoes;
  return [{ value, label: `Valor atual: ${value}` }, ...opcoes];
}

export function labelDestinatarioConfig(dest: string): string {
  switch (dest) {
    case 'CONTRIBUINTE':
      return 'Contribuinte';
    case 'NAO_CONTRIBUINTE':
      return 'Não contribuinte';
    default:
      return 'Qualquer destinatário';
  }
}

/** Catálogo auxiliar de CFOP de saída (UX — ampliável). */
export const CFOP_SAIDA_OPCOES: OpcaoCatalogo[] = [
  { value: '5101', label: '5101 — Venda de produção do estabelecimento' },
  { value: '5102', label: '5102 — Venda de mercadoria adquirida ou recebida de terceiros' },
  {
    value: '5105',
    label: '5105 — Venda de produção do estabelecimento que não deva transitar pelo estabelecimento depositante',
  },
  {
    value: '5106',
    label: '5106 — Venda de mercadoria adquirida ou recebida de terceiros que não deva transitar pelo estabelecimento depositante',
  },
  { value: '5401', label: '5401 — Venda de produção com ST' },
  { value: '5403', label: '5403 — Venda de mercadoria adquirida ou recebida de terceiros com ST' },
  {
    value: '5405',
    label: '5405 — Venda de mercadoria adquirida ou recebida de terceiros sujeita ao regime de ST, na condição de substituído',
  },
  { value: '5910', label: '5910 — Remessa em bonificação, doação ou brinde' },
  {
    value: '5922',
    label: '5922 — Lançamento efetuado a título de simples faturamento decorrente de venda para entrega futura',
  },
  { value: '5923', label: '5923 — Remessa de mercadoria por conta e ordem de terceiros' },
  { value: '5949', label: '5949 — Outra saída de mercadoria ou prestação de serviço não especificado' },
  { value: '6101', label: '6101 — Venda de produção do estabelecimento' },
  { value: '6102', label: '6102 — Venda de mercadoria adquirida ou recebida de terceiros' },
  {
    value: '6105',
    label: '6105 — Venda de produção do estabelecimento que não deva transitar pelo estabelecimento depositante',
  },
  {
    value: '6106',
    label: '6106 — Venda de mercadoria adquirida ou recebida de terceiros que não deva transitar pelo estabelecimento depositante',
  },
  {
    value: '6108',
    label: '6108 — Venda de mercadoria adquirida ou recebida de terceiros, destinada a não contribuinte',
  },
  { value: '6401', label: '6401 — Venda de produção com ST' },
  { value: '6403', label: '6403 — Venda de mercadoria adquirida ou recebida de terceiros com ST' },
  {
    value: '6404',
    label: '6404 — Venda de mercadoria sujeita ao regime de ST, cujo imposto já tenha sido retido anteriormente',
  },
  { value: '6910', label: '6910 — Remessa em bonificação, doação ou brinde' },
  {
    value: '6922',
    label: '6922 — Lançamento efetuado a título de simples faturamento decorrente de venda para entrega futura',
  },
  { value: '6923', label: '6923 — Remessa de mercadoria por conta e ordem de terceiros' },
  { value: '6949', label: '6949 — Outra saída de mercadoria ou prestação de serviço não especificado' },
  { value: '7101', label: '7101 — Venda de produção do estabelecimento' },
  { value: '7102', label: '7102 — Venda de mercadoria adquirida ou recebida de terceiros' },
  { value: '7949', label: '7949 — Outra saída de mercadoria ou prestação de serviço não especificado' },
];

export const HINT_CFOP_SAIDA =
  'Selecione o CFOP aplicável. O catálogo é auxiliar; confirme a operação com a contabilidade.';

/** Catálogo auxiliar de CFOP de entrada (compra, devolução, remessa). */
export const CFOP_ENTRADA_OPCOES: OpcaoCatalogo[] = [
  { value: '1102', label: '1102 — Compra para comercialização' },
  { value: '1201', label: '1201 — Devolução de venda de produção do estabelecimento' },
  { value: '1202', label: '1202 — Devolução de venda de mercadoria adquirida de terceiros' },
  { value: '1403', label: '1403 — Compra para comercialização em operação com ST' },
  { value: '1556', label: '1556 — Compra de material para uso ou consumo' },
  { value: '1901', label: '1901 — Entrada para industrialização por encomenda' },
  { value: '1902', label: '1902 — Retorno de mercadoria utilizada na industrialização' },
  { value: '1949', label: '1949 — Outra entrada de mercadoria ou prestação de serviço' },
  { value: '2102', label: '2102 — Compra para comercialização' },
  { value: '2201', label: '2201 — Devolução de venda de produção do estabelecimento' },
  { value: '2202', label: '2202 — Devolução de venda de mercadoria adquirida de terceiros' },
  { value: '2403', label: '2403 — Compra para comercialização em operação com ST' },
  { value: '2556', label: '2556 — Compra de material para uso ou consumo' },
  { value: '2901', label: '2901 — Entrada para industrialização por encomenda' },
  { value: '2902', label: '2902 — Retorno de mercadoria utilizada na industrialização' },
  { value: '2949', label: '2949 — Outra entrada de mercadoria ou prestação de serviço' },
];

export const HINT_CFOP_ENTRADA =
  'Selecione o CFOP de entrada. Em devolução de venda use 1201/1202 (mesmo estado) ou 2201/2202 (outra UF).';

/** Alíquotas comuns — evita digitação manual pelo operador. */
export const ALIQUOTA_PIS_OPCOES: OpcaoCatalogo[] = [
  { value: '0.65', label: '0,65% — Lucro Presumido (cumulativo)' },
  { value: '1.65', label: '1,65% — Não cumulativo' },
];

export const ALIQUOTA_COFINS_OPCOES: OpcaoCatalogo[] = [
  { value: '3', label: '3,00% — Lucro Presumido (cumulativo)' },
  { value: '7.6', label: '7,60% — Não cumulativo' },
];

export const ALIQUOTA_ICMS_OPCOES: OpcaoCatalogo[] = [
  { value: '4', label: '4%' },
  { value: '7', label: '7%' },
  { value: '12', label: '12%' },
  { value: '17', label: '17%' },
  { value: '18', label: '18%' },
  { value: '19', label: '19%' },
  { value: '20', label: '20%' },
  { value: '25', label: '25%' },
];

export const ALIQUOTA_CBS_2026_OPCOES: OpcaoCatalogo[] = [
  { value: '0.9', label: '0,90% — alíquota-teste CBS 2026' },
];

export const ALIQUOTA_IBS_UF_2026_OPCOES: OpcaoCatalogo[] = [
  { value: '0.1', label: '0,10% — alíquota-teste IBS UF 2026' },
];

export const EMPTY_LABEL_NAO_VALIDAR = '— Não validar / espelha origem —';

export function normalizarCfopCodigo(valor: string): string {
  return (valor || '').replace(/\D/g, '').slice(0, 4);
}

export function labelCfopCatalogo(
  codigo: string,
  opcoes: OpcaoCatalogo[] = CFOP_SAIDA_OPCOES,
): string {
  const c = normalizarCfopCodigo(codigo);
  if (!c) return '';
  const op = opcoes.find((o) => o.value === c);
  if (op) return op.label;
  // Tenta também catálogo de entrada
  const opEnt = CFOP_ENTRADA_OPCOES.find((o) => o.value === c);
  if (opEnt) return opEnt.label;
  return `Valor atual: ${c}`;
}

export function prefixoCfopProvavel(ufOrigem: string, ufDestino: string): string | null {
  const o = (ufOrigem || '').trim().toUpperCase();
  const d = (ufDestino || '').trim().toUpperCase();
  if (!o || !d) return null;
  if (d === 'EX' || d === 'EXTERIOR') return '7';
  if (o === d) return '5';
  return '6';
}

export function filtrarCfopBusca(opcoes: OpcaoCatalogo[], busca: string): OpcaoCatalogo[] {
  const q = busca.trim().toLowerCase();
  if (!q) return opcoes;
  const digits = q.replace(/\D/g, '');
  return opcoes.filter((o) => {
    if (o.label.toLowerCase().includes(q)) return true;
    if (digits && o.value.includes(digits)) return true;
    return false;
  });
}

export function agruparCfopSaida(
  opcoes: OpcaoCatalogo[],
  ufOrigem: string,
  ufDestino: string,
): { maisProvaveis: OpcaoCatalogo[]; outros: OpcaoCatalogo[] } {
  const prefix = prefixoCfopProvavel(ufOrigem, ufDestino);
  if (!prefix) return { maisProvaveis: [], outros: opcoes };
  return {
    maisProvaveis: opcoes.filter((o) => o.value.startsWith(prefix)),
    outros: opcoes.filter((o) => !o.value.startsWith(prefix)),
  };
}
