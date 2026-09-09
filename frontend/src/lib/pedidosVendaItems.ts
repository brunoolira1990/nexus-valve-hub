import type { ItemPedido } from '@/types';
import { espelhoValorUnitarioLegado } from '@/lib/pedidoVendaValorUnitario';

function toNumber(value: unknown, fallback = 0): number {
  const n = Number(value ?? fallback);
  return Number.isFinite(n) ? n : fallback;
}

export function normalizeItemPedidoForForm(it: ItemPedido): ItemPedido {
  const produtoNomeFallback =
    it.produto_nome ||
    ((it.snapshot_produto as { descricao?: string } | undefined)?.descricao ?? '') ||
    '';
  const preco = toNumber(it.preco_por_unidade_negociada ?? it.valor_unitario, 0);
  return {
    ...it,
    produto_nome: produtoNomeFallback,
    quantidade_negociada: toNumber(it.quantidade_negociada ?? it.quantidade, 0),
    preco_por_unidade_negociada: preco,
    quantidade: toNumber(it.quantidade, 0),
    // Fonte comercial = preco; legado só espelho de 2 casas.
    valor_unitario: toNumber(it.valor_unitario, espelhoValorUnitarioLegado(preco)),
    desconto_valor: toNumber((it as ItemPedido & { desconto?: number }).desconto ?? it.desconto_valor, 0),
    quantidade_faturada: toNumber(it.quantidade_faturada, 0),
  };
}

function computePedidoTotalRaw(itens: ItemPedido[], valorFrete = 0): number {
  return itens.reduce((s, i) => {
    const qtd = toNumber(i.quantidade_negociada ?? i.quantidade, 0);
    const pu = toNumber(i.preco_por_unidade_negociada ?? i.valor_unitario, 0);
    const desconto = toNumber((i as ItemPedido & { desconto?: number }).desconto ?? i.desconto_valor, 0);
    // Sem arredondar o unitário antes do produto; total da UI é informativo.
    return s + qtd * pu - desconto;
  }, toNumber(valorFrete, 0));
}

export function computePedidoFinancialSummary(itens: ItemPedido[], valorFrete = 0) {
  const subtotal = itens.reduce(
    (s, i) => s + toNumber(i.quantidade_negociada ?? i.quantidade, 0) * toNumber(i.preco_por_unidade_negociada ?? i.valor_unitario, 0),
    0,
  );
  const desconto = itens.reduce(
    (s, i) => s + toNumber((i as ItemPedido & { desconto?: number }).desconto ?? i.desconto_valor, 0),
    0,
  );
  const frete = toNumber(valorFrete, 0);
  const totalRaw = computePedidoTotalRaw(itens, valorFrete);
  const total = Math.round((totalRaw + Number.EPSILON) * 100) / 100;
  return { subtotal, desconto, frete, total };
}

export function computePedidoTotal(itens: ItemPedido[], valorFrete = 0): number {
  return computePedidoFinancialSummary(itens, valorFrete).total;
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
    // Precisão comercial em preco_*; legado só com 2 casas (numeric(14,2) / DRF).
    preco_por_unidade_negociada: precoUnitario,
    valor_unitario: espelhoValorUnitarioLegado(precoUnitario),
    desconto,
    unidade_negociada: (it.unidade_negociada || 'PC').toUpperCase(),
    ipi_valor: toNumber(it.ipi_valor, 0),
    icms_st_valor: toNumber(it.icms_st_valor, 0),
    outras_despesas_valor: toNumber(it.outras_despesas_valor, 0),
  };
}
