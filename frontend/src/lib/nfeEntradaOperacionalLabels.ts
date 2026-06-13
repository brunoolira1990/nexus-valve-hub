import type { NFeEntrada, NFeEntradaStatusOperacional } from '@/types';

const STATUS_OPERACIONAL_LABEL: Record<NFeEntradaStatusOperacional, string> = {
  RASCUNHO: 'Rascunho',
  IMPORTADA_PENDENTE_CONFERENCIA: 'Pendente conferência',
};

/** Label amigável para badge — nunca exibe enum cru na UI principal. */
export function labelStatusOperacionalNfeEntrada(
  status?: NFeEntradaStatusOperacional | null,
  fallbackLabel?: string | null,
): string {
  if (status && STATUS_OPERACIONAL_LABEL[status]) {
    return STATUS_OPERACIONAL_LABEL[status];
  }
  const fb = (fallbackLabel || '').trim();
  if (!fb) return '—';
  if (fb.includes('pendente conferência') || fb.includes('pendente conferencia')) {
    return 'Pendente conferência';
  }
  if (fb.toLowerCase().includes('rascunho')) return 'Rascunho';
  return fb;
}

export function labelTipoOrigemNfeEntrada(e: Pick<NFeEntrada, 'tipo_origem' | 'tipo_origem_label'>): string {
  if (e.tipo_origem === 'ENTRADA_PROPRIA_IMPORTADA') {
    return e.tipo_origem_label || 'Entrada própria';
  }
  return 'Manual';
}

/** Entrada própria operacional 4.0.14 — revisão visual read-only, sem conferência completa. */
export function exibirAcaoRevisarDados(e: Pick<NFeEntrada, 'tipo_origem'>): boolean {
  return e.tipo_origem === 'ENTRADA_PROPRIA_IMPORTADA';
}

export function emitenteDestinatarioLabelNfeEntrada(nfe: NFeEntrada): string {
  if (nfe.tipo_origem === 'ENTRADA_PROPRIA_IMPORTADA') {
    return nfe.destinatario_nome
      ? `${nfe.fornecedor_nome} → ${nfe.destinatario_nome}`
      : nfe.fornecedor_nome;
  }
  return nfe.fornecedor_nome;
}
