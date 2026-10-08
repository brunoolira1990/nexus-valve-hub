import type { StatusExpedicao, TipoOperacaoExpedicao } from '@/types/expedicao';

export const LABEL_TIPO_OPERACAO: Record<TipoOperacaoExpedicao, string> = {
  ESTOQUE_PROPRIO: 'Estoque próprio',
  RETIRADA_FORNECEDOR: 'Retirada fornecedor',
  ENTREGA_DIRETA_FORNECEDOR_CLIENTE: 'Entrega direta fornecedor → cliente',
  RETIRADA_FORNECEDOR_TRANSPORTADORA: 'Retirada fornecedor → transportadora',
  MISTO: 'Misto',
  OUTROS: 'Outros',
};

export const LABEL_STATUS_EXPEDICAO: Record<StatusExpedicao, string> = {
  RASCUNHO: 'Rascunho',
  AGUARDANDO_SEPARACAO: 'Aguardando separação',
  AGUARDANDO_RETIRADA_FORNECEDOR: 'Aguardando retirada fornecedor',
  MOTORISTA_ENVIADO: 'Motorista enviado',
  RETIRADO_FORNECEDOR: 'Retirado fornecedor',
  EM_TRANSITO: 'Em trânsito',
  ENTREGUE_TRANSPORTADORA: 'Entregue transportadora',
  ENTREGUE_CLIENTE: 'Entregue cliente',
  OCORRENCIA: 'Ocorrência',
  CANCELADO: 'Cancelado',
};

export function badgeStatusExpedicao(status: StatusExpedicao): string {
  if (status === 'ENTREGUE_CLIENTE') return 'success';
  if (status === 'OCORRENCIA') return 'warning';
  if (status === 'CANCELADO') return 'muted';
  if (status === 'EM_TRANSITO' || status === 'MOTORISTA_ENVIADO') return 'info';
  return 'default';
}

export function fmtDataBr(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = iso.slice(0, 10);
  const [y, m, day] = d.split('-');
  if (!y || !m || !day) return iso;
  return `${day}/${m}/${y}`;
}

export function fmtDateTimeBr(iso: string | null | undefined): string {
  if (!iso) return '—';
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso.slice(0, 16).replace('T', ' ');
  return dt.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export function vinculosResumo(item: {
  pedido_venda_numero?: string;
  pedido_compra_numero?: string;
  faturamento_numero?: string;
  nfe_saida_numero?: string;
  alocacao_atendimento?: number | null;
}): string {
  const parts = [
    item.pedido_venda_numero ? `PV ${item.pedido_venda_numero}` : '',
    item.pedido_compra_numero ? `PC ${item.pedido_compra_numero}` : '',
    item.faturamento_numero ? `FAT ${item.faturamento_numero}` : '',
    item.nfe_saida_numero ? `NF-e ${item.nfe_saida_numero}` : '',
    item.alocacao_atendimento ? `Aloc. ${item.alocacao_atendimento}` : '',
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : '—';
}
