/** Payload de itens complementares na conferência NF-e (origem comercial travada). */

/** Campos comerciais imutáveis em NF-e herdada — nunca devem ir no salvar-conferencia. */
export const CAMPOS_COMERCIAIS_ITEM_NFE = [
  'produto',
  'produto_id',
  'quantidade',
  'valor',
  'corrida',
  'corrida_id',
] as const;

export type ItemConferenciaComplementar = {
  item_id?: number | string | null;
  pedido_cliente_numero?: string | null;
  pedido_cliente_numero_editavel?: string | null;
  pedido_cliente_item?: string | null;
  pedido_cliente_item_editavel?: string | null;
  observacao_item?: string | null;
  informacao_adicional_item?: string | null;
};

export type ItemComplementarPayload = {
  id: number;
  pedido_cliente_numero?: string;
  pedido_cliente_item?: string;
  observacao_item?: string;
  informacao_adicional_item?: string;
};

export function montarItensComplementaresConferencia(
  itens: ItemConferenciaComplementar[],
  origemComercialTravada: boolean,
): ItemComplementarPayload[] | undefined {
  const mapped: ItemComplementarPayload[] = [];
  for (const it of itens) {
    const rawId = it.item_id ?? (it as { id?: number | string }).id;
    const id = typeof rawId === 'number' ? rawId : Number(rawId);
    if (!Number.isFinite(id) || id <= 0) continue;
    // Somente complementos — produto/quantidade/valor nunca entram no payload.
    mapped.push({
      id,
      pedido_cliente_numero: String(it.pedido_cliente_numero_editavel ?? it.pedido_cliente_numero ?? '').trim(),
      pedido_cliente_item: String(it.pedido_cliente_item_editavel ?? it.pedido_cliente_item ?? '').trim(),
      observacao_item: String(it.observacao_item ?? '').trim(),
      informacao_adicional_item: String(it.informacao_adicional_item ?? '').trim(),
    });
  }
  if (origemComercialTravada && mapped.length === 0) {
    return undefined;
  }
  return mapped.length > 0 ? mapped : undefined;
}
