import type { ItemConferenciaNFeEntrada } from '@/types';

/** Espelha `calcular_status_operacional_item_conferencia` no backend. */
export function calcularStatusOperacionalItemConferencia(
  item: Pick<ItemConferenciaNFeEntrada, 'status' | 'produto_id' | 'item_pedido_compra_id' | 'divergencias'>,
): ItemConferenciaNFeEntrada['status'] {
  if (item.status === 'IGNORADO') {
    return 'IGNORADO';
  }
  if (!item.produto_id) {
    return 'PENDENTE_PRODUTO';
  }
  if (item.divergencias?.length) {
    return 'DIVERGENTE';
  }
  if (item.item_pedido_compra_id) {
    return 'CONFERIDO';
  }
  return 'PRODUTO_VINCULADO';
}

export function aplicarStatusAutomaticoItem<T extends ItemConferenciaNFeEntrada>(item: T): T {
  if (item.status === 'IGNORADO') {
    return item;
  }
  return { ...item, status: calcularStatusOperacionalItemConferencia(item) };
}
