import type { NFeSaida } from '@/types';

const STATUS_NFE_FINALIZADA = new Set([
  'AUTORIZADA_INTERNA',
  'AUTORIZADA',
  'AUTORIZADA_HOMOLOGACAO',
  'EMITIDA',
  'EMITIDO',
  'CANCELADA_INTERNA',
  'CANCELADA',
  'CANCELADO',
]);

export type ResumoEmissaoSefazNfe = {
  status_emissao_sefaz?: string;
  serie_nfe?: string;
  numero_nfe?: string;
  ambiente_emissao?: string;
  nfe?: { cstat?: string; xmotivo?: string; protocolo?: string };
  lote?: { cstat?: string; xmotivo?: string };
};

export type NFeSaidaApresentacao = {
  numero_interno?: string;
  origem_operacional?: string;
  numero_faturamento?: string;
  numero_pedido_venda?: string;
  numero_pedido_cliente?: string;
  numero_fiscal?: string;
  serie_fiscal?: string;
  chave_acesso?: string;
  protocolo_autorizacao?: string;
  ambiente_emissao?: string;
  status_emissao_sefaz?: string;
  status_conferencia?: string;
  titulo_exibicao?: string;
  subtitulo_exibicao?: string;
  linhas_subtitulo?: string[];
  badge_principal?: { label: string; tipo: string };
  badges_secundarios?: Array<{ label: string; tipo: string }>;
  autorizada_homologacao?: boolean;
  modo_leitura?: boolean;
  cancelada_interna?: boolean;
  ocultar_status_conferencia_listagem?: boolean;
  listagem_titulo?: string;
  listagem_subtitulo?: string;
};

export function tituloListagemNfe(nfe: {
  numero?: string | null;
  apresentacao?: NFeSaidaApresentacao | null;
}): string {
  const ap = nfe.apresentacao;
  if (ap?.listagem_titulo) return ap.listagem_titulo;
  if (ap?.titulo_exibicao) return ap.titulo_exibicao;
  return (nfe.numero || '').trim() || '—';
}

export function subtituloListagemNfe(nfe: {
  apresentacao?: NFeSaidaApresentacao | null;
}): string {
  return (nfe.apresentacao?.listagem_subtitulo || nfe.apresentacao?.subtitulo_exibicao || '').trim();
}

export function nfeModoLeitura(nfe: {
  status?: string | null;
  apresentacao?: NFeSaidaApresentacao | null;
  resumo_emissao_sefaz?: ResumoEmissaoSefazNfe | null;
}): boolean {
  if (nfe.apresentacao?.modo_leitura) return true;
  return isAutorizadaHomologacao(nfe);
}

export function isCanceladaInterna(nfe: { status?: string | null; apresentacao?: NFeSaidaApresentacao | null }): boolean {
  if (nfe.apresentacao?.cancelada_interna) return true;
  const st = (nfe.status || '').trim().toUpperCase();
  return st === 'CANCELADA_INTERNA' || st === 'CANCELADA' || st === 'CANCELADO';
}

export function deveExibirStatusConferenciaListagem(nfe: {
  status?: string | null;
  status_conferencia?: string | null;
  apresentacao?: NFeSaidaApresentacao | null;
  resumo_emissao_sefaz?: ResumoEmissaoSefazNfe | null;
}): boolean {
  if (nfe.apresentacao?.ocultar_status_conferencia_listagem) return false;
  if (isAutorizadaHomologacao(nfe)) return false;
  if (isCanceladaInterna(nfe)) return false;
  return Boolean((nfe.status_conferencia || '').trim());
}

export function isAutorizadaHomologacao(
  nfe: { status?: string | null; resumo_emissao_sefaz?: ResumoEmissaoSefazNfe | null },
  emissaoSefaz?: ResumoEmissaoSefazNfe | null,
): boolean {
  const st = (emissaoSefaz?.status_emissao_sefaz ?? nfe.resumo_emissao_sefaz?.status_emissao_sefaz ?? '').trim();
  if (st === 'AUTORIZADA_HOMOLOGACAO') return true;
  return (nfe.status || '').trim().toUpperCase() === 'AUTORIZADA_HOMOLOGACAO';
}

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

const STATUS_PEDIDO_ITENS_BLOQUEADOS = new Set(['FATURADO', 'CANCELADO']);

/** Pedido faturado/cancelado — itens somente leitura. */
export function pedidoItensBloqueados(status: string | undefined | null): boolean {
  return STATUS_PEDIDO_ITENS_BLOQUEADOS.has((status || '').trim().toUpperCase());
}

export const MSG_PEDIDO_FATURADO_ITENS =
  'Pedido faturado. Itens bloqueados para preservar histórico de faturamento e NF-e.';

