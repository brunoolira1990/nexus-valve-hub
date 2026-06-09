import type { ItemPedido } from '@/types';

function toNumber(value: unknown, fallback = 0): number {
  const n = Number(value ?? fallback);
  return Number.isFinite(n) ? n : fallback;
}

export function normalizeItemPedidoForForm(it: ItemPedido): ItemPedido {
  const produtoNomeFallback =
    it.produto_nome ||
    ((it.snapshot_produto as { descricao?: string } | undefined)?.descricao ?? '') ||
    '';
  return {
    ...it,
    produto_nome: produtoNomeFallback,
    quantidade_negociada: toNumber(it.quantidade_negociada ?? it.quantidade, 0),
    preco_por_unidade_negociada: toNumber(it.preco_por_unidade_negociada ?? it.valor_unitario, 0),
    quantidade: toNumber(it.quantidade, 0),
    valor_unitario: toNumber(it.valor_unitario, 0),
    desconto_valor: toNumber((it as ItemPedido & { desconto?: number }).desconto ?? it.desconto_valor, 0),
    quantidade_faturada: toNumber(it.quantidade_faturada, 0),
  };
}

export function computePedidoTotal(itens: ItemPedido[]): number {
  return itens.reduce((s, i) => {
    const qtd = toNumber(i.quantidade_negociada ?? i.quantidade, 0);
    const pu = toNumber(i.preco_por_unidade_negociada ?? i.valor_unitario, 0);
    const desconto = toNumber((i as ItemPedido & { desconto?: number }).desconto ?? i.desconto_valor, 0);
    const ipi = toNumber(i.ipi_valor, 0);
    const st = toNumber(i.icms_st_valor, 0);
    const frete = toNumber(i.frete_valor, 0);
    const outras = toNumber(i.outras_despesas_valor, 0);
    return s + Math.max(0, qtd * pu - desconto + ipi + st + frete + outras);
  }, 0);
}

export function buildItemPayload(it: ItemPedido, idx: number): Record<string, unknown> {
  const rawId = it.id;
  const id = typeof rawId === 'number' && rawId > 0 && rawId < 1_000_000_000 ? rawId : undefined;
  const produtoId = toNumber(it.produto_id, 0);
  if (!produtoId) throw new Error(`Item ${idx + 1} está sem produto.`);
  const quantidade = toNumber(it.quantidade_negociada ?? it.quantidade, 0);
  if (quantidade <= 0) throw new Error(`Quantidade do item ${idx + 1} deve ser maior que zero.`);
  const precoUnitario = toNumber(it.preco_por_unidade_negociada ?? it.valor_unitario, 0);
  if (precoUnitario < 0) throw new Error(`Preço do item ${idx + 1} não pode ser negativo.`);
  const desconto = toNumber((it as ItemPedido & { desconto?: number }).desconto ?? it.desconto_valor, 0);
  return {
    ...(id ? { id } : {}),
    produto_id: produtoId,
    quantidade,
    quantidade_negociada: quantidade,
    valor_unitario: precoUnitario,
    preco_por_unidade_negociada: precoUnitario,
    desconto,
    unidade_negociada: (it.unidade_negociada || 'PC').toUpperCase(),
    ipi_valor: toNumber(it.ipi_valor, 0),
    icms_st_valor: toNumber(it.icms_st_valor, 0),
    frete_valor: toNumber(it.frete_valor, 0),
    outras_despesas_valor: toNumber(it.outras_despesas_valor, 0),
  };
}
