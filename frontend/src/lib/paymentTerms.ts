const SPLIT_REGEX = /[\/,\-\s]+/;

/** Mensagem padrão quando a condição não é interpretável ou usa termos indefinidos (pedido de compra). */
export const MENSAGEM_CONDICAO_PAGAMENTO_PEDIDO_DEFINIDA =
  'Informe uma condição de pagamento definida. Ex.: À vista, 30, 30/45/60.';

function normalize(text: string): string {
  return (text ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/ddl/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Remove sufixos como "30 dias" -> "30" (uma parcela). */
function stripDiaSuffixes(normalized: string): string {
  return normalized.replace(/\b(\d+)\s*dias?\b/g, '$1').replace(/\s+/g, ' ').trim();
}

function isIndeterminatePayment(normalized: string): boolean {
  if (!normalized) return false;
  const markers = [
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
  return markers.some((m) => normalized.includes(m));
}

export type ParseCondicaoPagamentoResult =
  | { kind: 'dias'; dias: number[] }
  | { kind: 'invalid'; message: string };

/** Pedido de compra: exige condição fechada; termos indefinidos são inválidos. */
export function parseCondicaoPagamentoPedido(text: string): ParseCondicaoPagamentoResult {
  const raw = (text ?? '').trim();
  if (!raw) return { kind: 'dias', dias: [] };
  const normalized = normalize(raw);
  if (isIndeterminatePayment(normalized)) {
    return { kind: 'invalid', message: MENSAGEM_CONDICAO_PAGAMENTO_PEDIDO_DEFINIDA };
  }
  try {
    return { kind: 'dias', dias: parsePaymentCondition(text) };
  } catch {
    return { kind: 'invalid', message: MENSAGEM_CONDICAO_PAGAMENTO_PEDIDO_DEFINIDA };
  }
}

export function parsePaymentCondition(text: string): number[] {
  const raw = (text ?? '').trim();
  if (!raw) return [];

  const normalized = stripDiaSuffixes(normalize(raw));
  if (isIndeterminatePayment(normalized)) {
    return [];
  }
  if (normalized === 'a vista' || normalized === 'avista' || normalized === '0') {
    return [0];
  }

  const parts = normalized.split(SPLIT_REGEX).filter(Boolean);
  if (!parts.length) throw new Error("Condição inválida. Use formatos como '30/45 DDL' ou 'à vista'.");

  const days = parts.map((part) => {
    if (!/^\d+$/.test(part)) throw new Error('Condição inválida. Use apenas números e separadores.');
    const value = Number(part);
    if (value < 0) throw new Error('Dias da condição devem ser maiores ou iguais a zero.');
    return value;
  });

  return days;
}

export function buildDueDates(baseDate: string, days: number[]): string[] {
  if (!baseDate) return [];
  const base = new Date(`${baseDate}T00:00:00`);
  if (Number.isNaN(base.getTime())) return [];
  return days.map((day) => {
    const due = new Date(base);
    due.setDate(due.getDate() + day);
    return due.toISOString().slice(0, 10);
  });
}

/** Formata yyyy-mm-dd (ou ISO) para dd/mm/aaaa sem depender de fuso. */
export function formatDataIsoParaBr(iso: string): string {
  const s = (iso || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return iso || '—';
  const [y, m, d] = s.split('-');
  return `${d}/${m}/${y}`;
}
