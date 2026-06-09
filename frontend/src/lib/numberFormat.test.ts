import { describe, expect, it } from 'vitest';
import { formatDecimal, formatMoneyBr, formatPercent, toNumber } from './numberFormat';

describe('toNumber', () => {
  it('aceita number', () => {
    expect(toNumber(18)).toBe(18);
  });
  it('aceita string com ponto', () => {
    expect(toNumber('18.00')).toBe(18);
  });
  it('aceita string com vírgula', () => {
    expect(toNumber('18,00')).toBe(18);
  });
  it('nullish e inválido', () => {
    expect(toNumber(null)).toBe(0);
    expect(toNumber(undefined)).toBe(0);
    expect(toNumber('')).toBe(0);
    expect(toNumber('abc')).toBe(0);
  });
});

describe('formatPercent', () => {
  it('não quebra com string da API', () => {
    expect(formatPercent('18.00')).toBe('18.00%');
  });
  it('null', () => {
    expect(formatPercent(null)).toBe('0.00%');
  });
});

describe('formatMoneyBr', () => {
  it('formata moeda', () => {
    expect(formatMoneyBr(500)).toBe('R$ 500,00');
  });
});

describe('formatDecimal', () => {
  it('fixed seguro', () => {
    expect(formatDecimal('3.5', 3)).toBe('3.500');
  });
});
