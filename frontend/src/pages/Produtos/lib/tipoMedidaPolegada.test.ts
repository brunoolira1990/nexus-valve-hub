import { describe, expect, it } from 'vitest';
import { tipoMedidaPrincipalPorDimensional, tipoMedidaSecundariaPorDimensional } from '@/lib/familiaRegra';
import { resolverTipoMedida } from './tipoMedidaPolegada';

describe('resolverTipoMedida — filtro NPS/OD da busca de polegada', () => {
  it('prioriza o tipo da polegada já salva, para não reclassificar a medida do código', () => {
    expect(resolverTipoMedida('OD', 'NPS')).toBe('OD');
    expect(resolverTipoMedida('NPS', 'OD')).toBe('NPS');
  });

  it('usa a regra da família quando ainda não há valor salvo', () => {
    expect(resolverTipoMedida(null, 'NPS')).toBe('NPS');
    expect(resolverTipoMedida(undefined, undefined)).toBeUndefined();
  });

  it('a regra da família decide o tipo (espelho de tipo_medida_esperado_por_campo)', () => {
    expect(tipoMedidaPrincipalPorDimensional('NPS_SCHEDULE')).toBe('NPS');
    expect(tipoMedidaPrincipalPorDimensional('NPS_X_ROSCA')).toBe('NPS');
    expect(tipoMedidaPrincipalPorDimensional('ROSCA')).toBe('NPS');
    expect(tipoMedidaPrincipalPorDimensional('OD_POLEGADA')).toBe('OD');
    // OD_MM e SIMPLES não usam FK de polegada: a busca fica livre em vez de forçar OD.
    expect(tipoMedidaPrincipalPorDimensional('OD_MM')).toBeUndefined();
    expect(tipoMedidaPrincipalPorDimensional('SIMPLES')).toBeUndefined();
    expect(tipoMedidaSecundariaPorDimensional('NPS_SCHEDULE')).toBe('NPS');
    expect(tipoMedidaSecundariaPorDimensional('OD_POLEGADA')).toBeUndefined();
  });
});
