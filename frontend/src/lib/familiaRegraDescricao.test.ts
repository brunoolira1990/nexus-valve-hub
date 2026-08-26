import { describe, expect, it } from 'vitest';

import {
  DESCRICAO_TOKEN_POLEGADA_PRINCIPAL,
  DESCRICAO_TOKENS_TECNICOS,
  LEGACY_DESCRIPTION_TOKENS,
  ORIENTACAO_DESCRICAO_MANOMETRO,
  orientacaoDescricaoBaseFamilia,
  requisitosMedidasPermitidasModal,
  TIPOS_DIMENSIONAIS_MATERIAL_DIMENSIONAL,
  TIPOS_DIMENSIONAIS_PRODUTO_TECNICO,
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
    expect(orientacaoDescricaoBaseFamilia('MANOMETRO')).toBe(ORIENTACAO_DESCRICAO_MANOMETRO);
    expect(orientacaoDescricaoBaseFamilia('NPS')).toBeNull();
    expect(ORIENTACAO_DESCRICAO_MANOMETRO).toContain('Polegada, rosca e atributos técnicos do manômetro');
    expect(DESCRICAO_TOKENS_TECNICOS).toHaveLength(7);
    expect(DESCRICAO_TOKENS_TECNICOS).toBe(LEGACY_DESCRIPTION_TOKENS);
  });

  it('disponibiliza MANOMETRO apenas para Produto técnico com requisitos corretos', () => {
    expect(TIPOS_DIMENSIONAIS_PRODUTO_TECNICO).toContain('MANOMETRO');
    expect(TIPOS_DIMENSIONAIS_MATERIAL_DIMENSIONAL).not.toContain('MANOMETRO');
    expect(TIPOS_DIMENSIONAIS_PRODUTO_TECNICO).toEqual(
      expect.arrayContaining(['SIMPLES', 'NPS', 'NPS_X_ROSCA', 'VALVULA', 'MANOMETRO']),
    );

    expect(requisitosMedidasPermitidasModal('MANOMETRO', 'BASE_ROSCA_POLEGADA')).toEqual({
      usa_rosca_conexao: true,
      usa_schedule: false,
      usa_polegada_principal: true,
      usa_polegada_secundaria: false,
    });
    expect(sugerirTipoRegraPorDimensional('MANOMETRO')).toBe('BASE_ROSCA_POLEGADA');
  });
});
