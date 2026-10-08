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
  const list = (
    produto.unidades_compra_permitidas_efetivas?.length
      ? produto.unidades_compra_permitidas_efetivas
      : produto.unidades_compra_permitidas?.length
        ? produto.unidades_compra_permitidas
        : []
  ) || [];
  let out = Array.from(new Set(list.map((u) => (u || '').toUpperCase()).filter(Boolean)));
  if (!out.length) {
    const fallback = (
      produto.unidade_compra_efetiva ||
      produto.unidade_compra_padrao ||
      produto.unidade_estoque_efetiva ||
      produto.unidade_estoque ||
      produto.unidade_venda_efetiva ||
      produto.unidade_venda_padrao ||
      produto.unidade ||
      'PC'
    ).toUpperCase();
    out = [fallback];
  }

  // Tubo/barra dimensional: permitir negociar em metro mesmo se o cadastro só listou BR.
  const usaConv = Boolean(produto.usa_conversao_dimensional_efetivo || produto.usa_conversao_dimensional);
  const tipoComp = (produto.tipo_composicao_fisica_efetivo || 'BARRA_M').toUpperCase();
  if (usaConv && tipoComp === 'BARRA_M') {
    out = Array.from(new Set([...out, 'M', 'BR']));
    if (Number(produto.peso_por_metro_kg_efetivo || produto.peso_por_metro_kg || 0) > 0) {
      out = Array.from(new Set([...out, 'KG']));
    }
  }

  const preferida = (
    produto.unidade_compra_efetiva ||
    produto.unidade_compra_padrao ||
    produto.unidade_estoque_efetiva ||
    ''
  ).toUpperCase();
  if (preferida && out.includes(preferida)) {
    return [preferida, ...out.filter((u) => u !== preferida)];
  }
  // Em barra dimensional, M primeiro facilita compra por metro.
  if (usaConv && tipoComp === 'BARRA_M' && out.includes('M')) {
    return ['M', ...out.filter((u) => u !== 'M')];
  }
  return out;
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

function numComercial(v: unknown, fallback = 0): number {
  const n = Number(v ?? fallback);
  return Number.isFinite(n) ? n : fallback;
}

export function previewConversaoItem(item: Pick<ItemProposta, 'quantidade_negociada' | 'quantidade' | 'unidade_negociada' | 'metros_total' | 'peso_total_kg' | 'barras_total' | 'quantidade_estoque_calculada' | 'unidade_estoque_calculada'>): string {
  const qtd = numComercial(item.quantidade_negociada ?? item.quantidade);
  const un = (item.unidade_negociada || 'UN').toUpperCase();
  const parts = [`${qtd.toFixed(3)} ${un}`];
  const metros = numComercial(item.metros_total);
  const peso = numComercial(item.peso_total_kg);
  const barras = numComercial(item.barras_total);
  if (metros > 0) parts.push(`${metros.toFixed(3)} M`);
  if (peso > 0) parts.push(`${peso.toFixed(3)} KG`);
  if (barras > 0) parts.push(`${barras.toFixed(3)} BR`);
  const estoqueQtd = numComercial(item.quantidade_estoque_calculada);
  const estoqueUn = (item.unidade_estoque_calculada || '').toUpperCase();
  const estoque = estoqueUn ? `Estoque: ${estoqueQtd.toFixed(3)} ${estoqueUn}` : '';
  return estoque ? `${parts.join(' = ')} | ${estoque}` : parts.join(' = ');
}

export function equivalentesPreco(
  item: Pick<ItemProposta | ItemPedido, 'preco_por_unidade_negociada' | 'valor_unitario' | 'preco_por_metro' | 'preco_por_kg' | 'unidade_negociada'>,
): string[] {
  const rows: string[] = [];
  const base = Number(item.preco_por_unidade_negociada ?? item.valor_unitario ?? 0);
  const un = (item.unidade_negociada || '').toUpperCase();
  const pm = Number(item.preco_por_metro ?? 0);
  const pkg = Number(item.preco_por_kg ?? 0);
  if (Number.isFinite(base) && base > 0 && un) rows.push(`R$ ${base.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} / ${un}`);
  if (Number.isFinite(pm) && pm > 0 && un !== 'M') rows.push(`Equiv.: R$ ${pm.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} / M`);
  if (Number.isFinite(pkg) && pkg > 0 && un !== 'KG') rows.push(`Equiv.: R$ ${pkg.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} / KG`);
  return rows;
}

export function todasUnidadesPadrao(): string[] {
  return BASE_UNIDADES;
}
