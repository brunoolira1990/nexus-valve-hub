/**
 * Rótulo de rosca/conexão para exibição. Espelho frontend de
 * `_descricao_rosca_comercial` (backend/apps/produtos/codigo_produto.py): o catálogo
 * guarda uma linha-sentinela com `codigo` vazio e `descricao` 'BSP / padrão da família',
 * e esse metadado interno nunca deve aparecer na ficha do produto.
 */

/** Fragmentos de nome que o backend também descarta (`_descricao_rosca_comercial`). */
const FRAGMENTOS_NAO_EXIBIVEIS = ['sem rosca', 'default'] as const;

function normalizarEspacos(valor: string): string {
  return valor.replace(/\s+/g, ' ').trim();
}

export function etiquetaRosca(
  rosca?: { codigo?: string | null; descricao?: string | null } | null,
): string {
  if (!rosca) return '';
  const codigo = normalizarEspacos(rosca.codigo || '');
  if (codigo.toUpperCase() === 'SW') return 'SW';

  const bruto = normalizarEspacos(rosca.descricao || '');
  if (/PADR[ÃA]O DA FAM[ÍI]LIA/i.test(bruto)) return 'BSP';

  let limpo = bruto;
  for (const fragmento of FRAGMENTOS_NAO_EXIBIVEIS) {
    limpo = limpo.replace(new RegExp(fragmento.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&'), 'gi'), '');
  }
  limpo = normalizarEspacos(limpo.replace(/^[ /-]+/, '').replace(/[ /-]+$/, ''));

  if (!limpo && !codigo) return 'BSP';
  return limpo || codigo;
}
