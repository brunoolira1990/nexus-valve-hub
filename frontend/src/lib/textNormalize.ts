export function toOperationalUpper(value: unknown): string {
  if (value === null || value === undefined) return '';
  return String(value).toLocaleUpperCase('pt-BR');
}

export function normalizeOperationalInput(value: string): string {
  return (value ?? '').toLocaleUpperCase('pt-BR');
}

export function shouldNormalizeOperationalByType(inputType?: string): boolean {
  const t = (inputType || '').toLowerCase();
  return !['email', 'url', 'password', 'hidden'].includes(t);
}
