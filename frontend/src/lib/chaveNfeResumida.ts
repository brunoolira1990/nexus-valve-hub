/** Exibe chave NF-e resumida para listagens (sem XML completo). */
export function chaveNfeResumida(chave?: string | null): string {
  if (!chave) return '—';
  const c = chave.trim();
  if (c.length <= 12) return c;
  return `${c.slice(0, 4)}…${c.slice(-4)}`;
}
