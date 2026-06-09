export function normalizeDecimalForApi(value: unknown, precision = 3): string {
  const n = Number(value ?? 0);
  const safe = Number.isFinite(n) ? n : 0;
  return safe.toFixed(precision);
}

export function parseLocaleDecimalInput(value: string): number {
  if (!value) return 0;
  const cleaned = value
    .replace(/\s/g, '')
    .replace(/\./g, '')
    .replace(',', '.')
    .replace(/[^\d.-]/g, '');
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : 0;
}

export function parseMoneyInputToDecimal(value: string): number {
  return parseLocaleDecimalInput(value);
}

export function parseQuantityInputToDecimal(value: string): number {
  return parseLocaleDecimalInput(value);
}

export function parsePercentInputToDecimal(value: string): number {
  return parseLocaleDecimalInput(value);
}

export function formatMoneyBRL(value: unknown): string {
  const n = Number(value ?? 0);
  return Number.isFinite(n)
    ? n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
    : 'R$ 0,00';
}

export function formatQuantityBR(value: unknown, unit?: string | null): string {
  const n = Number(value ?? 0);
  const safe = Number.isFinite(n) ? n : 0;
  const isInt = Math.abs(safe - Math.round(safe)) < 1e-9;
  const qty = isInt
    ? String(Math.round(safe))
    : safe.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 3 });
  const un = (unit || '').trim().toUpperCase();
  return un ? `${qty} ${un}` : qty;
}

export function formatPercentBR(value: unknown): string {
  const n = Number(value ?? 0);
  const safe = Number.isFinite(n) ? n : 0;
  return `${safe.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}%`;
}

export function isValidPositiveQuantity(value: unknown): boolean {
  return Number(value ?? 0) > 0;
}

export function isValidMoneyValue(value: unknown): boolean {
  const n = Number(value ?? 0);
  return Number.isFinite(n) && n >= 0;
}
