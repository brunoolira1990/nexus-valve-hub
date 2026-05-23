import type { NFeSaida } from '@/types';

const STATUS_NFE_FINALIZADA = new Set([
  'AUTORIZADA_INTERNA',
  'AUTORIZADA',
  'EMITIDA',
  'EMITIDO',
  'CANCELADA_INTERNA',
  'CANCELADA',
  'CANCELADO',
]);

/** NF-e já emitida/autorizada/cancelada — não salvar via formulário genérico. */
export function nfeItensComerciaisEditaveis(
  nfe: Pick<NFeSaida, 'itens_comerciais_editaveis' | 'origem_comercial_travada'> | null,
  status: string | undefined | null,
): boolean {
  if (nfe?.itens_comerciais_editaveis !== undefined) return Boolean(nfe.itens_comerciais_editaveis);
  if (nfe?.origem_comercial_travada) return false;
  return (status || '').trim().toUpperCase() === 'RASCUNHO';
}

export function nfeDadosComplementaresEditaveis(
  nfe: Pick<NFeSaida, 'dados_complementares_editaveis'> | null,
  status: string | undefined | null,
): boolean {
  if (nfe?.dados_complementares_editaveis !== undefined) {
    return Boolean(nfe.dados_complementares_editaveis);
  }
  return (status || '').trim().toUpperCase() === 'RASCUNHO';
}

export function nfeSalvarFormularioBloqueado(status: string | undefined | null): boolean {
  const st = (status || '').trim().toUpperCase();
  return STATUS_NFE_FINALIZADA.has(st);
}

/** Pedido com status FATURADO — itens somente leitura. */
export function pedidoItensBloqueados(status: string | undefined | null): boolean {
  return (status || '').trim().toUpperCase() === 'FATURADO';
}

export function itemPedidoPrecoProdutoBloqueado(
  item: { status_item?: string; quantidade_faturada?: number },
  pedidoStatus: string | undefined | null,
): boolean {
  if (pedidoItensBloqueados(pedidoStatus)) return true;
  const st = (item.status_item || '').trim().toUpperCase();
  if (st === 'FATURADO') return true;
  const qFat = Number(item.quantidade_faturada ?? 0);
  return qFat > 0;
}

export function itemPedidoReadOnly(
  item: { status_item?: string; quantidade_faturada?: number },
  pedidoStatus: string | undefined | null,
): boolean {
  return itemPedidoPrecoProdutoBloqueado(item, pedidoStatus);
}

export function itemPedidoPodeExcluir(
  item: { quantidade_faturada?: number },
  pedidoStatus: string | undefined | null,
): boolean {
  if (pedidoItensBloqueados(pedidoStatus)) return false;
  const qFat = Number(item.quantidade_faturada ?? 0);
  return Number.isFinite(qFat) && qFat <= 0;
}

/** NF-e originada de faturamento/pedido — cliente herdado, não editável. */
export function nfeClienteBloqueado(
  nfe: Pick<NFeSaida, 'faturamento_pedido_venda_id' | 'pedido_venda_id'> | null,
): boolean {
  if (!nfe) return false;
  return Boolean(nfe.faturamento_pedido_venda_id || nfe.pedido_venda_id);
}

const LABELS_MODO_ATENDIMENTO: Record<string, string> = {
  IMEDIATO: 'Imediato',
  ANTECIPADO: 'Antecipado',
};

export function labelModoAtendimentoEstoque(modo: string | undefined | null): string {
  const key = (modo || '').trim().toUpperCase();
  if (!key) return '—';
  return LABELS_MODO_ATENDIMENTO[key] ?? modo ?? '—';
}

const LABELS_STATUS_NFE: Record<string, string> = {
  RASCUNHO: 'Rascunho',
  AUTORIZADA_INTERNA: 'Autorizada (interna)',
  CANCELADA_INTERNA: 'Cancelada (interna)',
  EMITIDA: 'Emitida',
  EMITIDO: 'Emitido',
  AUTORIZADA: 'Autorizada',
  CANCELADA: 'Cancelada',
};

export function badgeNfeSaidaStatus(status: string | undefined | null): { label: string; className: string } {
  const st = (status || '').trim().toUpperCase();
  const label = LABELS_STATUS_NFE[st] || status || '—';
  if (st === 'AUTORIZADA_INTERNA' || st === 'EMITIDA' || st === 'EMITIDO' || st === 'AUTORIZADA') {
    return { label, className: 'erp-badge-success' };
  }
  if (st === 'CANCELADA_INTERNA' || st === 'CANCELADA' || st === 'CANCELADO') {
    return { label, className: 'erp-badge-danger' };
  }
  if (st === 'RASCUNHO') {
    return { label, className: 'erp-badge-warning' };
  }
  return { label, className: 'erp-badge-warning' };
}

export function formatDateTimeBr(iso: string | undefined | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const LABELS_TIPO_EVENTO: Record<string, string> = {
  AUTORIZACAO_INTERNA: 'Autorização interna',
  CANCELAMENTO_INTERNO: 'Cancelamento interno',
  GERACAO_RASCUNHO: 'Geração de rascunho',
  IMPOSTOS_ATUALIZADOS: 'Impostos atualizados',
  RASCUNHO_CRIADO: 'Rascunho criado',
  VALIDADA: 'Validada',
  AUTORIZACAO_EFEITOS_APLICADOS: 'Efeitos de autorização',
  CANCELAMENTO_EFEITOS_APLICADOS: 'Efeitos de cancelamento',
  CANCELADA: 'Cancelada',
  ESTORNO_FATURAMENTO: 'Estorno de faturamento',
  OBSERVACAO: 'Observação',
};

export function labelTipoEventoNFe(tipo: string): string {
  return LABELS_TIPO_EVENTO[tipo] || tipo.replace(/_/g, ' ');
}

export function resumoEventoCurto(resumo: Record<string, unknown> | null | undefined): string {
  if (!resumo || typeof resumo !== 'object') return '';
  const parts: string[] = [];
  if (resumo.mensagem) parts.push(String(resumo.mensagem));
  if (resumo.pedido_id) parts.push(`Pedido #${resumo.pedido_id}`);
  if (resumo.faturamento_id) parts.push(`Faturamento #${resumo.faturamento_id}`);
  return parts.join(' · ');
}
