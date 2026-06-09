import { describe, expect, it } from 'vitest';
import { reformaFromApi, reformaToApi } from '@/lib/regrasFiscaisEntradaHelpers';

describe('reformaTributariaApi', () => {
  it('reformaToApi converte 0,1 e 0,9 para ponto decimal', () => {
    const api = reformaToApi({
      cst_ibs_cbs: '000',
      classificacao_tributaria: '000001',
      aliquota_ibs_estadual: '0,1',
      aliquota_cbs: '0,9',
      aliquota_ibs_municipal: '',
      reducao_cbs: '',
      reducao_ibs: '',
      diferimento_cbs: '',
      diferimento_ibs: '',
      credito_presumido_cbs: '',
      credito_presumido_ibs: '',
      observacoes: '',
    });
    expect(api?.aliquota_ibs_estadual).toBe('0.1');
    expect(api?.aliquota_cbs).toBe('0.9');
  });

  it('reformaFromApi preserva valores da API', () => {
    const form = reformaFromApi({ aliquota_ibs_estadual: '0.1', aliquota_cbs: '0.9' });
    expect(form.aliquota_ibs_estadual).toBe('0.1');
    expect(form.aliquota_cbs).toBe('0.9');
  });
});
