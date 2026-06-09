import { describe, expect, it } from 'vitest';
import {
  formatCurrencyBRL,
  formatProdutoComercialLinha,
  formatQuantidadeBR,
} from '@/lib/formatBr';

describe('formatBr', () => {
  it('formatCurrencyBRL usa pt-BR', () => {
    expect(formatCurrencyBRL(5000)).toBe('R$\u00a05.000,00');
    expect(formatCurrencyBRL(5000)).not.toBe('R$ 5000.00');
  });

  it('formatQuantidadeBR inteiro sem casas', () => {
    expect(formatQuantidadeBR(10, 'PC')).toBe('10 PC');
    expect(formatQuantidadeBR(10.0, 'PC')).toBe('10 PC');
  });

  it('formatQuantidadeBR decimal com vírgula', () => {
    expect(formatQuantidadeBR(10.5, 'KG')).toContain(',');
    expect(formatQuantidadeBR(10.5, 'KG')).toContain('KG');
  });

  it('produto código + descrição', () => {
    const { linha, tituloCompleto } = formatProdutoComercialLinha(
      '018840.06',
      'CURVA 90 RL AÇO CARBONO SCH 40 1"',
    );
    expect(linha).toContain('018840.06');
    expect(linha).toContain('CURVA');
    expect(tituloCompleto).toContain('—');
  });
});
