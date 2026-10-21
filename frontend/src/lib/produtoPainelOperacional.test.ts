import { describe, expect, it } from 'vitest';
import {
  painelValorExibicao,
  painelValorMoeda,
  painelValorQuantidade,
} from '@/lib/produtoPainelOperacional';

describe('painelValorMoeda', () => {
  it('formata em pt-BR o preço unitário que vem do backend como string decimal', () => {
    expect(painelValorMoeda('900.00')).toBe('900,00');
    expect(painelValorMoeda('900.0000')).toBe('900,00');
    expect(painelValorMoeda('87.50')).toBe('87,50');
  });

  it('mantém as casas decimais do preço de item de conferência (14,4)', () => {
    expect(painelValorMoeda('1234.5678')).toBe('1.234,5678');
    expect(painelValorMoeda('78.0613')).toBe('78,0613');
  });

  it('usa separador de milhar no total da linha', () => {
    expect(painelValorMoeda('7200.00')).toBe('7.200,00');
    expect(painelValorMoeda(7200)).toBe('7.200,00');
  });

  it('devolve traço para preço inexistente', () => {
    expect(painelValorMoeda(null)).toBe('—');
    expect(painelValorMoeda(undefined)).toBe('—');
    expect(painelValorMoeda('')).toBe('—');
  });

  it('não converte em moeda o que não é número', () => {
    expect(painelValorMoeda('NF-e não conferida')).toBe('NF-e não conferida');
  });

  it('painelValorExibicao preserva o número cru do documento', () => {
    expect(painelValorExibicao('15395')).toBe('15395');
  });
});

describe('painelValorQuantidade', () => {
  it('remove as casas vazias da quantidade que vem da NF-e', () => {
    expect(painelValorQuantidade('8.000')).toBe('8');
    expect(painelValorQuantidade('3.500')).toBe('3,5');
  });

  it('preserva até 3 casas decimais e separa milhar', () => {
    expect(painelValorQuantidade('26.847')).toBe('26,847');
    expect(painelValorQuantidade('1500.000')).toBe('1.500');
    expect(painelValorQuantidade(12.5)).toBe('12,5');
  });

  it('devolve traço para quantidade ausente e não mexe em texto', () => {
    expect(painelValorQuantidade(null)).toBe('—');
    expect(painelValorQuantidade(undefined)).toBe('—');
    expect(painelValorQuantidade('')).toBe('—');
    expect(painelValorQuantidade('sem saldo')).toBe('sem saldo');
  });
});
