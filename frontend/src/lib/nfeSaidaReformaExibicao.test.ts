import { describe, expect, it } from 'vitest';
import { linhasReformaItemExibicao } from '@/lib/nfeSaidaReformaExibicao';

describe('nfeSaidaReformaExibicao', () => {
  it('exibe base alíquota e valor CBS/IBS', () => {
    const linhas = linhasReformaItemExibicao({
      base_cbs: '500',
      aliquota_cbs: '0.9',
      valor_cbs: '4.5',
      base_ibs_estadual: '500',
      aliquota_ibs_estadual: '0.1',
      valor_ibs_estadual: '0.5',
      valor_total_ibs_cbs: '5',
    });
    expect(linhas.some((l) => l.includes('Base IBS/CBS'))).toBe(true);
    expect(linhas.some((l) => l.includes('Valor CBS') && l.includes('4,50'))).toBe(true);
    expect(linhas.some((l) => l.includes('Valor IBS UF') && l.includes('0,50'))).toBe(true);
    expect(linhas.some((l) => l.includes('Total IBS/CBS'))).toBe(true);
  });
});
