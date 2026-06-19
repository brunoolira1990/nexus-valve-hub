import { describe, expect, it } from 'vitest';
import { itemPodeSelecionarParaPedido } from '@/lib/propostaStatus';
import type { ItemProposta } from '@/types';

function item(partial: Partial<ItemProposta>): ItemProposta {
  return partial as ItemProposta;
}

describe('itemPodeSelecionarParaPedido', () => {
  it('permite item pendente com produto vinculado', () => {
    expect(
      itemPodeSelecionarParaPedido(
        item({ produto_id: 10, status_comercial: 'PENDENTE', pode_selecionar_para_pedido: true }),
      ),
    ).toBe(true);
  });

  it('bloqueia item pendente sem produto', () => {
    expect(
      itemPodeSelecionarParaPedido(
        item({ produto_id: null, status_comercial: 'PENDENTE', pode_selecionar_para_pedido: true }),
      ),
    ).toBe(false);
  });

  it('bloqueia item convertido, cancelado, perdido ou mantido', () => {
    for (const status of ['CONVERTIDO_EM_PEDIDO', 'CANCELADO', 'PERDIDO', 'MANTIDO_PARA_DEPOIS'] as const) {
      expect(
        itemPodeSelecionarParaPedido(
          item({ produto_id: 10, status_comercial: status, pode_selecionar_para_pedido: true }),
        ),
      ).toBe(false);
    }
  });

  it('respeita pode_selecionar_para_pedido=false do backend', () => {
    expect(
      itemPodeSelecionarParaPedido(
        item({ produto_id: 10, status_comercial: 'PENDENTE', pode_selecionar_para_pedido: false }),
      ),
    ).toBe(false);
  });
});
