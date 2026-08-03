import type { NFeEntrada, NFeEntradaStatusOperacional } from '@/types';

const STATUS_OPERACIONAL_LABEL: Record<string, string> = {
  RASCUNHO: 'Rascunho',
  EM_CONFERENCIA: 'Em conferência',
  PRONTA_HOMOLOGACAO: 'Pronta homologação',
  AUTORIZADA_HOMOLOGACAO: 'Autorizada homologação',
  PRONTA_PRODUCAO: 'Pronta produção',
  AUTORIZADA_PRODUCAO: 'Autorizada produção',
  REJEITADA: 'Rejeitada',
  ERRO_TRANSMISSAO: 'Erro transmissão',
  IMPORTADA_PENDENTE_CONFERENCIA: 'Pendente conferência',
};

/** Label amigável para badge — nunca exibe enum cru na UI principal. */
export function labelStatusOperacionalNfeEntrada(
  status?: NFeEntradaStatusOperacional | string | null,
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
    return e.tipo_origem_label || 'Entrada própria importada';
  }
  if (e.tipo_origem === 'ENTRADA_PROPRIA_EMITIDA') {
    return e.tipo_origem_label || 'Entrada própria emitida';
  }
  return 'Manual';
}

/** Entrada própria operacional 4.0.14 — revisão visual read-only, sem conferência completa. */
export function exibirAcaoRevisarDados(e: Pick<NFeEntrada, 'tipo_origem'>): boolean {
  return e.tipo_origem === 'ENTRADA_PROPRIA_IMPORTADA';
}

export function exibirPainelEmissaoEntrada(e: Pick<NFeEntrada, 'tipo_origem'>): boolean {
  return e.tipo_origem === 'ENTRADA_PROPRIA_EMITIDA';
}

export function emitenteDestinatarioLabelNfeEntrada(nfe: NFeEntrada): string {
  if (nfe.tipo_origem === 'ENTRADA_PROPRIA_IMPORTADA' || nfe.tipo_origem === 'ENTRADA_PROPRIA_EMITIDA') {
    return nfe.destinatario_nome
      ? `${nfe.fornecedor_nome || 'Emitente'} → ${nfe.destinatario_nome}`
      : nfe.fornecedor_nome || nfe.destinatario_nome || '—';
  }
  return nfe.fornecedor_nome;
}
