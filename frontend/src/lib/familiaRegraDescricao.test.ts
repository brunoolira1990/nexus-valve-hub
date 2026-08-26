import { describe, expect, it } from 'vitest';

import {
  DESCRICAO_TOKEN_POLEGADA_PRINCIPAL,
  DESCRICAO_TOKENS_TECNICOS,
  tokensDescricaoTecnicaConfigurados,
} from '@/lib/familiaRegra';

describe('descrição posicionável de Família/Figura', () => {
  it('expõe o token real da Polegada principal', () => {
    expect(DESCRICAO_TOKEN_POLEGADA_PRINCIPAL).toBe('[P]');
  });

  it('expõe somente o conjunto fechado de tokens técnicos', () => {
    expect(DESCRICAO_TOKENS_TECNICOS.map(({ token }) => token)).toEqual([
      '[ESCALA]',
      '[UNIDADE]',
      '[PONTEIRO]',
      '[VIDRO]',
      '[CLASSE]',
      '[FLUIDO]',
      '[CERTIFICACAO]',
    ]);
  });

  it('detecta apenas os tokens configurados na descrição da Figura', () => {
    expect(
      tokensDescricaoTecnicaConfigurados('MANOMETRO [P] ESCALA [ESCALA] [UNIDADE]'),
    ).toEqual([
      expect.objectContaining({ token: '[ESCALA]', key: 'escala' }),
      expect.objectContaining({ token: '[UNIDADE]', key: 'unidade_escala' }),
    ]);
  });
});