/** Quantidade editável enquanto pedido aberto e item sem bloqueio de faturamento total. */
export function itemPedidoQuantidadeEditavel(
  item: { status_item?: string; quantidade_faturada?: number },
  pedidoStatus: string | undefined | null,
): boolean {
  if (pedidoItensBloqueados(pedidoStatus)) return false;
  const st = (item.status_item || '').trim().toUpperCase();
  if (st === 'FATURADO' || st === 'CANCELADO') return false;
  return true;
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
  AUTORIZADA_HOMOLOGACAO: 'Autorizada homologação',
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
  if (
    st === 'AUTORIZADA_INTERNA' ||
    st === 'EMITIDA' ||
    st === 'EMITIDO' ||
    st === 'AUTORIZADA' ||
    st === 'AUTORIZADA_HOMOLOGACAO'
  ) {
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

export function badgeNfeSaidaEmissaoSefaz(
  resumo?: ResumoEmissaoSefazNfe | null,
): { label: string; className: string } | null {
  const st = (resumo?.status_emissao_sefaz || '').trim().toUpperCase();
  if (!st) return null;
  if (st === 'AUTORIZADA_HOMOLOGACAO') {
    return { label: 'Autorizada homologação', className: 'erp-badge-success' };
  }
  if (st === 'REJEITADA_HOMOLOGACAO') {
    return { label: 'Rejeitada homologação', className: 'erp-badge-danger' };
  }
  if (st === 'ERRO_TRANSMISSAO') {
    return { label: 'Erro transmissão', className: 'erp-badge-danger' };
  }
  return { label: st.replace(/_/g, ' '), className: 'erp-badge-warning' };
}

export function badgeNfeSaidaLinhaListagem(nfe: {
  status?: string | null;
  resumo_emissao_sefaz?: ResumoEmissaoSefazNfe | null;
  apresentacao?: NFeSaidaApresentacao | null;
}): { principal: { label: string; className: string }; secundario?: { label: string; className: string } } {
  if (isAutorizadaHomologacao(nfe)) {
    const ap = nfe.apresentacao;
    const resumo = nfe.resumo_emissao_sefaz;
    const rawCstat =
      resumo?.nfe?.cstat ||
      ap?.badges_secundarios?.find((b) => b.label.startsWith('cStat'))?.label?.replace('cStat ', '');
    const cstatLabel = rawCstat ? (String(rawCstat).startsWith('cStat') ? String(rawCstat) : `cStat ${rawCstat}`) : undefined;
    return {
      principal: {
        label: ap?.badge_principal?.label || 'Autorizada homologação',
        className: 'erp-badge-success',
      },
      secundario: cstatLabel ? { label: cstatLabel, className: 'erp-badge-success opacity-90 text-[10px]' } : undefined,
    };
  }
  if (isCanceladaInterna(nfe)) {
    const ap = nfe.apresentacao;
    const sec = ap?.badges_secundarios?.[0];
    return {
      principal: { label: ap?.badge_principal?.label || 'Cancelada interna', className: 'erp-badge-danger' },
      secundario: sec ? { label: sec.label, className: 'text-xs text-muted-foreground' } : undefined,
    };
  }
  return { principal: badgeNfeSaidaStatus(nfe.status) };
}

export function mensagemCabecalhoNfeAutorizadaHomolog(): string {
  return 'NF-e autorizada em homologação pela SEFAZ. Documento sem valor fiscal de produção.';
}

export function deveExibirMensagemProntaEmissao(
  statusConferencia: string | undefined,
  autorizadaHomolog: boolean,
): boolean {
  if (autorizadaHomolog) return false;
  return (statusConferencia || '').toUpperCase() === 'PRONTA_PARA_EMISSAO';
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
  ESTORNO_FATURAMENTO_PRE_AUTORIZACAO_NFE: 'Estorno antes da autorização SEFAZ',
  DESCARTE_RASCUNHO_NFE: 'Descarte interno de rascunho',
  OBSERVACAO: 'Observação',
  NFE_AUTORIZADA_HOMOLOGACAO: 'Autorizada homologação SEFAZ',
};

export function labelTipoEventoNFe(tipo: string): string {
  return LABELS_TIPO_EVENTO[tipo] || tipo.replace(/_/g, ' ');
}

const STATUS_NFE_DESCARTADA = 'DESCARTADA_INTERNA';

export function nfePodeDescartarRascunho(nfe: {
  status?: string | null;
  status_emissao_sefaz?: string | null;
  protocolo_autorizacao?: string | null;
  cstat_autorizacao?: string | null;
}): { pode: boolean; motivo: string } {
  const st = (nfe.status || '').toUpperCase();
  if (st === STATUS_NFE_DESCARTADA) {
    return { pode: false, motivo: 'NF-e já descartada internamente.' };
  }
  if (st === 'AUTORIZADA_HOMOLOGACAO' || (nfe.status_emissao_sefaz || '') === 'AUTORIZADA_HOMOLOGACAO') {
    return {
      pode: false,
      motivo: 'NF-e autorizada. Use fluxo fiscal de cancelamento (fase futura).',
    };
  }
  if ((nfe.protocolo_autorizacao || '').trim() || (nfe.cstat_autorizacao || '').trim() === '100') {
    return { pode: false, motivo: 'NF-e possui protocolo de autorização.' };
  }
  if (['EMITIDA', 'AUTORIZADA', 'AUTORIZADA_INTERNA', 'CANCELADA_INTERNA'].includes(st)) {
    return { pode: false, motivo: `Status ${nfe.status} não permite descarte interno.` };
  }
  return { pode: true, motivo: '' };
}

export function nfeRascunhoSemAutorizacao(nfe: {
  status?: string | null;
  status_emissao_sefaz?: string | null;
}): boolean {
  const st = (nfe.status || '').toUpperCase();
  if (st === STATUS_NFE_DESCARTADA) return false;
  return !['AUTORIZADA_HOMOLOGACAO', 'AUTORIZADA', 'EMITIDA', 'AUTORIZADA_INTERNA'].includes(st);
}

export function resumoEventoCurto(resumo: Record<string, unknown> | null | undefined): string {
  if (!resumo || typeof resumo !== 'object') return '';
  const parts: string[] = [];
  if (resumo.mensagem) parts.push(String(resumo.mensagem));
  if (resumo.pedido_id) parts.push(`Pedido #${resumo.pedido_id}`);
  if (resumo.faturamento_id) parts.push(`Faturamento #${resumo.faturamento_id}`);
  return parts.join(' · ');
}
