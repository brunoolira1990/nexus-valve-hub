import { toNumber } from '@/lib/numberFormat';
import type { ItemProposta } from '@/types';

/** Divisor fixo da regra comercial validada (não é markup genérico). */
export const PRECO_BASE_DIVISOR = 0.6;

export function normalizeNcm(ncm: string): string {
  return (ncm || '').replace(/\D/g, '');
}

/** NCM com dígitos suficientes para busca de regra fiscal (8 dígitos). */
export function ncmFiscalDigitsValid(ncm: string): boolean {
  return normalizeNcm(ncm).length >= 8;
}

export function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function computeIpiEntradaValor(custoProduto: number, ipiPct: number, ipiLegacy: number): number {
  const custo = toNumber(custoProduto);
  const pct = toNumber(ipiPct);
  const legacy = toNumber(ipiLegacy);
  if (pct > 0) return round2(custo * (pct / 100));
  return round2(legacy);
}

export function computeCustoCarregado(item: ItemProposta): number {
  const custo = toNumber(item.custo_utilizado);
  const ipiVal = computeIpiEntradaValor(
    custo,
    item.ipi_entrada_percentual,
    item.ipi_custo,
  );
  return round2(
    custo +
      ipiVal +
      toNumber(item.st_custo) +
      toNumber(item.frete) +
      toNumber(item.despesas) +
      toNumber(item.outros_impostos_custo),
  );
}

export function computePrecoBase(custoCarregado: number): number {
  if (custoCarregado <= 0 || PRECO_BASE_DIVISOR <= 0) return 0;
  return round2(custoCarregado / PRECO_BASE_DIVISOR);
}

export function percentualSaidaTotal(item: ItemProposta): number {
  const icms = toNumber(item.icms_saida_percentual);
  let pis = toNumber(item.pis_saida_percentual);
  let cofins = toNumber(item.cofins_saida_percentual);

  if (item.regra_fiscal_origem === 'CENARIO_SAIDA' || item.origem_regra_fiscal_saida === 'CENARIO_SAIDA') {
    if (item.deduzir_icms_base_pis && pis > 0 && icms > 0) {
      pis = round2((pis * (100 - icms)) / 100);
    }
    if (item.deduzir_icms_base_cofins && cofins > 0 && icms > 0) {
      cofins = round2((cofins * (100 - icms)) / 100);
    }
  }

  return round2(
    icms +
      pis +
      cofins +
      toNumber(item.ipi_saida_percentual) +
      toNumber(item.irpj_estimado_percentual) +
      toNumber(item.csll_estimada_percentual) +
      toNumber(item.comissao_percentual),
  );
}

export function computeValorCargaSaida(precoRef: number, pctSaida: number): number {
  if (precoRef <= 0) return 0;
  return round2(precoRef * (pctSaida / 100));
}

export function computeLucroMargem(
  precoRef: number,
  custoCarregado: number,
  valorCarga: number,
  freteSaida: number,
  outrasSaida: number,
): { lucro: number; margem: number } {
  const lucro = round2(precoRef - custoCarregado - valorCarga - freteSaida - outrasSaida);
  const margem = precoRef > 0 ? round2((lucro / precoRef) * 100) : 0;
  return { lucro, margem };
}

/** Recalcula campos derivados do item (espelha a validação do backend). */
export function recalcPropostaItem(item: ItemProposta): ItemProposta {
  const custoCarregado = computeCustoCarregado(item);
  const precoBase = computePrecoBase(custoCarregado);
  const modo = item.modo_preco === 'manual' ? 'manual' : 'sugerido';
  const precoSugerido = precoBase;
  const precoFinal = modo === 'manual' ? round2(Number(item.preco_final) || 0) : precoSugerido;
  const pctSaida = percentualSaidaTotal(item);
  const precoRef = modo === 'sugerido' ? precoSugerido : precoFinal;
  const valorCarga = computeValorCargaSaida(precoRef, pctSaida);
  const { lucro, margem } = computeLucroMargem(
    precoRef,
    custoCarregado,
    valorCarga,
    toNumber(item.frete_saida),
    toNumber(item.outras_despesas_saida),
  );
  return {
    ...item,
    custo_final: custoCarregado,
    preco_sugerido: precoSugerido,
    preco_final: precoFinal,
    valor_unitario: precoFinal,
    lucro_resultante: lucro,
    margem_resultante: margem,
  };
}

/** Receita comercial do item após desconto (unidade negociada). */
export function computeReceitaComercialItem(item: ItemProposta): number {
  const qtd = toNumber(item.quantidade_negociada ?? item.quantidade);
  const preco = toNumber(item.preco_por_unidade_negociada ?? item.preco_final);
  const desconto = toNumber(item.desconto);
  return round2(qtd * preco - desconto);
}

/** Custo carregado total do item (quantidade negociada × custo_final). */
export function computeCustoCarregadoTotalItem(item: ItemProposta): number {
  const qtd = toNumber(item.quantidade_negociada ?? item.quantidade);
  const custoFinal = toNumber(item.custo_final);
  return round2(qtd * custoFinal);
}

/** Cargas/despesas variáveis totais do item (quantidade negociada × unitários). */
export function computeCargasDespesasVariaveisTotalItem(item: ItemProposta): number {
  const qtd = toNumber(item.quantidade_negociada ?? item.quantidade);
  const precoRef = toNumber(item.preco_por_unidade_negociada ?? (item.modo_preco === 'manual' ? item.preco_final : item.preco_sugerido));
  const pctSaida = percentualSaidaTotal(item);
  const valorCarga = computeValorCargaSaida(precoRef, pctSaida);
  const freteSaida = toNumber(item.frete_saida);
  const outrasSaida = toNumber(item.outras_despesas_saida);
  return round2(qtd * (valorCarga + freteSaida + outrasSaida));
}

/** Resultado Estimado do item (gerencial, não persistido). */
export function computeResultadoEstimadoItem(item: ItemProposta): number {
  const receita = computeReceitaComercialItem(item);
  const custoTotal = computeCustoCarregadoTotalItem(item);
  const cargasTotal = computeCargasDespesasVariaveisTotalItem(item);
  return round2(receita - custoTotal - cargasTotal);
}

/** Margem de Contribuição Estimada do item (%). */
export function computeMargemContribuicaoEstimadaItem(item: ItemProposta): number {
  const receita = computeReceitaComercialItem(item);
  if (receita <= 0) return 0;
  const resultado = computeResultadoEstimadoItem(item);
  return round2((resultado / receita) * 100);
}

/** Consolidado da proposta: Receita comercial total. */
export function computeReceitaComercialConsolidada(itens: ItemProposta[]): number {
  return round2(itens.reduce((s, i) => s + computeReceitaComercialItem(i), 0));
}

/** Consolidado da proposta: Resultado Estimado total. */
export function computeResultadoEstimadoConsolidado(itens: ItemProposta[]): number {
  return round2(itens.reduce((s, i) => s + computeResultadoEstimadoItem(i), 0));
}

/** Consolidado da proposta: Margem de Contribuição Estimada (%). */
export function computeMargemContribuicaoEstimadaConsolidada(itens: ItemProposta[]): number {
  const receita = computeReceitaComercialConsolidada(itens);
  if (receita <= 0) return 0;
  const resultado = computeResultadoEstimadoConsolidado(itens);
  return round2((resultado / receita) * 100);
}
