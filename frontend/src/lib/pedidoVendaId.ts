/** Resolve o pk numérico do pedido de venda para chamadas à API (PDF, delete, etc.). */

export type PedidoVendaIdSource = {
  id?: number | string | null;
  pk?: number | string | null;
};

export const MSG_PDF_PEDIDO_SEM_ID = 'Salve ou recarque o pedido antes de gerar o PDF.';

export function resolvePedidoVendaId(source: PedidoVendaIdSource | null | undefined): number | null {
  if (!source) return null;
  const raw = source.id ?? source.pk;
  if (raw == null || raw === '') return null;
  const n = typeof raw === 'number' ? raw : Number(String(raw).trim());
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.trunc(n);
}

export function normalizePedidoVendaRow<T extends PedidoVendaIdSource>(row: T): T & { id: number } {
  const id = resolvePedidoVendaId(row);
  if (id == null) return row as T & { id: number };
  return { ...row, id };
}
