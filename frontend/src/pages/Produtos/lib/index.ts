/**
 * Barrel do lib/ de Produtos. Ponto único de import para a página container e abas.
 * Re-exporta também helpers de @/lib/familiaRegra por conveniência (fonte única —
 * NÃO redefinidos aqui).
 */
export * from './codigoPreview';
export * from './herancaFamilia';
export * from './familiaDerivations';

// Re-export de conveniência (fonte da verdade permanece em @/lib/familiaRegra)
export {
  labelsCamposObrigatoriosProduto,
  normalizarTipoRegra,
  flagsPorTipoRegra,
  hintTipoDimensional,
} from '@/lib/familiaRegra';
