/** Remove não-dígitos e limita a 14 caracteres. */
export function normalizeCnpj(value: string): string {
  return value.replace(/\D/g, '').slice(0, 14);
}

/** Formata CNPJ para exibição (14 dígitos); caso incompleto, devolve o texto trimado. */
export function formatCnpjDisplay(value: string): string {
  const c = normalizeCnpj(value);
  if (c.length !== 14) return (value || '').trim() || '—';
  return `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}`;
}

/** Valida dígitos verificadores do CNPJ (após normalização). */
export function isValidCnpj(value: string): boolean {
  const c = normalizeCnpj(value);
  if (c.length !== 14) return false;
  if (/^(\d)\1{13}$/.test(c)) return false;

  const calc = (base: string, length: number): number => {
    let sum = 0;
    let pos = length - 7;
    for (let i = length; i >= 1; i--) {
      sum += Number(base.charAt(length - i)) * pos--;
      if (pos < 2) pos = 9;
    }
    const r = sum % 11;
    return r < 2 ? 0 : 11 - r;
  };

  const len = 12;
  const d1 = calc(c.substring(0, len), len);
  if (d1 !== Number(c.charAt(12))) return false;
  const d2 = calc(c.substring(0, 13), 13);
  return d2 === Number(c.charAt(13));
}
