import { toNumber } from '@/lib/numberFormat';
import type { ItemProposta } from '@/types';

/** Campos aceitos pelo ItemPropostaSerializer no write (exclui read_only / UI). */
const WRITABLE_ITEM_KEYS = [
  'produto_id',
  'quantidade',
  'unidade_negociada',
  'quantidade_negociada',
  'unidade_estoque_calculada',
  'quantidade_estoque_calculada',
  'peso_total_kg',
  'metros_total',
  'barras_total',
  'valor_unitario',
  'preco_por_unidade_negociada',
  'preco_por_kg',
  'preco_por_metro',
  'fator_conversao',
  'desconto',
  'custo_utilizado',
  'frete',
  'despesas',
  'ipi_entrada_percentual',
  'ipi_custo',
  'st_custo',
  'outros_impostos_custo',
  'custo_final',
  'icms_saida_percentual',
  'pis_saida_percentual',
  'cofins_saida_percentual',
  'ipi_saida_percentual',
  'regra_fiscal_id',
  'irpj_estimado_percentual',
  'csll_estimada_percentual',
  'comissao_percentual',
  'frete_saida',
  'outras_despesas_saida',
  'modo_preco',
  'preco_sugerido',
  'preco_final',
  'margem_resultante',
  'lucro_resultante',
  'descricao_avulsa',
  'ncm_avulso',
  'snapshot_produto',
] as const;

const ITEM_NUMERIC_KEYS = new Set<string>([
  'quantidade',
  'quantidade_negociada',
  'quantidade_estoque_calculada',
  'peso_total_kg',
  'metros_total',
  'barras_total',
  'valor_unitario',
  'preco_por_unidade_negociada',
  'preco_por_kg',
  'preco_por_metro',
  'fator_conversao',
  'desconto',
  'custo_utilizado',
  'frete',
  'despesas',
  'ipi_entrada_percentual',
  'ipi_custo',
  'st_custo',
  'outros_impostos_custo',
  'custo_final',
  'icms_saida_percentual',
  'pis_saida_percentual',
  'cofins_saida_percentual',
  'ipi_saida_percentual',
  'irpj_estimado_percentual',
  'csll_estimada_percentual',
  'comissao_percentual',
  'frete_saida',
  'outras_despesas_saida',
  'preco_sugerido',
  'preco_final',
  'margem_resultante',
  'lucro_resultante',
]);

const PROPOSTA_READONLY_KEYS = new Set([
  'cliente_nome',
  'empresa_emitente_nome',
  'cenario_fiscal_saida_nome',
  'origem_fiscal_resumo',
  'pedido_venda_id',
  'pedido_venda_numero',
  'pode_converter_em_pedido',
  'pode_gerar_pedido',
  'requer_recuperacao',
  'pedidos_gerados_resumo',
  'itens_pendentes_conversao',
  'vendedor_nome',
  'uf_origem',
  'operacao_fiscal',
]);

export function inferItemAvulso(item: Partial<ItemProposta>): boolean {
  if (item.item_avulso === true) return true;
  if (item.item_avulso === false) return false;
  if (item.produto_id) return false;
  return Boolean((item.descricao_avulsa || '').trim() || (item.ncm_avulso || '').trim());
}

/** Payload de item para POST/PATCH — só campos writable e números finitos. */
export function sanitizeItemPropostaForApi(item: ItemProposta): Record<string, unknown> {
  const avulso = inferItemAvulso(item);
  const out: Record<string, unknown> = {};

  for (const key of WRITABLE_ITEM_KEYS) {
    if (!(key in item)) continue;
    let value: unknown = item[key as keyof ItemProposta];
    if (ITEM_NUMERIC_KEYS.has(key)) {
      value = toNumber(value);
    }
    if (key === 'produto_id' && avulso) {
      value = null;
    }
    if (key === 'descricao_avulsa' && !avulso) {
      value = '';
    }
    if (key === 'ncm_avulso' && !avulso) {
      value = '';
    }
    out[key] = value;
  }

  return out;
}

/** Remove campos read_only da proposta antes do envio à API. */
export function sanitizePropostaRestForApi(data: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (key === 'itens' || PROPOSTA_READONLY_KEYS.has(key)) continue;
    out[key] = value;
  }
  return out;
}

export function stripPropostaItensForApi(itens: ItemProposta[]): Record<string, unknown>[] {
  return itens.map(sanitizeItemPropostaForApi);
}
