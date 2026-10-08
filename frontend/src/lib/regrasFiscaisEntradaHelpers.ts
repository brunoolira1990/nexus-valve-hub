import type {
  ConfiguracaoMatrizFiscalEntrada,
  RegraFiscalEntrada,
  ResultadoFiscalEntrada,
  StatusConfiguracaoFiscalEntrada,
} from '@/types';

export const MSG_SEM_REGRA_FISCAL_ENTRADA =
  'Não há regra fiscal de entrada configurada para este CFOP/NCM/UF. Cadastre uma regra ou valide com o fiscal.';

export function mensagemFiscalEntrada(rf: ResultadoFiscalEntrada | undefined): string {
  if (!rf) return MSG_SEM_REGRA_FISCAL_ENTRADA;
  if (rf.status === 'SEM_REGRA') {
    return rf.mensagens?.[0] || MSG_SEM_REGRA_FISCAL_ENTRADA;
  }
  return rf.mensagens?.[0] || '';
}

export type RegrasFiscaisEntradaPrefill = {
  cfop?: string;
  cfop_origem?: string;
  ncm?: string;
  uf_origem?: string;
  uf_destino?: string;
  tipo_operacao_fiscal?: string;
  movimenta_estoque?: boolean;
};

export function buildCriarRegraFiscalEntradaUrl(
  rf: ResultadoFiscalEntrada | undefined,
  ctx?: { uf_origem?: string; uf_destino?: string; tipo_operacao_fiscal?: string },
): string {
  const p = new URLSearchParams({ aba: 'entrada', nova: '1' });
  const cfop = (rf?.cfop_nf || '').trim();
  const ncm = (rf?.ncm_nf || '').trim();
  if (cfop) {
    p.set('cfop', cfop);
    p.set('cfop_origem', cfop);
  }
  if (ncm) p.set('ncm', ncm);
  const ufo = (ctx?.uf_origem || '').trim();
  const ufd = (ctx?.uf_destino || '').trim();
  if (ufo) p.set('uf_origem', ufo);
  if (ufd) p.set('uf_destino', ufd);
  const tipo = (ctx?.tipo_operacao_fiscal || '').trim();
  if (tipo) p.set('tipo_operacao_fiscal', tipo);
  if (tipo === 'FRETE_TRANSPORTE') p.set('movimenta_estoque', '0');
  return `/regras-fiscais?${p.toString()}`;
}

/** Prefill para regra de frete/CT-e a partir do CFOP do documento. */
export function buildCriarRegraFiscalCteUrl(opts: {
  cfop?: string;
  uf_origem?: string;
  uf_destino?: string;
}): string {
  const p = new URLSearchParams({
    aba: 'entrada',
    nova: '1',
    tipo_operacao_fiscal: 'FRETE_TRANSPORTE',
    movimenta_estoque: '0',
  });
  const cfop = (opts.cfop || '').trim();
  if (cfop) {
    p.set('cfop', cfop);
    p.set('cfop_origem', cfop);
  }
  const ufo = (opts.uf_origem || '').trim();
  const ufd = (opts.uf_destino || '').trim();
  if (ufo) p.set('uf_origem', ufo);
  if (ufd) p.set('uf_destino', ufd);
  return `/regras-fiscais?${p.toString()}`;
}

const TIPO_OP_LABEL: Record<string, string> = {
  COMPRA: 'Compra',
  DEVOLUCAO_VENDA: 'Devolução de venda',
  DEVOLUCAO_COMPRA: 'Devolução de compra',
  REMESSA: 'Remessa',
  BONIFICACAO: 'Bonificação',
  USO_CONSUMO: 'Uso e consumo',
  INDUSTRIALIZACAO: 'Industrialização',
  FRETE_TRANSPORTE: 'Frete / transporte (CT-e)',
  OUTROS: 'Outros',
};
export function labelCenarioRegraEntrada(regra: RegraFiscalEntrada): string {
  const label = (regra.label_configuracao || regra.descricao_cenario || '').trim();
  if (label) return label;
  return (regra.nome || '').trim() || '—';
}

