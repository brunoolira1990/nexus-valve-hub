/** Descrição comercial: maiúsculas sem acento (símbolos # " ° - / . preservados). */

export function normalizarDescricaoProduto(texto: string): string {
  if (texto == null || texto === '') return '';
  const s = String(texto).trim();
  if (!s) return '';
  const semAcento = s.normalize('NFKD').replace(/\p{Mn}/gu, '');
  return semAcento.replace(/\s+/g, ' ').trim().toUpperCase();
}
