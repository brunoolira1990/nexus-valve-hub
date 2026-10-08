import { describe, expect, it } from 'vitest';
import { formatMoneyBRL } from './numberFields';

const normalizarEspacoMoeda = (valor: string) => valor.replace(/\u00a0/g, ' ');

describe('formatMoneyBRL', () => {
  it('formata valor positivo com centavos no padrão BRL', () => {
    expect(normalizarEspacoMoeda(formatMoneyBRL(1234.56))).toBe('R$ 1.234,56');
  });

  it('formata zero', () => {
    expect(normalizarEspacoMoeda(formatMoneyBRL(0))).toBe('R$ 0,00');
  });

  it('segue a convenção existente para nullish e inválido', () => {
    expect(normalizarEspacoMoeda(formatMoneyBRL(null))).toBe('R$ 0,00');
    expect(normalizarEspacoMoeda(formatMoneyBRL(undefined))).toBe('R$ 0,00');
    expect(normalizarEspacoMoeda(formatMoneyBRL('não numérico'))).toBe('R$ 0,00');
  });

  it('aceita string numérica usada pela API', () => {
    expect(normalizarEspacoMoeda(formatMoneyBRL('1234.56'))).toBe('R$ 1.234,56');
  });

  it('formata valores altos sem perder agrupamento', () => {
    expect(normalizarEspacoMoeda(formatMoneyBRL(1234567.89))).toBe('R$ 1.234.567,89');
  });
});
