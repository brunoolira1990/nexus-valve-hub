import { describe, expect, it } from 'vitest';

import {
  DESCRICAO_TOKEN_POLEGADA_PRINCIPAL,
  DESCRICAO_TOKENS_TECNICOS,
  LEGACY_DESCRIPTION_TOKENS,
  ORIENTACAO_DESCRICAO_MANOMETRO,
  deveExibirTokensDescricaoFamilia,
  tokensDescricaoTecnicaConfigurados,
  sugerirTipoRegraPorDimensional,
  tipoMedidaPrincipalPorDimensional,
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

  it('mapeia MANOMETRO para a regra de código compatível e medida NPS', () => {
    expect(sugerirTipoRegraPorDimensional('MANOMETRO')).toBe('BASE_ROSCA_POLEGADA');
    expect(tipoMedidaPrincipalPorDimensional('MANOMETRO')).toBe('NPS');
  });

  it('separa a orientação estrutural dos tokens mantidos para legado', () => {
    expect(deveExibirTokensDescricaoFamilia('MANOMETRO')).toBe(false);
    expect(deveExibirTokensDescricaoFamilia('NPS')).toBe(true);
    expect(ORIENTACAO_DESCRICAO_MANOMETRO).toContain('Polegada, rosca e atributos técnicos');
    expect(DESCRICAO_TOKENS_TECNICOS).toHaveLength(7);
    expect(DESCRICAO_TOKENS_TECNICOS).toBe(LEGACY_DESCRIPTION_TOKENS);
  });
});
