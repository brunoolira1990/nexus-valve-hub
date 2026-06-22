/** Helpers — listagem compacta NF-e Saída (ERP 4.0.13.4.1). */

import type { NFeSaidaListagemResumo } from '@/types';
import { formatNfeAtendimentoResumo } from '@/lib/nfeSaidaApresentacaoFormat';

const VARIANT_CLASS: Record<string, string> = {
  success: 'erp-badge-success',
  warning: 'erp-badge-warning',
  danger: 'erp-badge-danger',
  info: 'erp-badge-info',
  neutral: 'erp-badge-warning',
};

export function fiscalResumoBadgeClass(variant: string | undefined): string {
  return VARIANT_CLASS[variant || 'neutral'] ?? 'erp-badge-warning';
}

export function atendimentoResumoBadgeClass(variant: string | undefined): string {
  return VARIANT_CLASS[variant || 'neutral'] ?? 'erp-badge-warning';
}

type ListItemFiscalFallback = {
  status?: string | null;
  status_emissao_sefaz?: string | null;
};

function deriveFiscalFromListItem(item: ListItemFiscalFallback | undefined) {
  const sefaz = (item?.status_emissao_sefaz || '').trim();
  const st = (item?.status || '').trim().toUpperCase();
  if (
    st === 'CANCELADA_PRODUCAO' ||
    st === 'CANCELADA_HOMOLOGACAO' ||
    st === 'CANCELADA_INTERNA' ||
    st === 'CANCELADA' ||
    st === 'CANCELADO'
  ) {
    return { badge: 'Cancelada', variant: 'danger', subtexto: '' };
  }
  if (sefaz === 'AUTORIZADA_HOMOLOGACAO' || st === 'AUTORIZADA_HOMOLOGACAO') {
    return {
      badge: 'Homologação autorizada',
      variant: 'warning',
      subtexto: '',
    };
  }
  if (st === 'RASCUNHO') {
    return { badge: 'Rascunho', variant: 'neutral', subtexto: '' };
  }
  if (sefaz === 'REJEITADA_HOMOLOGACAO') {
    return { badge: 'Rejeitada homologação', variant: 'danger', subtexto: '' };
  }
  if (sefaz === 'ERRO_TRANSMISSAO') {
    return { badge: 'Erro transmissão', variant: 'danger', subtexto: '' };
  }
  if (st) {
    return { badge: st.replace(/_/g, ' '), variant: 'neutral', subtexto: '' };
  }
  return null;
}

export function getNfeFiscalSummaryBadge(
  resumo: NFeSaidaListagemResumo | undefined,
  item?: ListItemFiscalFallback,
) {
  const f = resumo?.fiscal_resumo;
  const fallback = !f?.badge?.trim() ? deriveFiscalFromListItem(item) : null;
  const label = (f?.badge || fallback?.badge || '').trim();
  const variant = f?.variant || fallback?.variant;
  const subtexto = (f?.subtexto || fallback?.subtexto || '').trim();
  return {
    label: label || 'Pendente',
    className: fiscalResumoBadgeClass(variant),
    subtexto,
    hasData: Boolean(label),
  };
}

export function getNfeOperationalSummaryBadges(resumo: NFeSaidaListagemResumo | undefined) {
  return formatNfeAtendimentoResumo(resumo);
}

export function getNfeHiddenBadgesCount(resumo: NFeSaidaListagemResumo | undefined): number {
  return resumo?.atendimento_resumo?.ocultos ?? 0;
}

export function getNfeFiscalSummaryText(resumo: NFeSaidaListagemResumo | undefined): string {
  return resumo?.fiscal_resumo?.subtexto ?? '';
}
