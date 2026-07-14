import { describe, expect, it } from 'vitest';

import { montarItensComplementaresConferencia } from './nfeSaidaConferenciaSave';

describe('montarItensComplementaresConferencia', () => {
  it('remove item sem id em origem travada', () => {
    const out = montarItensComplementaresConferencia(
      [{ item_id: null, pedido_cliente_item: 'x' }, { item_id: 5, pedido_cliente_item: '10' }],
      true,
    );
    expect(out).toEqual([
      {
        id: 5,
        pedido_cliente_numero: '',
        pedido_cliente_item: '10',
        observacao_item: '',
        informacao_adicional_item: '',
      },
    ]);
  });

  it('aceita id alternativo no objeto do item', () => {
    const out = montarItensComplementaresConferencia([{ id: 7, pedido_cliente_item: 'A' } as never], true);
    expect(out?.[0]?.id).toBe(7);
  });

  it('retorna undefined quando origem travada e nenhum id válido', () => {
    expect(montarItensComplementaresConferencia([{ item_id: undefined }], true)).toBeUndefined();
  });

  it('envia apenas complementares com id', () => {
    const out = montarItensComplementaresConferencia(
      [{ item_id: 12, observacao_item: 'Obs item', pedido_cliente_numero_editavel: 'PC-1' }],
      true,
    );
    expect(out?.[0]).toMatchObject({ id: 12, observacao_item: 'Obs item', pedido_cliente_numero: 'PC-1' });
    expect(out?.[0]).not.toHaveProperty('produto_id');
  });

  it('ignora produto/quantidade/valor mesmo se vierem no objeto do item', () => {
    const out = montarItensComplementaresConferencia(
      [
        {
          item_id: 9,
          pedido_cliente_item: '01',
          produto_id: 99,
          quantidade: '4',
          valor: '1128.1250',
        } as never,
      ],
      true,
    );
    expect(out).toHaveLength(1);
    expect(out?.[0]).toEqual({
      id: 9,
      pedido_cliente_numero: '',
      pedido_cliente_item: '01',
      observacao_item: '',
      informacao_adicional_item: '',
    });
    expect(out?.[0]).not.toHaveProperty('valor');
    expect(out?.[0]).not.toHaveProperty('quantidade');
    expect(out?.[0]).not.toHaveProperty('produto_id');
  });
});
