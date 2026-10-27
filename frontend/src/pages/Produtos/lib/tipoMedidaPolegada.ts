export type TipoMedidaPolegada = 'NPS' | 'OD';

/**
 * Tipo usado para filtrar a busca de polegada.
 *
 * A polegada já salva manda: trocar o filtro dela reclassificaria a medida e mudaria o
 * código do produto. Sem valor salvo, vale a regra da família
 * (`tipoMedidaPrincipalPorDimensional` / `tipoMedidaSecundariaPorDimensional`, que
 * espelham `tipo_medida_esperado_por_campo` do backend). `undefined` deixa o autocomplete
 * buscar nos dois tipos em vez de forçar OD.
 */
export function resolverTipoMedida(
  salva: TipoMedidaPolegada | null | undefined,
  esperado: TipoMedidaPolegada | undefined,
): TipoMedidaPolegada | undefined {
  if (salva === 'NPS' || salva === 'OD') return salva;
  return esperado;
}
