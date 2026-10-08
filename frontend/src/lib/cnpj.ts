/** Remove separadores e converte para maiúsculas; a validação verifica as 14 posições. */
export function normalizeCnpj(value: string): string {
  return value.replace(/[^0-9A-Za-z]/g, '').toUpperCase();
}

/** Formata CNPJ numérico ou alfanumérico no padrão XX.XXX.XXX/XXXX-DV. */
export function formatCnpjDisplay(value: string): string {
  const c = normalizeCnpj(value);
  if (c.length !== 14) return (value || '').trim() || '—';
  return `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}`;
}

/** Valida CNPJ numérico ou alfanumérico conforme o módulo 11 oficial. */
export function isValidCnpj(value: string): boolean {
  const c = normalizeCnpj(value);
  if (c.length !== 14 || !/^[0-9A-Z]{12}[0-9]{2}$/.test(c)) return false;
  if (new Set(c).size === 1) return false;

  const valorCaractere = (char: string): number => char.charCodeAt(0) - 48;
  const calc = (base: string, length: number): number => {
    let sum = 0;
    let pos = length - 7;
    for (let i = length; i >= 1; i--) {
      sum += valorCaractere(base.charAt(length - i)) * pos--;
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
