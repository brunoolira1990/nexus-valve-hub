import { describe, expect, it } from 'vitest';

import { DESCRICAO_TOKEN_POLEGADA_PRINCIPAL } from '@/lib/familiaRegra';

describe('descrição posicionável de Família/Figura', () => {
  it('expõe o token real da Polegada principal', () => {
    expect(DESCRICAO_TOKEN_POLEGADA_PRINCIPAL).toBe('[P]');
  });
});
