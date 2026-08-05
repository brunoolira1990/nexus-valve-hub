import { describe, expect, it, vi, afterEach } from 'vitest';

import {
  competenciaDeDataIso,
  competenciaMesAtualMmAaaa,
  intervaloMesAtual,
  pad2,
} from '@/lib/periodoFiltroFiscal';

describe('periodoFiltroFiscal — competência', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('converte data ISO em mm/aaaa', () => {
    expect(competenciaDeDataIso('2026-08-01')).toBe('08/2026');
    expect(competenciaDeDataIso('2026-06-30')).toBe('06/2026');
  });

  it('competência do mês atual acompanha a data do sistema', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 7, 4)); // ago/2026
    expect(competenciaMesAtualMmAaaa()).toBe('08/2026');
    const p = intervaloMesAtual();
    expect(p.inicio).toBe('2026-08-01');
    expect(p.fim).toBe(`2026-08-${pad2(31)}`);
  });
});
