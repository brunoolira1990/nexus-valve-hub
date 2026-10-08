import { describe, expect, it } from 'vitest';

import {
  badgeStatusBaseReforma,
  labelFonteRegraBase,
  linhasReformaItemExibicao,
  mensagemBaseReforma,
} from '@/lib/nfeSaidaReformaExibicao';

describe('nfeSaidaReformaExibicao base IBS/CBS 4013611', () => {
  it('exibe base cheia R$ 12.500,00', () => {
    const linhas = linhasReformaItemExibicao({
      base_original_reforma: '12500',
      base_ibs_cbs: '12500',
      modo_base_ibs_cbs: 'BASE_CHEIA_OPERACAO',
      formula_base_ibs_cbs: 'vProd',
      valor_cbs: '112.50',
      valor_ibs_estadual: '12.50',
      aliquota_cbs: '0.9',
      aliquota_ibs_estadual: '0.1',
    });
    expect(linhas.some((l) => l.includes('12.500,00'))).toBe(true);
    expect(linhas.some((l) => l.includes('Fórmula: vProd'))).toBe(true);
  });

  it('exibe deduções e base sem ICMS/PIS/COFINS', () => {
    const linhas = linhasReformaItemExibicao({
      base_original_reforma: '12500',
      base_ibs_cbs: '11200.69',
      valor_deduzido_icms: '875',
      valor_deduzido_pis: '75.56',
      valor_deduzido_cofins: '348.75',
      formula_base_ibs_cbs: 'vProd - vICMS - vPIS - vCOFINS',
      valor_cbs: '100.81',
      valor_ibs_estadual: '11.20',
      aliquota_cbs: '0.9',
      aliquota_ibs_estadual: '0.1',
      valor_total_ibs_cbs: '112.01',
    });
    expect(linhas.some((l) => l.includes('Dedução ICMS'))).toBe(true);
    expect(linhas.some((l) => l.includes('11.200,69'))).toBe(true);
    expect(linhas.some((l) => l.includes('100,81'))).toBe(true);
  });

  it('badge pendente e mensagem base cheia', () => {
    expect(badgeStatusBaseReforma('pendente_confirmacao').label).toContain('pendente');
    expect(
      mensagemBaseReforma({ modo_base_ibs_cbs: 'BASE_CHEIA_OPERACAO', fonte_regra_base_ibs_cbs: 'pendente' }),
    ).toContain('integral');
  });

  it('labelFonteRegraBase', () => {
    expect(labelFonteRegraBase('contador')).toContain('contábil');
  });
});
