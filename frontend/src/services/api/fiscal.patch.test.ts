import { describe, expect, it } from 'vitest';

import { stripNfItens } from './fiscal';

describe('stripNfItens PATCH', () => {
  it('mantém id ao atualizar NF-e', () => {
    const out = stripNfItens(
      [
        {
          id: 42,
          produto_id: 1,
          produto_nome: 'Válvula',
          quantidade: 2,
          valor: 100,
          corrida_numero: 'C-1',
          observacao_item: 'Obs',
        },
      ],
      { keepId: true },
    );
    expect(out[0]).toMatchObject({ id: 42, observacao_item: 'Obs', produto_id: 1 });
    expect(out[0]).not.toHaveProperty('produto_nome');
    expect(out[0]).not.toHaveProperty('corrida_numero');
  });

  it('remove id em create', () => {
    const out = stripNfItens([
      { id: 99, produto_id: 1, produto_nome: 'X', quantidade: 1, valor: 10 },
    ]);
    expect(out[0]).not.toHaveProperty('id');
  });
});
