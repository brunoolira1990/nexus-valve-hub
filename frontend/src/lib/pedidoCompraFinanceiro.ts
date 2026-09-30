import type { ItemPedido } from '@/types';

/** Helper: converte para numero seguro (0 se null/undefined/NaN). */
const n = (v: unknown): number => {
  if (v == null || v === '') return 0;
  const num = Number(v);
  return Number.isFinite(num) ? num : 0;
};

export type CalculoFinanceiroItemPedido = {
  valorProdutos: number;
  valorIpi: number;
  valorIcmsSt: number;
  desconto: number;
  frete: number;
  outras: number;
  valorTotalItem: number;
};

/** Calcula rateio do desconto de cabecalho proporcionalmente aos itens (nao gravado no banco). */
export function calcularRateioDescontoCabecalhoLocally(
  itens: ItemPedido[],
  descontoCabecalho: number,
  tipo: 'valor' | 'percentual'
): Record<number, number> {
  const itensNaoCancelados = itens.filter((it) => it.status_item !== 'CANCELADO');
  if (!itensNaoCancelados.length) {
    return {};
  }
  // Verifica se algum item tem desconto proprio
  if (itensNaoCancelados.some((it) => (it.desconto_valor ?? 0) > 0)) {
    return {}; // regra um-ou-outro
  }

  // Calcula subtotal dos itens (qtd * preco)
  const subtotal = itensNaoCancelados.reduce(
    (sum, it) => sum + Number((it.quantidade_negociada ?? it.quantidade) * (it.preco_por_unidade_negociada ?? it.valor_unitario ?? 0)),
    0
  );

  let descCabValor: number;
  if (tipo === 'percentual') {
    descCabValor = Math.max(0, Math.min((subtotal * descontoCabecalho) / 100, subtotal));
  } else {
    descCabValor = Math.max(0, Math.min(descontoCabecalho, subtotal));
  }
  if (descCabValor <= 0) {
    return {};
  }

  // Calcula pesos (qtd * preco) de cada item
  const pesos: Record<number, number> = {};
  let totalPeso = 0;
  for (const it of itensNaoCancelados) {
    const peso = Number((it.quantidade_negociada ?? it.quantidade) * (it.preco_por_unidade_negociada ?? it.valor_unitario ?? 0));
    pesos[it.id] = peso;
    totalPeso += peso;
  }
  if (totalPeso <= 0) {
    return {};
  }

  // Distribui o desconto proporcionalmente
  const rateio: Record<number, number> = {};
  let acumulado = 0;
  const itensOrdenados = [...itensNaoCancelados].sort((a, b) => (a.id ?? 0) - (b.id ?? 0));
  for (let idx = 0; idx < itensOrdenados.length; idx++) {
    const it = itensOrdenados[idx];
    let valor: number;
    if (idx === itensOrdenados.length - 1) {
      // ultimo absorve diferenca
      valor = Math.max(0, descCabValor - acumulado);
    } else {
      valor = Math.round((descCabValor * pesos[it.id] / totalPeso) * 100) / 100;
      acumulado += valor;
    }
    rateio[it.id] = valor;
  }
  return rateio;
}

export function calcularFinanceiroItemPedidoCompra(
  item: Pick<
    ItemPedido,
    | 'quantidade_negociada'
    | 'quantidade'
    | 'preco_por_unidade_negociada'
    | 'valor_unitario'
    | 'ipi_percentual'
    | 'ipi_valor'
    | 'icms_st_percentual'
    | 'icms_st_valor'
    | 'desconto_valor'
    | 'desconto_tipo'
    | 'frete_valor'
    | 'outras_despesas_valor'
  >,
): CalculoFinanceiroItemPedido {
  const q = n(item.quantidade_negociada ?? item.quantidade);
  const preco = n(item.preco_por_unidade_negociada ?? item.valor_unitario);
  const valorProdutos = Math.round(q * preco * 100) / 100;

  const ipiPct = n(item.ipi_percentual);
  const ipiValInf = n(item.ipi_valor);
  let valorIpi = 0;
  if (ipiValInf > 0) valorIpi = Math.round(ipiValInf * 100) / 100;
  else if (ipiPct > 0) valorIpi = Math.round(((valorProdutos * ipiPct) / 100) * 100) / 100;

  const stPct = n(item.icms_st_percentual);
  const stValInf = n(item.icms_st_valor);
  let valorIcmsSt = 0;
  if (stValInf > 0) valorIcmsSt = Math.round(stValInf * 100) / 100;
  else if (stPct > 0) valorIcmsSt = Math.round(((valorProdutos * stPct) / 100) * 100) / 100;

  let desconto = n(item.desconto_valor);
  if (item.desconto_tipo === 'percentual') {
    desconto = Math.max(0, Math.round((q * preco * desconto) / 100));
  } else {
    desconto = Math.max(0, desconto);
  }

  const frete = Math.max(0, n(item.frete_valor));
  const outras = Math.max(0, n(item.outras_despesas_valor));

  let valorTotalItem = valorProdutos + valorIpi + valorIcmsSt + frete + outras - desconto;
  if (valorTotalItem < 0) valorTotalItem = 0;
  valorTotalItem = Math.round(valorTotalItem * 100) / 100;

  return { valorProdutos, valorIpi, valorIcmsSt, desconto, frete, outras, valorTotalItem };
}
