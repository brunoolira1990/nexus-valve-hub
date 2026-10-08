import { formatMoneyBRL, formatPercentBR } from '@/lib/numberFields';

export type ReformaItemDados = Record<string, string | number | undefined>;

export function linhasReformaItemExibicao(dados: ReformaItemDados): string[] {
  const linhas: string[] = [];
  const push = (label: string, valor: string) => {
    if (valor && valor !== '—') linhas.push(`${label} ${valor}`);
  };
  push('Base original', formatMoneyBRL(dados.base_original_reforma));
  if (Number(dados.valor_deduzido_icms) > 0) {
    push('Dedução ICMS', formatMoneyBRL(dados.valor_deduzido_icms));
  }
  if (Number(dados.valor_deduzido_pis) > 0) {
    push('Dedução PIS', formatMoneyBRL(dados.valor_deduzido_pis));
  }
  if (Number(dados.valor_deduzido_cofins) > 0) {
    push('Dedução COFINS', formatMoneyBRL(dados.valor_deduzido_cofins));
  }
  if (Number(dados.valor_deduzido_ipi) > 0) {
    push('Dedução IPI', formatMoneyBRL(dados.valor_deduzido_ipi));
  }
  push('Base IBS/CBS', formatMoneyBRL(dados.base_ibs_cbs ?? dados.base_cbs));
  if (dados.formula_base_ibs_cbs) {
    linhas.push(`Fórmula: ${dados.formula_base_ibs_cbs}`);
  }
  if (dados.fonte_regra_base_ibs_cbs) {
    linhas.push(`Fonte: ${labelFonteRegraBase(String(dados.fonte_regra_base_ibs_cbs))}`);
  }
  push('Aliq. CBS', formatPercentBR(dados.aliquota_cbs));
  push('Valor CBS', formatMoneyBRL(dados.valor_cbs));
  push('Aliq. IBS UF', formatPercentBR(dados.aliquota_ibs_estadual));
  push('Valor IBS UF', formatMoneyBRL(dados.valor_ibs_estadual));
  const total = dados.total_ibs_cbs ?? dados.valor_total_ibs_cbs;
  if (total !== undefined && total !== '') {
    push('Total IBS/CBS', formatMoneyBRL(total));
  }
  return linhas.filter(Boolean);
}

export function labelFonteRegraBase(fonte: string): string {
  const map: Record<string, string> = {
    pendente: 'Pendente de confirmação',
    oficial: 'Nota Técnica / XSD oficial',
    contador: 'Orientação contábil',
    comparativo_erp: 'Comparativo ERP externo',
    manual: 'Manual / interno',
  };
  return map[fonte] || fonte;
}

export function badgeStatusBaseReforma(status?: string): { label: string; className: string } {
  const st = (status || 'pendente_confirmacao').toLowerCase();
  if (st === 'confirmada') {
    return { label: 'Base oficial confirmada', className: 'erp-badge-success' };
  }
  if (st === 'comparativo' || st === 'manual') {
    return { label: 'Base validada internamente', className: 'erp-badge-warning' };
  }
  return {
    label: 'Regra pendente de confirmação',
    className: 'erp-badge-warning',
  };
}

export function mensagemBaseReforma(dados: ReformaItemDados): string | null {
  const modo = String(dados.modo_base_ibs_cbs || 'BASE_CHEIA_OPERACAO');
  const fonte = String(dados.fonte_regra_base_ibs_cbs || 'pendente');
  if (modo === 'BASE_CHEIA_OPERACAO' && fonte === 'pendente') {
    return 'Base IBS/CBS calculada sobre o valor integral da operação.';
  }
  if (fonte === 'pendente' || dados.status_base_reforma === 'pendente_confirmacao') {
    return 'Regra de base pendente de confirmação oficial/contábil.';
  }
  return null;
}
