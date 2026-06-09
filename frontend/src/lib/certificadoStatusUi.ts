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
