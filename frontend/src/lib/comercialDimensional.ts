import type { ItemPedido, ItemProposta, Produto } from '@/types';

const BASE_UNIDADES = ['PC', 'KG', 'TON', 'M', 'BR', 'CH', 'UN', 'CJ'];

export function unidadesNegociacaoProduto(produto?: Produto | null): string[] {
  if (!produto) return ['PC'];
  const list = (produto.unidades_venda_permitidas_efetivas?.length
    ? produto.unidades_venda_permitidas_efetivas
    : produto.unidades_venda_permitidas) || [];
  const out = Array.from(new Set(list.map((u) => (u || '').toUpperCase()).filter(Boolean)));
  if (out.length) return out;
  const fallback = (
    produto.unidade_venda_efetiva ||
    produto.unidade_venda_padrao ||
    produto.unidade ||
    'PC'
  ).toUpperCase();
  return [fallback];
}

/** Unidades permitidas no pedido de compra (compra → estoque). */
export function unidadesNegociacaoCompraProduto(produto?: Produto | null): string[] {
  if (!produto) return ['PC'];
  const list = (produto.unidades_compra_permitidas?.length ? produto.unidades_compra_permitidas : []) || [];
  const out = Array.from(new Set(list.map((u) => (u || '').toUpperCase()).filter(Boolean)));
  if (out.length) return out;
  const fallback = (
    produto.unidade_compra_efetiva ||
    produto.unidade_compra_padrao ||
    produto.unidade_venda_efetiva ||
    produto.unidade_venda_padrao ||
    produto.unidade ||
    'PC'
  ).toUpperCase();
  return [fallback];
}

export function labelPrecoPorUnidade(unidade?: string): string {
  const u = (unidade || '').trim().toUpperCase();
  if (!u) return 'Preço unitário';
  if (u === 'PC') return 'Preço por PC';
  if (u === 'KG') return 'Preço por KG';
  if (u === 'M') return 'Preço por M';
  if (u === 'BR') return 'Preço por BR';
  if (u === 'TON') return 'Preço por TON';
  if (u === 'CH') return 'Preço por CH';
  if (u === 'UN' || u === 'CJ') return `Preço por ${u}`;
  return 'Preço unitário';
}

/** Label comercial para pedidos (valor unitário negociado). */
export function labelPrecoUnitarioPorUnidade(unidade?: string): string {
  const u = (unidade || '').trim().toUpperCase();
  if (!u) return 'Preço unitário';
  if (u === 'PC') return 'Preço unitário por PC';
  if (u === 'KG') return 'Preço unitário por KG';
  if (u === 'M') return 'Preço unitário por M';
  if (u === 'BR') return 'Preço unitário por BR';
  if (u === 'TON') return 'Preço unitário por TON';
  if (u === 'CH') return 'Preço unitário por CH';
  if (u === 'UN' || u === 'CJ') return `Preço unitário por ${u}`;
  return 'Preço unitário';
}

export function previewConversaoItem(item: Pick<ItemProposta, 'quantidade_negociada' | 'quantidade' | 'unidade_negociada' | 'metros_total' | 'peso_total_kg' | 'barras_total' | 'quantidade_estoque_calculada' | 'unidade_estoque_calculada'>): string {
  const qtd = item.quantidade_negociada ?? item.quantidade ?? 0;
  const un = (item.unidade_negociada || 'UN').toUpperCase();
  const parts = [`${qtd.toFixed(3)} ${un}`];
  if ((item.metros_total ?? 0) > 0) parts.push(`${(item.metros_total ?? 0).toFixed(3)} M`);
  if ((item.peso_total_kg ?? 0) > 0) parts.push(`${(item.peso_total_kg ?? 0).toFixed(3)} KG`);
  if ((item.barras_total ?? 0) > 0) parts.push(`${(item.barras_total ?? 0).toFixed(3)} BR`);
  const estoqueQtd = item.quantidade_estoque_calculada ?? 0;
  const estoqueUn = (item.unidade_estoque_calculada || '').toUpperCase();
  const estoque = estoqueUn ? `Estoque: ${estoqueQtd.toFixed(3)} ${estoqueUn}` : '';
  return estoque ? `${parts.join(' = ')} | ${estoque}` : parts.join(' = ');
}

export function equivalentesPreco(item: Pick<ItemProposta | ItemPedido, 'preco_por_unidade_negociada' | 'preco_por_metro' | 'preco_por_kg' | 'unidade_negociada'>): string[] {
  const rows: string[] = [];
  const base = item.preco_por_unidade_negociada ?? 0;
  const un = (item.unidade_negociada || '').toUpperCase();
  if (base > 0 && un) rows.push(`R$ ${base.toFixed(4)} / ${un}`);
  if ((item.preco_por_metro ?? 0) > 0 && un !== 'M') rows.push(`Equiv.: R$ ${(item.preco_por_metro ?? 0).toFixed(4)} / M`);
  if ((item.preco_por_kg ?? 0) > 0 && un !== 'KG') rows.push(`Equiv.: R$ ${(item.preco_por_kg ?? 0).toFixed(4)} / KG`);
  return rows;
}

export function todasUnidadesPadrao(): string[] {
  return BASE_UNIDADES;
}
