import { describe, expect, it } from 'vitest';
import {
  CBENEF_SEM_CODIGO_LITERAL,
  ehMarcadorCbenefNaoFiscal,
} from './catalogosFiscais';

describe('ehMarcadorCbenefNaoFiscal', () => {
  it('detecta SEM CBENEF e variantes', () => {
    expect(ehMarcadorCbenefNaoFiscal(CBENEF_SEM_CODIGO_LITERAL)).toBe(true);
    expect(ehMarcadorCbenefNaoFiscal('sem cbenef')).toBe(true);
    expect(ehMarcadorCbenefNaoFiscal('SEM BENEFICIO')).toBe(true);
  });

  it('aceita código fiscal real', () => {
    expect(ehMarcadorCbenefNaoFiscal('SP020120')).toBe(false);
    expect(ehMarcadorCbenefNaoFiscal('')).toBe(false);
    expect(ehMarcadorCbenefNaoFiscal(null)).toBe(false);
  });
});
