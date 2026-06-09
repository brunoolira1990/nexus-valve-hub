import { STATUS_PROPOSTA_CONVERTIDA } from '@/lib/comercialFormDefaults';
import type { Proposta } from '@/types';

export type PropostaStatusUi = {
  label: string;
  badgeClass: string;
  valor: string;
};

function normStatus(status: string | undefined): string {
  return (status || '').trim().toUpperCase();
}

/** Proposta já gerou pedido de venda (API ou status CONVERTIDA). */
export function propostaTemPedidoGerado(
  proposta: Pick<Proposta, 'pedido_venda_id' | 'status'> | null | undefined,
): boolean {
  if (!proposta) return false;
  if (proposta.pedido_venda_id) return true;
  return normStatus(proposta.status) === STATUS_PROPOSTA_CONVERTIDA;
}

export function statusPropostaUi(
  proposta: Pick<Proposta, 'status' | 'pedido_venda_id'>,
): PropostaStatusUi {
  if (propostaTemPedidoGerado(proposta)) {
    return {
      label: 'Convertida',
      badgeClass: 'erp-badge-success',
      valor: STATUS_PROPOSTA_CONVERTIDA,
    };
  }
  const st = (proposta.status || '').trim();
  const upper = normStatus(st);
  if (upper === 'APROVADA' || upper === 'APROVADO') {
    return { label: 'Aprovada', badgeClass: 'erp-badge-success', valor: st };
  }
  if (upper === 'PENDENTE' || st === 'Pendente') {
    return { label: 'Pendente', badgeClass: 'erp-badge-warning', valor: st };
  }
  if (upper === 'REJEITADA' || upper === 'REJEITADO') {
    return { label: 'Rejeitada', badgeClass: 'erp-badge-danger', valor: st };
  }
  return { label: st || '—', badgeClass: 'erp-badge-danger', valor: st };
}
