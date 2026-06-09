/** Formatação amigável — NF-e Saída (listagem compacta e drawer). */

import type { NFeSaidaListItem, NFeSaidaListagemResumo } from '@/types';
import { formatCurrencyBRL } from '@/lib/formatBr';
import { formatDateBr } from '@/lib/dateBr';

export { formatCurrencyBRL, formatDateBr };

const STATUS_LABELS: Record<string, string> = {
  AUTORIZADA_HOMOLOGACAO: 'Autorizada em homologação',
  AUTORIZADA: 'Autorizada',
  AUTORIZADA_INTERNA: 'Autorizada (interna)',
  REJEITADA_HOMOLOGACAO: 'Rejeitada em homologação',
  REJEITADA: 'Rejeitada',
  CANCELADA: 'Cancelada',
  CANCELADA_INTERNA: 'Cancelada (interna)',
  CANCELADO: 'Cancelada',
  RASCUNHO: 'Rascunho',
  ERRO_TRANSMISSAO: 'Erro de transmissão',
  PENDENTE_GERACAO: 'Pendente de geração',
  PRONTA_PARA_EMISSAO: 'Pronta para emissão',
  EMITIDA: 'Emitida',
  EMITIDO: 'Emitido',
};

const AMBIENTE_LABELS: Record<string, string> = {
  homologacao: 'Homologação',
  producao: 'Produção',
  '1': 'Produção',
  '2': 'Homologação',
};

const REFERENCIA_INTERNA = /^RASCUNHO(-FAT)?/i;

export function formatStatusNfe(status: string | null | undefined): string {
  const key = (status || '').trim().toUpperCase();
  if (!key) return '—';
  return STATUS_LABELS[key] || status || '—';
}

export function formatAmbienteNfe(ambiente: string | null | undefined): string {
  const raw = (ambiente || '').trim().toLowerCase();
  if (!raw) return '—';
  return AMBIENTE_LABELS[raw] || ambiente || '—';
}

export function isReferenciaInternaRascunho(texto: string | null | undefined): boolean {
  return REFERENCIA_INTERNA.test((texto || '').trim());
}

export function formatNfeTituloListagem(
  item: {
    numero?: string | null;
    status?: string | null;
    status_emissao_sefaz?: string | null;
    listagem_resumo?: NFeSaidaListagemResumo | null;
  },
): string {
  const resumo = item.listagem_resumo;
  const titulo = resumo?.titulo?.trim();
  const fiscalBadge = (resumo?.fiscal_resumo?.badge || '').trim();
  const st = (item.status || '').trim().toUpperCase();
  const sefaz = (item.status_emissao_sefaz || '').trim();

  const homologAutorizada =
    fiscalBadge === 'Homologação autorizada' ||
    sefaz === 'AUTORIZADA_HOMOLOGACAO' ||
    st === 'AUTORIZADA_HOMOLOGACAO';

  if (homologAutorizada) {
    if (titulo && titulo.includes('Homologação')) return titulo;
    return 'NF-e Homologação autorizada';
  }

  if (titulo && titulo !== 'NF-e em rascunho') {
    if (!isReferenciaInternaRascunho(titulo) && titulo !== (item.numero || '').trim()) {
      return titulo;
    }
    if (titulo.includes('Homologação') || titulo.includes('Conferência') || titulo.includes('nº')) {
      return titulo;
    }
  }

  if (st === 'RASCUNHO' || isReferenciaInternaRascunho(item.numero)) {
    return 'NF-e em rascunho';
  }

  return titulo || item.numero || 'NF-e sem número fiscal';
}

export function formatNfeSubtituloListagem(item: Pick<NFeSaidaListItem, 'listagem_resumo'>): string {
  return (item.listagem_resumo?.subtitulo || '').trim();
}

export type AtendimentoBadgeResumo = { label: string; variant: string };

export function formatNfeAtendimentoResumo(
  resumo: NFeSaidaListagemResumo | undefined,
): { badges: AtendimentoBadgeResumo[]; ocultos: number; vazioLabel: string } {
  const raw = resumo?.atendimento_resumo;
  const badges: AtendimentoBadgeResumo[] = (raw?.badges ?? []).map((b) => {
    if (typeof b === 'string') return { label: b, variant: 'neutral' };
    return { label: b.label, variant: b.variant || 'neutral' };
  });
  return {
    badges,
    ocultos: raw?.ocultos ?? 0,
    vazioLabel: raw?.vazio_label || 'Atendimento não definido',
  };
}

export function formatNfeValorListagem(valor: number | string | null | undefined): string {
  return formatCurrencyBRL(valor);
}
