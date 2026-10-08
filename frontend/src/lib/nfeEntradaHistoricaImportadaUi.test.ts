import { describe, expect, it } from 'vitest';

import {
  labelBotaoPrincipalConferenciaNfeEntradaHistorica,
  labelStatusOperacionalNfeEntradaHistorica,
  resolverStatusOperacionalNfeEntradaHistorica,
  rotaConferenciaNfeEntradaHistorica,
} from './nfeEntradaHistoricaImportadaUi';

describe('nfeEntradaHistoricaImportadaUi', () => {
  it('mapeia os quatro estados operacionais', () => {
    expect(
      labelStatusOperacionalNfeEntradaHistorica({
        conferencia_status: null,
        conferencia_preparado_em: null,
        conferencia_estoque_aplicado_em: null,
      }),
    ).toBe('Aguardando conferência');

    expect(
      labelStatusOperacionalNfeEntradaHistorica({
        conferencia_status: 'PENDENTE',
        conferencia_preparado_em: null,
        conferencia_estoque_aplicado_em: null,
      }),
    ).toBe('Conferência em andamento');

    expect(
      labelStatusOperacionalNfeEntradaHistorica({
        conferencia_status: 'PREPARADA',
        conferencia_preparado_em: '2026-01-01T12:00:00Z',
        conferencia_estoque_aplicado_em: null,
      }),
    ).toBe('Aguardando estoque');

    expect(
      labelStatusOperacionalNfeEntradaHistorica({
        conferencia_status: 'PREPARADA',
        conferencia_preparado_em: '2026-01-01T12:00:00Z',
        conferencia_estoque_aplicado_em: '2026-01-02T12:00:00Z',
      }),
    ).toBe('Entrada realizada');
  });

  it('ajusta o botão principal por estado', () => {
    const base = {
      conferencia_preparado_em: null as string | null,
      conferencia_estoque_aplicado_em: null as string | null,
    };

    expect(
      labelBotaoPrincipalConferenciaNfeEntradaHistorica({
        ...base,
        conferencia_status: null,
      }),
    ).toBe('Conferir entrada');

    expect(
      labelBotaoPrincipalConferenciaNfeEntradaHistorica({
        ...base,
        conferencia_status: 'PENDENTE',
      }),
    ).toBe('Continuar conferência');

    expect(
      labelBotaoPrincipalConferenciaNfeEntradaHistorica({
        conferencia_status: 'PREPARADA',
        conferencia_preparado_em: '2026-01-01T12:00:00Z',
        conferencia_estoque_aplicado_em: null,
      }),
    ).toBe('Aplicar estoque');

    expect(
      labelBotaoPrincipalConferenciaNfeEntradaHistorica({
        conferencia_status: 'PREPARADA',
        conferencia_preparado_em: '2026-01-01T12:00:00Z',
        conferencia_estoque_aplicado_em: '2026-01-02T12:00:00Z',
      }),
    ).toBe('Ver conferência');
  });

  it('usa hash de estoque quando aguardando aplicação', () => {
    const row = {
      conferencia_status: 'PREPARADA',
      conferencia_preparado_em: '2026-01-01T12:00:00Z',
      conferencia_estoque_aplicado_em: null,
    };
    expect(resolverStatusOperacionalNfeEntradaHistorica(row)).toBe('aguardando_estoque');
    expect(rotaConferenciaNfeEntradaHistorica(42, row)).toBe('/nfe-entrada/42/conferencia#aplicar-estoque-fisico');
  });
});