export function cfopOrigemRegraEntrada(regra: RegraFiscalEntrada): string {
  return (regra.cfop_origem || regra.cfop || '').trim();
}

export function descricaoCriteriosRegraEntrada(regra: RegraFiscalEntrada): string {
  const partes: string[] = [];
  const cfopOrig = cfopOrigemRegraEntrada(regra);
  if (cfopOrig) partes.push(`CFOP orig. ${cfopOrig}`);
  if (regra.cfop_entrada?.trim()) partes.push(`CFOP entr. ${regra.cfop_entrada.trim()}`);
  if (regra.ncm?.trim()) {
    partes.push(`NCM ${regra.ncm.trim()}${regra.ncm_prefixo ? ' (prefixo)' : ''}`);
  }
  if (regra.uf_origem?.trim() || regra.uf_destino?.trim()) {
    partes.push(`UF ${regra.uf_origem || '*'}→${regra.uf_destino || '*'}`);
  }
  if (regra.tipo_operacao_fiscal) {
    partes.push(TIPO_OP_LABEL[regra.tipo_operacao_fiscal] || regra.tipo_operacao_fiscal);
  }
  if (regra.produto_id) partes.push(`Produto #${regra.produto_id}`);
  if (regra.fornecedor_id) partes.push(`Fornecedor #${regra.fornecedor_id}`);
  return partes.length ? partes.join(' · ') : '—';
}

export const HINT_CAMPOS_NAO_VALIDADOS =
  'Campos não preenchidos não serão comparados com o XML.';

export const REFORMA_TRIBUTARIA_KEYS = [
  'cst_ibs_cbs',
  'classificacao_tributaria',
  'aliquota_cbs',
  'aliquota_ibs_estadual',
  'aliquota_ibs_municipal',
  'reducao_cbs',
  'reducao_ibs',
  'diferimento_cbs',
  'diferimento_ibs',
  'credito_presumido_cbs',
  'credito_presumido_ibs',
  'modo_base_ibs_cbs',
  'deduzir_icms_base_ibs_cbs',
  'deduzir_pis_base_ibs_cbs',
  'deduzir_cofins_base_ibs_cbs',
  'deduzir_ipi_base_ibs_cbs',
  'deduzir_iss_base_ibs_cbs',
  'fonte_regra_base_ibs_cbs',
  'observacoes',
] as const;

export type ReformaTributariaForm = Record<(typeof REFORMA_TRIBUTARIA_KEYS)[number], string>;

export function emptyReformaTributaria(): ReformaTributariaForm {
  return Object.fromEntries(REFORMA_TRIBUTARIA_KEYS.map((k) => [k, ''])) as ReformaTributariaForm;
}

export function reformaFromApi(data?: Record<string, unknown> | null): ReformaTributariaForm {
  const base = emptyReformaTributaria();
  if (!data || typeof data !== 'object') return base;
  for (const key of REFORMA_TRIBUTARIA_KEYS) {
    const v = data[key];
    if (v !== null && v !== undefined && String(v).trim()) base[key] = String(v);
  }
  return base;
}

const REFORMA_PERCENT_KEYS_API = new Set([
  'aliquota_cbs',
  'aliquota_ibs_estadual',
  'aliquota_ibs_municipal',
  'reducao_cbs',
  'reducao_ibs',
  'diferimento_cbs',
  'diferimento_ibs',
  'credito_presumido_cbs',
  'credito_presumido_ibs',
]);

export function reformaToApi(form: ReformaTributariaForm): Record<string, string> | null {
  const out: Record<string, string> = {};
  for (const key of REFORMA_TRIBUTARIA_KEYS) {
    const v = (form[key] || '').trim();
    if (!v) continue;
    if (REFORMA_PERCENT_KEYS_API.has(key)) {
      const n = toApiDecimal(v);
      if (n !== null) out[key] = String(n);
      else out[key] = v;
    } else {
      out[key] = v;
    }
  }
  return Object.keys(out).length ? out : null;
}

export function decFieldToForm(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === '') return '';
  return String(v);
}

