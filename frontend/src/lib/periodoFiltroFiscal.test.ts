import { describe, expect, it } from 'vitest';
import {
  aplicarCompetenciaMmAaaa,
  intervaloMes,
  labelPeriodoFiltro,
} from '@/lib/periodoFiltroFiscal';

describe('periodoFiltroFiscal', () => {
  it('monta intervalo do mês', () => {
    expect(intervaloMes(2026, 6)).toEqual({ inicio: '2026-06-01', fim: '2026-06-30' });
  });

  it('aplica competência mm/aaaa', () => {
    expect(aplicarCompetenciaMmAaaa('06/2026')).toEqual({ inicio: '2026-06-01', fim: '2026-06-30' });
    expect(aplicarCompetenciaMmAaaa('062026')).toEqual({ inicio: '2026-06-01', fim: '2026-06-30' });
    expect(aplicarCompetenciaMmAaaa('13/2026')).toBeNull();
  });

  it('rotula período ativo', () => {
    expect(labelPeriodoFiltro({ dataInicio: '2026-06-01', dataFim: '2026-06-30' })).toContain('2026-06-01');
    expect(labelPeriodoFiltro({})).toMatch(/sem período/i);
  });
});
