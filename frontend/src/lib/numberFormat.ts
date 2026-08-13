/** Normalização segura de números vindos da API (string, number, null). */

export function toNumber(value: unknown, fallback = 0): number {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : fallback;
  }
  const s = String(value).trim().replace(/\s/g, '').replace(',', '.');
  if (!s) return fallback;
  const n = Number(s);
  return Number.isFinite(n) ? n : fallback;
}

export function formatDecimal(value: unknown, digits = 2): string {
  return toNumber(value).toFixed(digits);
}

export function formatPercent(value: unknown, digits = 2): string {
  return `${formatDecimal(value, digits)}%`;
}

/** Valor seguro para `<input type="number" value={...} />` (evita NaN no React). */
export function inputNumberValue(value: unknown, fallback = 0): number | '' {
  if (value === null || value === undefined || value === '') return '';
  const n = toNumber(value, NaN);
  return Number.isFinite(n) ? n : fallback;
}

export function formatMoneyBr(value: unknown, digits = 2): string {
  const n = toNumber(value);
  return n.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}
