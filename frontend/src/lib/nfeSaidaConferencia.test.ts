import { describe, expect, it } from 'vitest';
import {
  badgeStatusConferencia,
  fmtMoeda,
  fmtNum,
  labelOrigemNfe,
  GRUPO_VALIDACAO_LABELS,
} from './nfeSaidaConferencia';

describe('nfeSaidaConferencia', () => {
  it('badgeStatusConferencia mapeia status', () => {
    expect(badgeStatusConferencia('OK').label).toBe('OK');
    expect(badgeStatusConferencia('ATENCAO').label).toBe('Atenção');
    expect(badgeStatusConferencia('PENDENTE').className).toContain('danger');
    expect(badgeStatusConferencia('NAO_CONFIGURADA').label).toBe('Não configurada');
  });

  it('fmtMoeda e fmtNum formatam pt-BR', () => {
    expect(fmtMoeda('1234.5')).toMatch(/R\$\s*1\.234,50/);
    expect(fmtNum('10.5', 2)).toBe('10,50');
    expect(fmtMoeda(null)).toMatch(/R\$\s*0,00/);
    expect(fmtNum(undefined)).toBe('0,000');
  });

  it('labelOrigemNfe', () => {
    expect(labelOrigemNfe('FATURAMENTO')).toBe('Faturamento');
    expect(labelOrigemNfe('PEDIDO')).toBe('Pedido de venda');
    expect(labelOrigemNfe('')).toBe('Manual');
  });

  it('GRUPO_VALIDACAO_LABELS inclui reforma', () => {
    expect(GRUPO_VALIDACAO_LABELS.reforma_tributaria).toBe('Reforma Tributária');
  });
});
