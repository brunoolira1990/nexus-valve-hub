/**
 * Parsing de decimal no formato do operador (vírgula).
 *
 * Aceita o texto parcial digitado tecla a tecla: «12,» vale 12 e «,5» vale 0,5, para que
 * o número apareça enquanto ele digita. Qualquer coisa que não seja decimal simples
 * («abc», «1.2,3», vazio) volta null e o chamador NÃO grava nada.
 */
const RE_DECIMAL_PT_BR = /^\d*(?:[.,]\d*)?$/;

export function parseDecimalPtBr(raw: string): number | null {
  const t = raw.trim();
  if (!t || !RE_DECIMAL_PT_BR.test(t)) return null;
  const n = Number(t.replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

/** Número → texto do input (ponto vira vírgula). null/undefined volta vazio. */
export function formatDecimalPtBr(n: number | null | undefined): string {
  if (n === null || n === undefined) return '';
  return String(n).replace('.', ',');
}
