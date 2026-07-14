/**
 * Valor unitário do Pedido de Venda — até 3 casas decimais.
 */

export const MSG_VALOR_UNITARIO_MAX_3_CASAS =
  'O valor unitário aceita no máximo 3 casas decimais.';

export const MAX_CASAS_VALOR_UNITARIO = 3;

/** Parse flexível: aceita 10,125 e 10.125; mantém milhar BR 1.234,56. */
export function parseValorUnitarioInput(value: string): number {
  const raw = (value || '').trim().replace(/\s/g, '');
  if (!raw) return 0;
  if (raw.includes(',') && raw.includes('.')) {
    const cleaned = raw.replace(/\./g, '').replace(',', '.');
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : 0;
  }
  if (raw.includes(',')) {
    const n = Number(raw.replace(',', '.'));
    return Number.isFinite(n) ? n : 0;
  }
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
}

/** Conta casas digitadas na parte fracionária (entrada do usuário). */
export function countDecimalPlacesInInput(value: string): number {
  const raw = (value || '').trim().replace(/\s/g, '');
  if (!raw) return 0;
  if (raw.includes(',')) {
    const frac = raw.split(',').pop() || '';
    return frac.replace(/\D/g, '').length;
  }
  if (raw.includes('.')) {
    const parts = raw.split('.');
    // Só ponto como decimal (ex.: 10.125). Milhar sem decimais (1.250) é raro no unitário.
    if (parts.length === 2) return parts[1].replace(/\D/g, '').length;
  }
  return 0;
}

export function valorUnitarioExcedeMaxCasas(rawInput: string): boolean {
  return countDecimalPlacesInInput(rawInput) > MAX_CASAS_VALOR_UNITARIO;
}

export function formatValorUnitarioDisplay(value: number): string {
  if (!Number.isFinite(value) || value === 0) return '';
  const isInt = Math.abs(value - Math.round(value)) < 1e-9;
  if (isInt) return String(Math.round(value));
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: 1,
    maximumFractionDigits: MAX_CASAS_VALOR_UNITARIO,
  });
}

/** Arredonda só o espelho legado de 2 casas; o preço comercial permanece intacto. */
export function espelhoValorUnitarioLegado(preco: number): number {
  if (!Number.isFinite(preco)) return 0;
  return Math.round((preco + Number.EPSILON) * 100) / 100;
}
