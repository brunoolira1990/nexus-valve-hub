/** Sugestão de data prevista de entrega a partir do texto livre combinado com o fornecedor. */

const INDETERMINADOS = [
  'a combinar',
  'sob consulta',
  'apos aprovacao',
  'apos aprovacao do pedido',
  'apos pagamento',
  'apos pagamento do pedido',
  'a definir',
  'negociar',
  'conforme negocio',
  'conforme negociacao',
];

function normalize(text: string): string {
  return (text ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function isIndeterminado(n: string): boolean {
  return INDETERMINADOS.some((m) => n.includes(m));
}

function parseIsoLocal(iso: string): Date | null {
  const s = (iso || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function toIsoLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function addDiasCorridos(baseIso: string, dias: number): string | null {
  const b = parseIsoLocal(baseIso);
  if (!b) return null;
  const t = new Date(b);
  t.setDate(t.getDate() + dias);
  return toIsoLocal(t);
}

function addDiasUteis(baseIso: string, diasUteis: number): string | null {
  const b = parseIsoLocal(baseIso);
  if (!b) return null;
  let restantes = diasUteis;
  const cur = new Date(b);
  while (restantes > 0) {
    cur.setDate(cur.getDate() + 1);
    const dow = cur.getDay();
    if (dow !== 0 && dow !== 6) restantes -= 1;
  }
  return toIsoLocal(cur);
}

/**
 * Retorna ISO yyyy-mm-dd ou null se não for possível sugerir automaticamente.
 */
export function sugerirDataPrevistaEntregaIso(dataPedidoIso: string, prazoTexto: string): string | null {
  const raw = (prazoTexto || '').trim();
  if (!raw) return null;
  const n = normalize(raw);
  if (!dataPedidoIso || isIndeterminado(n)) return null;

  if (n === 'imediato' || n === 'imediat' || n === 'urgente') {
    return dataPedidoIso.slice(0, 10);
  }

  let m = n.match(/(\d+)\s*semanas?/);
  if (m) {
    const sem = Number(m[1]);
    if (sem >= 0 && sem < 500) return addDiasCorridos(dataPedidoIso, sem * 7);
  }

  m = n.match(/(\d+)\s*dias?\s*uteis?/);
  if (m) {
    const du = Number(m[1]);
    if (du >= 0 && du < 5000) return addDiasUteis(dataPedidoIso, du);
  }

  m = n.match(/(\d+)\s*dias?\s*corridos?/);
  if (m) {
    const dc = Number(m[1]);
    if (dc >= 0 && dc < 5000) return addDiasCorridos(dataPedidoIso, dc);
  }

  m = n.match(/(\d+)\s*dias?/);
  if (m) {
    const d = Number(m[1]);
    if (d >= 0 && d < 5000) return addDiasCorridos(dataPedidoIso, d);
  }

  return null;
}
