import { describe, expect, it } from 'vitest';

import type { ItemPedido } from '@/types';
import { buildItemPayload, computePedidoTotal, normalizeItemPedidoForForm } from '@/lib/pedidosVendaItems';

function itemBase(): ItemPedido {
  return {
    id: 10,
    produto_id: 456,
    produto_nome: 'FLANGE SW ACO CARBONO ANSI 150# RF SCH 160 1.1/2"',
    quantidade: 2,
    quantidade_negociada: 2,
    unidade_negociada: 'pc',
    valor_unitario: 250,
    preco_por_unidade_negociada: 250,
    desconto_valor: 0,
  };
}

describe('pedidosVendaItems', () => {
  it('normaliza item e preserva produto preenchido', () => {
    const item = normalizeItemPedidoForForm(itemBase());
    expect(item.produto_id).toBe(456);
    expect(item.produto_nome).toContain('FLANGE');
    expect(item.quantidade_negociada).toBe(2);
    expect(item.preco_por_unidade_negociada).toBe(250);
  });

  it('calcula total 2x250 = 500', () => {
    expect(computePedidoTotal([itemBase()])).toBe(500);
  });

  it('payload envia produto_id e nao envia objeto cru', () => {
    const payload = buildItemPayload(itemBase(), 0);
    expect(payload.produto_id).toBe(456);
    expect(payload.quantidade).toBe(2);
    expect(payload.preco_por_unidade_negociada).toBe(250);
    expect('produto' in payload).toBe(false);
  });

  it('falha com mensagem amigavel quando item sem produto', () => {
    const semProduto = { ...itemBase(), produto_id: 0 };
    expect(() => buildItemPayload(semProduto, 0)).toThrow(/item 1 está sem produto/i);
  });
});
