import { describe, expect, it } from 'vitest';
import {
  AVISO_COMPOSICAO_SEM_ESTOQUE,
  AVISO_EQUIVALENCIA_SEM_ESTOQUE,
  badgeConfiancaEquivalencia,
  exigeMotivoDivergencia,
  labelTipoComposicao,
  labelTipoEquivalencia,
} from './conferenciaEquivalencia';

describe('conferenciaEquivalencia', () => {
  it('badgeConfiancaEquivalencia', () => {
    expect(badgeConfiancaEquivalencia('alta').className).toContain('success');
    expect(badgeConfiancaEquivalencia('media').className).toContain('warning');
    expect(badgeConfiancaEquivalencia('baixa').className).toContain('danger');
  });

  it('labelTipoEquivalencia e composicao', () => {
    expect(labelTipoEquivalencia('equivalencia_composta')).toBe('Itens do fornecedor agrupados');
    expect(labelTipoComposicao('MONTAGEM_ROSCADA')).toContain('roscada');
    expect(labelTipoComposicao('MONTAGEM_SIMPLES')).toContain('simples');
    expect(labelTipoComposicao('MONTAGEM_SOLDADA')).toContain('soldada');
  });

  it('exigeMotivoDivergencia', () => {
    expect(
      exigeMotivoDivergencia({
        tipo: 'x',
        confianca: 1,
        nivel_confianca: 'alta',
        produto_interno_id: 1,
        dentro_tolerancia: true,
      }),
    ).toBe(false);
    expect(
      exigeMotivoDivergencia({
        tipo: 'x',
        confianca: 1,
        nivel_confianca: 'alta',
        produto_interno_id: 1,
        diferenca_valor: '1.00',
      }),
    ).toBe(true);
  });

  it('avisos de nao movimentar estoque', () => {
    expect(AVISO_EQUIVALENCIA_SEM_ESTOQUE).toContain('estoque');
    expect(AVISO_COMPOSICAO_SEM_ESTOQUE).toContain('estoque');
  });
});
