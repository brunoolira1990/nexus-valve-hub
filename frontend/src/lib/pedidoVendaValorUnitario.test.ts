import { describe, expect, it } from 'vitest';
import {
  MSG_VALOR_UNITARIO_MAX_3_CASAS,
  countDecimalPlacesInInput,
  espelhoValorUnitarioLegado,
  formatValorUnitarioDisplay,
  parseValorUnitarioInput,
  valorUnitarioExcedeMaxCasas,
} from './pedidoVendaValorUnitario';

describe('pedidoVendaValorUnitario', () => {
  it('parseia vírgula e ponto', () => {
    expect(parseValorUnitarioInput('10,125')).toBe(10.125);
    expect(parseValorUnitarioInput('10.125')).toBe(10.125);
    expect(parseValorUnitarioInput('10,5')).toBe(10.5);
    expect(parseValorUnitarioInput('0,001')).toBe(0.001);
    expect(parseValorUnitarioInput('10')).toBe(10);
  });

  it('detecta quarta casa', () => {
    expect(countDecimalPlacesInInput('10,125')).toBe(3);
    expect(countDecimalPlacesInInput('10.1255')).toBe(4);
    expect(valorUnitarioExcedeMaxCasas('10,1255')).toBe(true);
    expect(valorUnitarioExcedeMaxCasas('10.125')).toBe(false);
    expect(MSG_VALOR_UNITARIO_MAX_3_CASAS).toMatch(/3 casas/);
  });

  it('formata exibição com até 3 casas', () => {
    expect(formatValorUnitarioDisplay(10.125)).toBe('10,125');
    expect(formatValorUnitarioDisplay(10.25)).toBe('10,25');
    expect(formatValorUnitarioDisplay(10)).toBe('10');
  });

  it('espelho legado arredonda em 2 casas sem alterar a fonte', () => {
    expect(espelhoValorUnitarioLegado(10.125)).toBe(10.13);
  });
});
