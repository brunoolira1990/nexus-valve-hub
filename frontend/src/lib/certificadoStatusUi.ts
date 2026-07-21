/** Labels e classes de badge para listagens do módulo Qualidade (apenas UI). */

export type StatusBadgePair = { label: string; className: string };

const unknownBadge: StatusBadgePair = {
  label: '—',
  className: 'erp-badge bg-muted/80 text-muted-foreground',
};

export function certificadoQualidadeStatusBadge(status?: string | null): StatusBadgePair {
  const s = (status || '').toLowerCase().trim();
  if (s === 'rascunho') return { label: 'Rascunho', className: 'erp-badge-warning' };
  if (s === 'emitido') return { label: 'Emitido', className: 'erp-badge-success' };
  if (s === 'cancelado') return { label: 'Cancelado', className: 'erp-badge-danger' };
  if (!status) return unknownBadge;
  return { label: status, className: 'erp-badge-info' };
}

export function certificadoFornecedorStatusBadge(status?: string | null): StatusBadgePair {
  const s = (status || '').toLowerCase().trim();
  if (s === 'rascunho') return { label: 'Rascunho', className: 'erp-badge-warning' };
  if (s === 'registrado') return { label: 'Registrado', className: 'erp-badge-success' };
  if (s === 'cancelado') return { label: 'Cancelado', className: 'erp-badge-danger' };
  if (!status) return unknownBadge;
  return { label: status, className: 'erp-badge-info' };
}

export type RastreabilidadeCqStatus = 'COMPLETA' | 'PARCIAL' | 'PENDENTE';

export function rastreabilidadeCqBadge(status?: RastreabilidadeCqStatus | string | null): StatusBadgePair {
  const s = (status || '').toUpperCase().trim();
  if (s === 'COMPLETA') return { label: 'Rastreabilidade completa', className: 'erp-badge-success' };
  if (s === 'PARCIAL') return { label: 'Rastreabilidade parcial', className: 'erp-badge-warning' };
  if (s === 'PENDENTE') return { label: 'Rastreabilidade pendente', className: 'erp-badge-danger' };
  return unknownBadge;
}

export function rastreabilidadeCqResumoLabel(resumo?: {
  pode_emitir?: boolean;
  pendentes?: number;
  parciais?: number;
} | null): string {
  if (!resumo) return 'Rastreabilidade pendente';
  if (resumo.pode_emitir) return 'Rastreabilidade completa';
  if ((resumo.pendentes ?? 0) > 0) return 'Rastreabilidade pendente';
  if ((resumo.parciais ?? 0) > 0) return 'Rastreabilidade parcial';
  return 'Rastreabilidade pendente';
}

/**
 * Origem documental do item do CQ — apresentação separada da prontidão técnica.
 * Classificação conservadora usando somente campos já expostos pela API:
 * IDs de origem documental (CF), snapshots de corrida/lote gravados ao aplicar
 * uma origem e códigos de motivo. Texto digitado manualmente no campo corrida
 * NÃO comprova origem documental. Este indicador não comprova a origem física
 * consumida em estoque/alocação (lacuna registrada para a Fase 2).
 */
export type OrigemFisicaCqStatus = 'CONFIRMADA' | 'PARCIAL' | 'NAO_CONFIRMADA' | 'MANUAL';

export interface ItemOrigemFisicaCq {
  incluir_no_certificado?: boolean;
  corrida?: string;
  lote?: string;
  corrida_snapshot?: string;
  lote_snapshot?: string;
  norma?: string;
  certificado_fornecedor_origem_id?: number | null;
  item_certificado_fornecedor_origem_id?: number | null;
  tem_certificado_fornecedor?: boolean;
  rastreabilidade_motivos?: string[];
  rastreabilidade_avisos?: string[];
}

/** Vínculo documental já exposto pela API (CF de origem ou flag do backend). */
export function itemCqTemOrigemDocumental(item: ItemOrigemFisicaCq): boolean {
  return Boolean(
    item.tem_certificado_fornecedor
    || item.certificado_fornecedor_origem_id
    || item.item_certificado_fornecedor_origem_id,
  );
}

export function origemFisicaCqItem(item: ItemOrigemFisicaCq): OrigemFisicaCqStatus {
  const origemDocumental = itemCqTemOrigemDocumental(item);
  const marcadoManual = item.rastreabilidade_motivos?.includes('CF_NAO_VINCULADO_MANUAL') ?? false;
  if (!origemDocumental || marcadoManual) {
    const dadosDigitados = Boolean(
      (item.corrida || '').trim() || (item.lote || '').trim() || (item.norma || '').trim(),
    );
    return dadosDigitados ? 'MANUAL' : 'NAO_CONFIRMADA';
  }
  const corridaLoteDaOrigem = Boolean(
    (item.corrida_snapshot || '').trim() || (item.lote_snapshot || '').trim(),
  );
  if (!corridaLoteDaOrigem) return 'PARCIAL';
  return (item.rastreabilidade_avisos?.length ?? 0) > 0 ? 'PARCIAL' : 'CONFIRMADA';
}

/** Agregado dos itens incluídos; sem dado confiável, retorna NAO_CONFIRMADA. */
export function origemFisicaCqResumo(itens: ItemOrigemFisicaCq[]): OrigemFisicaCqStatus {
  const incluidos = itens.filter((it) => it.incluir_no_certificado !== false);
  if (!incluidos.length) return 'NAO_CONFIRMADA';
  const status = incluidos.map(origemFisicaCqItem);
  if (status.every((s) => s === 'CONFIRMADA')) return 'CONFIRMADA';
  if (status.some((s) => s === 'CONFIRMADA' || s === 'PARCIAL')) return 'PARCIAL';
  if (status.some((s) => s === 'MANUAL')) return 'MANUAL';
  return 'NAO_CONFIRMADA';
}

export function origemFisicaCqBadge(status: OrigemFisicaCqStatus): StatusBadgePair {
  if (status === 'CONFIRMADA') return { label: 'Origem documental confirmada', className: 'erp-badge-success' };
  if (status === 'PARCIAL') return { label: 'Origem documental parcial', className: 'erp-badge-warning' };
  if (status === 'MANUAL') return { label: 'Origem manual', className: 'erp-badge-info' };
  return { label: 'Origem documental não confirmada', className: 'erp-badge bg-muted/80 text-muted-foreground' };
}

export function origemFisicaCqDescricao(status: OrigemFisicaCqStatus): string {
  if (status === 'CONFIRMADA') {
    return 'Todos os itens incluídos possuem origem documental vinculada com corrida/lote identificado.';
  }
  if (status === 'PARCIAL') {
    return 'Há itens com origem vinculada, mas com corrida/lote não identificado ou avisos pendentes.';
  }
  if (status === 'MANUAL') {
    return 'Os dados técnicos/corrida foram informados manualmente e não possuem origem documental comprovada.';
  }
  return 'Não existe origem documental suficiente para confirmar a origem dos itens.';
}
