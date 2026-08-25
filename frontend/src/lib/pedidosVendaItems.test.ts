import { describe, expect, it } from 'vitest';

import type { ItemPedido } from '@/types';
import {
  buildItemPayload,
  computePedidoFinancialSummary,
  computePedidoTotal,
  normalizeItemPedidoForForm,
} from '@/lib/pedidosVendaItems';

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

  it('calcula subtotal, desconto, frete de cabeçalho e total separadamente', () => {
    const item = { ...itemBase(), desconto_valor: 10, frete_valor: 999 };
    expect(computePedidoFinancialSummary([item], 12.34)).toEqual({
      subtotal: 500,
      desconto: 10,
      frete: 12.34,
      total: 502.34,
    });
    expect(computePedidoTotal([item], 12.34)).toBe(502.34);
  });

  it('payload envia produto_id e nao envia objeto cru', () => {
    const payload = buildItemPayload(itemBase(), 0);
    expect(payload.produto_id).toBe(456);
    expect(payload.quantidade).toBe(2);
    expect(payload.preco_por_unidade_negociada).toBe(250);
    expect('produto' in payload).toBe(false);
    expect(payload).not.toHaveProperty('frete_valor');
  });

  it('payload preserva preco com 3 casas e espelho legado com 2', () => {
    const item = {
      ...itemBase(),
      preco_por_unidade_negociada: 10.125,
      valor_unitario: 10.125,
      quantidade_negociada: 3,
      quantidade: 3,
    };
    const payload = buildItemPayload(item, 0);
    expect(payload.preco_por_unidade_negociada).toBe(10.125);
    expect(payload.valor_unitario).toBe(10.13);
  });

  it('total usa unitario sem arredondar antes', () => {
    const item = {
      ...itemBase(),
      preco_por_unidade_negociada: 10.125,
      quantidade_negociada: 3,
      quantidade: 3,
    };
    expect(computePedidoTotal([item])).toBe(30.38);
  });
});
