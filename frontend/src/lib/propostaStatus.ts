import {
  STATUS_PROPOSTA_CONVERTIDA,
  STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA,
  STATUS_PROPOSTA_REABERTA,
} from '@/lib/comercialFormDefaults';
import type { Proposta } from '@/types';

export type PropostaStatusUi = {
  label: string;
  badgeClass: string;
  valor: string;
};

function normStatus(status: string | undefined): string {
  return (status || '').trim().toUpperCase();
}

/** Proposta convertida integralmente (todos os itens válidos). */
export function propostaTotalmenteConvertida(
  proposta: Pick<Proposta, 'status'> | null | undefined,
): boolean {
  if (!proposta) return false;
  return normStatus(proposta.status) === STATUS_PROPOSTA_CONVERTIDA;
}

/** Proposta já gerou ao menos um pedido de venda. */
export function propostaTemPedidoGerado(
  proposta: Pick<Proposta, 'pedido_venda_id' | 'status' | 'pedidos_gerados_resumo'> | null | undefined,
): boolean {
  if (!proposta) return false;
  if (proposta.pedidos_gerados_resumo?.length) return true;
  if (proposta.pedido_venda_id) return true;
  const st = normStatus(proposta.status);
  return st === STATUS_PROPOSTA_CONVERTIDA || st === STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA;
}

export function propostaPodeGerarPedido(
  proposta: Pick<Proposta, 'pode_gerar_pedido' | 'requer_recuperacao'> | null | undefined,
): boolean {
  if (!proposta) return false;
  if (proposta.requer_recuperacao) return false;
  return Boolean(proposta.pode_gerar_pedido);
}

export function propostaRequerRecuperacao(
  proposta: Pick<Proposta, 'requer_recuperacao'> | null | undefined,
): boolean {
  return Boolean(proposta?.requer_recuperacao);
}

export function statusPropostaUi(
  proposta: Pick<Proposta, 'status' | 'pedido_venda_id' | 'pedidos_gerados_resumo'>,
): PropostaStatusUi {
  const st = (proposta.status || '').trim();
  const upper = normStatus(st);
  if (upper === STATUS_PROPOSTA_CONVERTIDA) {
    return { label: 'Convertida', badgeClass: 'erp-badge-success', valor: st };
  }
  if (upper === STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA) {
    return { label: 'Parcialmente convertida', badgeClass: 'erp-badge-warning', valor: st };
  }
  if (upper === STATUS_PROPOSTA_REABERTA) {
    return { label: 'Reaberta', badgeClass: 'erp-badge-warning', valor: st };
  }
  if (upper === 'APROVADA' || upper === 'APROVADO') {
    return { label: 'Aprovada', badgeClass: 'erp-badge-success', valor: st };
  }
  if (upper === 'PENDENTE' || st === 'Pendente') {
    return { label: 'Pendente', badgeClass: 'erp-badge-warning', valor: st };
  }
  if (upper === 'REJEITADA' || upper === 'REJEITADO') {
    return { label: 'Rejeitada', badgeClass: 'erp-badge-danger', valor: st };
  }
  if (upper === 'CANCELADA' || upper === 'CANCELADO' || upper === 'PERDIDA' || upper === 'PERDIDO') {
    return { label: upper.startsWith('PERD') ? 'Perdida' : 'Cancelada', badgeClass: 'erp-badge-danger', valor: st };
  }
  return { label: st || '—', badgeClass: 'erp-badge-danger', valor: st };
}

export function labelStatusItemProposta(status?: string | null): string {
  const st = normStatus(status || 'PENDENTE');
  if (st === 'CONVERTIDO_EM_PEDIDO') return 'Convertido em pedido';
  if (st === 'CANCELADO') return 'Cancelado';
  if (st === 'PERDIDO') return 'Perdido';
  if (st === 'MANTIDO_PARA_DEPOIS') return 'Pendente (mantido)';
  return 'Pendente';
}

export function labelEventoComercialProposta(tipo?: string | null): string {
  const st = normStatus(tipo || '');
  if (st === 'PROPOSTA_RECUPERADA') return 'Proposta recuperada';
  if (st === 'PEDIDO_GERADO') return 'Pedido gerado';
  if (st === 'ITEM_CONVERTIDO') return 'Item convertido';
  if (st === 'ITEM_CANCELADO') return 'Item cancelado';
  if (st === 'ITEM_MANTIDO_PENDENTE') return 'Item mantido pendente';
  return tipo || '—';
}
