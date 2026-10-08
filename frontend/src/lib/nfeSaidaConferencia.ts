export type StatusConferencia = 'OK' | 'ATENCAO' | 'PENDENTE' | 'NAO_CONFIGURADA' | string;

export function badgeStatusConferencia(status: StatusConferencia): { label: string; className: string } {
  const st = (status || '').toUpperCase();
  if (st === 'OK' || st === 'PRONTA') return { label: 'OK', className: 'erp-badge-success' };
  if (st === 'PENDENTE' || st === 'COM_PENDENCIAS') return { label: 'Pendente', className: 'erp-badge-danger' };
  if (st === 'ATENCAO' || st === 'COM_ALERTAS') return { label: 'Atenção', className: 'erp-badge-warning' };
  if (st === 'NAO_CONFIGURADA') return { label: 'Não configurada', className: 'erp-badge-warning' };
  if (st === 'SEM_CALCULO') return { label: 'Sem cálculo', className: 'erp-badge-warning' };
  if (st === 'CALCULADA') return { label: 'Calculada', className: 'erp-badge-success' };
  return { label: status || '—', className: 'erp-badge-warning' };
}

export function fmtMoeda(v: string | number | undefined | null): string {
  const n = Number(v ?? 0);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function fmtNum(v: string | number | undefined | null, dec = 3): string {
  const n = Number(v ?? 0);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export function labelOrigemNfe(origem: string | undefined): string {
  const o = (origem || '').toUpperCase();
  if (o === 'FATURAMENTO') return 'Faturamento';
  if (o === 'PEDIDO') return 'Pedido de venda';
  return 'Manual';
}

export const GRUPO_VALIDACAO_LABELS: Record<string, string> = {
  cliente: 'Cliente',
  emitente: 'Emitente',
  itens: 'Itens',
  fiscal: 'Fiscal atual',
  valores: 'Valores',
  estoque: 'Estoque',
  transporte: 'Transporte',
  origem: 'Origem',
  reforma_tributaria: 'Reforma Tributária',
  pedido_cliente: 'Pedido do cliente',
  totais: 'Totais',
  higienizacao_xml: 'Higienização XML',
};
