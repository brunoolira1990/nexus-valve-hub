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
  if (ipiPct > 0) return round2(custoProduto * (ipiPct / 100));
  return round2(ipiLegacy);
}

export function computeCustoCarregado(item: ItemProposta): number {
  const custo = item.custo_utilizado ?? 0;
  const ipiVal = computeIpiEntradaValor(custo, item.ipi_entrada_percentual ?? 0, item.ipi_custo ?? 0);
  return round2(
    custo +
      ipiVal +
      (item.st_custo ?? 0) +
      (item.frete ?? 0) +
      (item.despesas ?? 0) +
      (item.outros_impostos_custo ?? 0),
  );
}

export function computePrecoBase(custoCarregado: number): number {
  if (custoCarregado <= 0 || PRECO_BASE_DIVISOR <= 0) return 0;
  return round2(custoCarregado / PRECO_BASE_DIVISOR);
}

export function percentualSaidaTotal(item: ItemProposta): number {
  return round2(
    (item.icms_saida_percentual ?? 0) +
      (item.pis_saida_percentual ?? 0) +
      (item.cofins_saida_percentual ?? 0) +
      (item.ipi_saida_percentual ?? 0) +
      (item.irpj_estimado_percentual ?? 0) +
      (item.csll_estimada_percentual ?? 0) +
      (item.comissao_percentual ?? 0),
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
    item.frete_saida ?? 0,
    item.outras_despesas_saida ?? 0,
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