export function toApiDecimal(v: string | number | null | undefined): number | null {
  const s = String(v ?? '')
    .trim()
    .replace(',', '.');
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** Normaliza texto opcional: vazio → null quando o backend espera ausência de valor. */
export function textoOpcionalParaApi(v: string | null | undefined): string | null {
  const s = (v ?? '').trim();
  return s || null;
}

export function abaRegraEntradaParaErro(mensagem: string): string | null {
  const msg = mensagem.toLowerCase();
  if (/cst|csosn|icms|fcp|modalidade_bc/.test(msg)) return 'icms';
  if (/ipi/.test(msg)) return 'ipi';
  if (/pis/.test(msg)) return 'pis';
  if (/cofins/.test(msg)) return 'cofins';
  if (/reforma|ibs|cbs/.test(msg)) return 'reforma';
  if (/severidade|estoque|crédito|credito|certificado|efeito/.test(msg)) return 'efeitos';
  if (/cfop|uf|fornecedor|tipo.?oper|classifica/.test(msg)) return 'cfop';
  return null;
}

export function tituloMatchRegraFiscal(rf: ResultadoFiscalEntrada | undefined): string | undefined {
  const motivos = (rf?.regra_match_motivos || []).filter((m) => m !== 'Critérios gerais');
  if (!motivos.length) return undefined;
  return `Regra aplicada por: ${motivos.join(', ')}.`;
}

export function resumoImpostosLinha(snap?: Record<string, string | undefined>): string {
  if (!snap) return '';
  const partes: string[] = [];
  if (snap.cst_icms || snap.csosn || snap.aliquota_fcp) {
    let icms = `ICMS ${[snap.cst_icms, snap.csosn].filter(Boolean).join('/')}`;
    if (!snap.cst_icms && !snap.csosn) icms = 'ICMS';
    if (snap.aliquota_icms) icms += ` ${snap.aliquota_icms}%`;
    if (snap.aliquota_fcp) icms += ` · FCP ${snap.aliquota_fcp}%`;
    partes.push(icms);
  }
  if (snap.cst_ipi) {
    let s = `IPI ${snap.cst_ipi}`;
    if (snap.aliquota_ipi) s += ` ${snap.aliquota_ipi}%`;
    partes.push(s);
  }
  if (snap.cst_pis) {
    let s = `PIS ${snap.cst_pis}`;
    if (snap.aliquota_pis) s += ` ${snap.aliquota_pis}%`;
    partes.push(s);
  }
  if (snap.cst_cofins) {
    let s = `COFINS ${snap.cst_cofins}`;
    if (snap.aliquota_cofins) s += ` ${snap.aliquota_cofins}%`;
    partes.push(s);
  }
  return partes.join(' · ');
}

export function labelStatusConfiguracao(status: StatusConfiguracaoFiscalEntrada): string {
  switch (status) {
    case 'CONFIGURADO':
      return 'Configurado';
    case 'INCOMPLETO':
      return 'Incompleta';
    case 'SEM_CONFIGURACAO':
      return 'Não configurado';
    default:
      return status;
  }
}

export function badgeClassStatusConfiguracao(status: StatusConfiguracaoFiscalEntrada): string {
  switch (status) {
    case 'CONFIGURADO':
      return 'erp-badge-info text-[10px]';
    case 'INCOMPLETO':
      return 'erp-badge-warning text-[10px]';
    default:
      return 'erp-badge-secondary text-[10px]';
  }
}

export function resumoEfeitosMatriz(cfg: ConfiguracaoMatrizFiscalEntrada): string {
  const partes: string[] = [];
  partes.push(cfg.efeitos.movimenta_estoque ? 'Mov. estoque' : 'Sem mov. estoque');
  if (cfg.efeitos.exige_certificado_fornecedor) partes.push('Cert. forn.');
  if (!cfg.efeitos.permite_credito_fiscal) partes.push('Sem crédito');
  return partes.join(' · ');
}

export function labelSeveridadeRegraEntrada(severidade: string): string {
  switch (severidade) {
    case 'BLOQUEIO':
      return 'Bloqueio';
    case 'ALERTA':
      return 'Alerta';
    case 'INFORMATIVO':
      return 'Informativo';
    default:
      return severidade;
  }
}
