import { describe, expect, it } from 'vitest';
import {
  itemPendenteProdutoParaRegularizar,
} from '@/components/comercial/GerarPedidoPropostaModal';
import { itemPodeSelecionarParaPedido } from '@/lib/propostaStatus';
import type { ItemProposta } from '@/types';

function item(partial: Partial<ItemProposta>): ItemProposta {
  return partial as ItemProposta;
}

describe('GerarPedidoPropostaModal — itens pendentes', () => {
  it('identifica item avulso pendente de produto para regularização', () => {
    expect(
      itemPendenteProdutoParaRegularizar(
        item({ produto_id: null, status_comercial: 'PENDENTE' }),
      ),
    ).toBe(true);
  });

  it('não marca item já vinculado como pendente', () => {
    expect(
      itemPendenteProdutoParaRegularizar(
        item({ produto_id: 10, status_comercial: 'PENDENTE' }),
      ),
    ).toBe(false);
  });

  it('item pendente não pode ser selecionado; vinculado pode', () => {
    const pendente = item({ produto_id: null, status_comercial: 'PENDENTE', pode_selecionar_para_pedido: true });
    const vinculado = item({ produto_id: 10, status_comercial: 'PENDENTE', pode_selecionar_para_pedido: true });
    expect(itemPendenteProdutoParaRegularizar(pendente)).toBe(true);
    expect(itemPodeSelecionarParaPedido(pendente)).toBe(false);
    expect(itemPodeSelecionarParaPedido(vinculado)).toBe(true);
  });
});
