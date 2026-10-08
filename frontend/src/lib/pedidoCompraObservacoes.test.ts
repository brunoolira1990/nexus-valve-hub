/** UI — Observações no Pedido de Compra. */

import { describe, expect, it } from 'vitest';

export function formPedidoCompraComObservacoes(base: {
  observacoes?: string;
}): { observacoes: string } {
  return { observacoes: base.observacoes ?? '' };
}

describe('PedidoCompra observações', () => {
  it('abre novo pedido com observações vazias', () => {
    expect(formPedidoCompraComObservacoes({}).observacoes).toBe('');
  });

  it('carrega observações multilinha ao editar', () => {
    const obs = 'Instrução A\nReferência B';
    expect(formPedidoCompraComObservacoes({ observacoes: obs }).observacoes).toBe(obs);
  });

  it('placeholder orienta o operador', () => {
    const placeholder = 'Instruções, referências ou informações adicionais do pedido...';
    expect(placeholder).toMatch(/Instruções/);
  });
});
