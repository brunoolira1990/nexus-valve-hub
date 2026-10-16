/**
 * Helpers puros de código/preview extraídos de ProdutoList.tsx.
 *
 * NOTA (duplicação temporária autorizada): `formatDecimalField` e
 * `codigoProdutoIgual` são definidas localmente em ProdutoList.tsx e NÃO são
 * exportadas de lá. Como ProdutoList.tsx deve permanecer intocado nesta fase
 * (Strangler Fig), elas são duplicadas aqui. Quando o modal for aposentado,
 * esta passa a ser a fonte única.
 */
import type { ProdutoFormState } from '../types';

/** Formata number -> string PT, removendo zeros decimais à direita. (dup. de ProdutoList) */
export function formatDecimalField(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '';
  const txt = String(v);
  return txt.includes('.') ? txt.replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1') : txt;
}

/** Compara códigos de produto normalizando trim+lowercase. (dup. de ProdutoList) */
export function codigoProdutoIgual(
  a: string | null | undefined,
  b: string | null | undefined,
): boolean {
  return (a || '').trim().toLowerCase() === (b || '').trim().toLowerCase();
}

/** Converte texto decimal flexível ("10,0" | "1.5") em number | null. */
export function parseDecimalFlexible(raw: string): number | null {
  const s = (raw || '').trim();
  if (!s) return null;
  const n = Number(s.replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

/** Lê um valor de dimensão (dim_<key> explícito ou dimensoes_json[key]) formatado. */
export function getDimInputValue(form: ProdutoFormState, key: string): string {
  const explicit = (form as unknown as Record<string, number | string | null | undefined>)[
    `dim_${key}`
  ];
  const v = explicit ?? form.dimensoes_json?.[key];
  if (v == null || v === '') return '';
  const n = typeof v === 'number' ? v : Number(String(v).replace(',', '.'));
  return Number.isFinite(n) ? formatDecimalField(n) : '';
}

/**
 * Prévia do código no modo LEGADO. Corpo VERBATIM de ProdutoList.tsx (linha 178):
 * junta figura/sufixo/schedule + polegadas com separador "." (ponto).
 */
export function genCodigoLegadoPreview(f: ProdutoFormState): string {
  const parts = [f.figura, f.sufixo, f.schedule].map((s) => (s || '').trim()).filter(Boolean);
  const p1 = (f.polegada_principal || '').replace(/"/g, '').trim();
  const p2 = (f.polegada_secundaria || '').replace(/"/g, '').trim();
  let inch = '';
  if (p1 && p2) inch = `${p1}x${p2}`;
  else if (p1) inch = p1;
  else if (p2) inch = p2;
  if (inch) parts.push(inch);
  return parts.join('.');
}
