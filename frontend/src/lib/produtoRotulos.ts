import type { ModoCodigoProduto } from '@/types';

/**
 * Rótulos curtos do modo de código para as telas de produto.
 * As choices oficiais do model (ModoCodigo) são frases longas, apropriadas só para o formulário.
 */
export const ROTULO_MODO_CODIGO: Record<ModoCodigoProduto, string> = {
  INTERNO: 'Interno',
  MANUAL: 'Manual',
  LEGADO: 'Legado',
};
