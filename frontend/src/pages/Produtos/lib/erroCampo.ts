import { cn } from '@/lib/utils';

/**
 * Campos que a validação de `salvar()` pode apontar. O valor é também o sufixo do
 * `id` do container na tela — a página usa isso para encontrar o elemento e rolar
 * até ele, sem manter um mapa de campos paralelo.
 */
export type CampoFormProdutoInvalido =
  | 'descricao'
  | 'familia_id'
  | 'material_ref'
  | 'od_mm'
  | 'diametro_interno_mm'
  | 'espessura_mm'
  | 'comprimento_mm'
  | 'diametro_mostrador_mm';

export const campoId = (campo: CampoFormProdutoInvalido) => `campo_${campo}`;

/** Anel vermelho no container do campo que bloqueou o salvamento. */
export const classeErroCampo = (
  campoErro: CampoFormProdutoInvalido | null | undefined,
  campo: CampoFormProdutoInvalido,
) => cn(campoErro === campo && 'rounded-md ring-2 ring-destructive');
