/** Formatação pt-BR para UI comercial (Pedido de Venda, etc.). */

export function formatCurrencyBRL(value: unknown): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return 'R$ 0,00';
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

/**
 * Quantidade legível: inteiro sem casas; decimais com vírgula (até 3 casas).
 * Unidade opcional após espaço.
 */
export function formatQuantidadeBR(value: unknown, unidade?: string | null): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return unidade ? `0 ${unidade}` : '0';
  const abs = Math.abs(n);
  const isInt = Math.abs(abs - Math.round(abs)) < 1e-9;
  let txt: string;
  if (isInt) {
    txt = String(Math.round(abs) * (n < 0 ? -1 : 1));
  } else {
    const dec = abs.toString().split('.')[1]?.length ?? 0;
    const places = Math.min(3, Math.max(1, dec));
    txt = n.toLocaleString('pt-BR', {
      minimumFractionDigits: places,
      maximumFractionDigits: places,
    });
  }
  const u = (unidade || '').trim().toUpperCase();
  return u ? `${txt} ${u}` : txt;
}

export function formatCepBR(cep: string | null | undefined): string {
  const d = String(cep || '').replace(/\D/g, '');
  if (d.length === 8) return `${d.slice(0, 5)}-${d.slice(5)}`;
  return (cep || '').trim() || '—';
}

export function formatPhoneBR(...parts: (string | null | undefined)[]): string {
  const joined = parts.map((p) => (p || '').trim()).filter(Boolean);
  return joined.length ? joined.join(' · ') : '—';
}

export function formatProdutoComercialLinha(
  codigo: string | null | undefined,
  descricao: string | null | undefined,
  maxLen = 72,
): { linha: string; tituloCompleto: string } {
  const cod = (codigo || '').trim();
  const desc = (descricao || '').trim();
  const tituloCompleto = cod && desc ? `${cod} — ${desc}` : cod || desc || '—';
  if (!cod) return { linha: tituloCompleto, tituloCompleto };
  if (!desc) return { linha: cod, tituloCompleto: cod };
  const prefix = `${cod} — `;
  const rest = maxLen - prefix.length;
  const descCurta = desc.length > rest && rest > 8 ? `${desc.slice(0, rest - 3).trim()}...` : desc;
  return { linha: `${prefix}${descCurta}`, tituloCompleto };
}
