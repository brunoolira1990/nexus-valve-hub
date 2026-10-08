/** Validações de e-mail/senha — ERP 4.0.14.9.2 */

export function emailOperacionalValido(email: string): boolean {
  const v = (email || '').trim();
  if (!v || !v.includes('@')) return false;
  const [, domain] = v.split('@');
  if (!domain || !domain.includes('.')) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}
