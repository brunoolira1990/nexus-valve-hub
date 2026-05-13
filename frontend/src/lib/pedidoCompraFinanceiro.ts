import type { ItemPedido } from '@/types';

export type CalculoFinanceiroItemPedido = {
  valorProdutos: number;
  valorIpi: number;
  valorIcmsSt: number;
  desconto: number;
  frete: number;
  outras: number;
  valorTotalItem: number;
};

function n(v: unknown): number {
  const x = Number(v);
  return Number.isFinite(x) ? x : 0;
}

/** Espelha a lógica do backend (`calcular_financeiro_item_pedido_compra`). */
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

  const desconto = Math.max(0, n(item.desconto_valor));
  const frete = Math.max(0, n(item.frete_valor));
  const outras = Math.max(0, n(item.outras_despesas_valor));

  let valorTotalItem = valorProdutos + valorIpi + valorIcmsSt + frete + outras - desconto;
  if (valorTotalItem < 0) valorTotalItem = 0;
  valorTotalItem = Math.round(valorTotalItem * 100) / 100;

  return { valorProdutos, valorIpi, valorIcmsSt, desconto, frete, outras, valorTotalItem };
}
