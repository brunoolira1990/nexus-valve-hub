import { badgeNfeSaidaStatus, isAutorizadaHomologacao } from '@/lib/nfeSaidaUi';
import type { HistoricoNfeSaidaPedido, ResumoFaturamentoPedido } from '@/types';
import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';

export type FaturamentoNfeLinha = ResumoFaturamentoPedido['faturamentos_nfe'][number];

/** Bloqueia apenas vínculos NF-e quebrados ou faturado acima do total — não aviso de total desatualizado. */
export function resumoBloqueiaGeracaoNfe(resumo: ResumoFaturamentoPedido): boolean {
  if (resumo.tem_inconsistencia_bloqueante_nfe != null) {
    return resumo.tem_inconsistencia_bloqueante_nfe;
  }
  const codigosBloqueantes = new Set([
    'fat_gerado_nfe_sem_vinculo',
    'fat_vinculo_orfao',
    'valor_faturado_excede_pedido',
  ]);
  return (resumo.inconsistencias ?? []).some((i) => codigosBloqueantes.has(i.codigo));
}

const LABELS_FATURAMENTO: Record<string, string> = {
  RASCUNHO: 'Rascunho',
  PRONTO_PARA_NFE: 'Pronto para NF-e',
  GERADO_NFE: 'NF-e gerada',
  PENDENTE_GERACAO: 'Pendente de geração',
  ERRO_TRANSMISSAO: 'Erro de transmissão',
};

const LABELS_EMISSAO_SEFAZ: Record<string, string> = {
  AUTORIZADA_HOMOLOGACAO: 'Autorizada em homologação',
  AUTORIZADA_PRODUCAO: 'Autorizada em produção',
  AUTORIZADA: 'Autorizada',
  REJEITADA_HOMOLOGACAO: 'Rejeitada',
  REJEITADA: 'Rejeitada',
  CANCELADA: 'Cancelada',
  ERRO_TRANSMISSAO: 'Erro de transmissão',
  RASCUNHO: 'Rascunho',
};

export function getFaturamentoStatusLabel(status: string | undefined | null): string {
  const s = (status || '').trim().toUpperCase();
  if (!s) return '—';
  return LABELS_FATURAMENTO[s] || s.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

export function getNfeEmissaoSefazLabel(
  status: string | undefined | null,
  nfeSaidaStatus?: string | undefined | null,
): string {
  if (isNfeCanceladaOperacional({ nfe_saida_status: nfeSaidaStatus })) {
    return 'Cancelada SEFAZ';
  }
  const s = (status || '').trim().toUpperCase();
  if (!s) return '';
  return LABELS_EMISSAO_SEFAZ[s] || getFaturamentoStatusLabel(s);
}

export function isNfeCanceladaOperacional(linha: {
  nfe_saida_status?: string | null;
}): boolean {
  const st = (linha.nfe_saida_status || '').trim().toUpperCase();
  return (
    st === 'CANCELADA_PRODUCAO' ||
    st === 'CANCELADA_HOMOLOGACAO' ||
    st === 'CANCELADA_INTERNA' ||
    st === 'CANCELADA' ||
    st === 'CANCELADO' ||
    st.includes('CANCELADA')
  );
}

export function formatNFeTitulo(linha: {
  nfe_titulo_exibicao?: string;
  nfe_numero_fiscal?: string;
  nfe_serie_fiscal?: string;
  nfe_status_emissao_sefaz?: string;
  nfe_saida_status?: string;
  nfe_saida_numero?: string;
}): string {
  if (linha.nfe_titulo_exibicao?.trim()) return linha.nfe_titulo_exibicao.trim();
  const st = (linha.nfe_saida_status || '').trim().toUpperCase();
  if (isNfeCanceladaOperacional({ nfe_saida_status: st })) {
    const n = linha.nfe_numero_fiscal?.trim();
    const serie = linha.nfe_serie_fiscal?.trim();
    return n
      ? `NF-e cancelada nº ${n}${serie ? ` — Série ${serie}` : ''}`
      : 'NF-e cancelada';
  }
  const sefaz = (linha.nfe_status_emissao_sefaz || '').trim().toUpperCase();
  const n = linha.nfe_numero_fiscal?.trim();
  const serie = linha.nfe_serie_fiscal?.trim();
  if (sefaz === 'AUTORIZADA_HOMOLOGACAO' && n) {
    return `NF-e Homologação nº ${n}${serie ? ` — Série ${serie}` : ''}`;
  }
  if ((sefaz === 'AUTORIZADA' || sefaz === 'AUTORIZADA_PRODUCAO') && n) {
    return `NF-e autorizada nº ${n}${serie ? ` — Série ${serie}` : ''}`;
  }
  if (st === 'CANCELADA' || st === 'CANCELADA_INTERNA') return 'NF-e cancelada';
  if (st.includes('REJEIT')) return 'NF-e rejeitada';
  if (st === 'RASCUNHO' || !st) return 'NF-e em rascunho';
  return linha.nfe_saida_numero?.trim() || 'NF-e vinculada';
}

export type NfeResumoPedidoCaso =
  | 'nenhuma'
  | 'rascunho'
  | 'vinculada'
  | 'autorizada_homolog'
  | 'autorizada_producao'
  | 'rejeitada'
  | 'cancelada';

export function classificarNfeResumoPedido(linha: FaturamentoNfeLinha): NfeResumoPedidoCaso {
  if (!linha.nfe_saida_id) return 'nenhuma';
  const sefaz = (linha.nfe_status_emissao_sefaz || '').trim().toUpperCase();
  const st = (linha.nfe_saida_status || '').trim().toUpperCase();
  if (isNfeCanceladaOperacional(linha) || linha.nfe_cancelada_sefaz) return 'cancelada';
  if (sefaz === 'AUTORIZADA_HOMOLOGACAO' || st === 'AUTORIZADA_HOMOLOGACAO') return 'autorizada_homolog';
  if (sefaz === 'AUTORIZADA_PRODUCAO' || st === 'AUTORIZADA') return 'autorizada_producao';
  if (st.includes('REJEIT') || sefaz.includes('REJEIT')) return 'rejeitada';
  if (st === 'RASCUNHO' || !sefaz) return 'rascunho';
  return 'vinculada';
}

/** Tokens para `StatusBadge` (design-system). */
export function getNFeFiscalBadgeTokens(linha: {
  nfe_status_emissao_sefaz?: string;
  nfe_saida_status?: string;
  nfe_cancelada_sefaz?: boolean;
}): string[] {
  const sefaz = (linha.nfe_status_emissao_sefaz || '').trim().toUpperCase();
  const st = (linha.nfe_saida_status || '').trim().toUpperCase();
  const tokens: string[] = [];

  if (isNfeCanceladaOperacional(linha) || linha.nfe_cancelada_sefaz) {
    tokens.push('cancelada');
    return tokens;
  }
  if (sefaz === 'AUTORIZADA_HOMOLOGACAO' || st === 'AUTORIZADA_HOMOLOGACAO') {
    tokens.push('homologacao', 'autorizada_homologacao', 'sem_valor_fiscal', 'fora_apuracao');
    return tokens;
  }
  if (sefaz === 'AUTORIZADA_PRODUCAO' || st === 'AUTORIZADA') {
    tokens.push('producao', 'autorizada', 'apura');
    return tokens;
  }
  if (st.includes('REJEIT') || sefaz.includes('REJEIT')) {
    tokens.push('rejeitada_homologacao');
    return tokens;
  }
  if (st === 'RASCUNHO' || !sefaz) {
    tokens.push('rascunho');
  }
  return tokens;
}

export function tituloResumoNfePedido(linha: FaturamentoNfeLinha): string {
  const caso = classificarNfeResumoPedido(linha);
  if (caso === 'nenhuma') return 'Nenhuma NF-e gerada';
  if (caso === 'rascunho') return 'NF-e em rascunho';
  if (caso === 'rejeitada') return 'NF-e rejeitada';
  if (caso === 'cancelada') return 'NF-e cancelada';
  return formatNFeTitulo(linha);
}

export function referenciaInternaNfe(linha: FaturamentoNfeLinha): string | null {
  const num = (linha.nfe_saida_numero || '').trim();
  if (/^RASCUNHO-FAT/i.test(num)) return num;
  const caso = classificarNfeResumoPedido(linha);
  if (
    num &&
    (caso === 'autorizada_homolog' || caso === 'autorizada_producao' || caso === 'vinculada') &&
    num !== formatNFeTitulo(linha)
  ) {
    return num;
  }
  return null;
}

export function faturamentoIndicaNfeGerada(status: string | undefined | null): boolean {
  return (status || '').trim().toUpperCase() === 'GERADO_NFE';
}

export function mensagemNfeFaturamentoInconsistencia(f: FaturamentoNfeLinha): string | null {
  if (faturamentoIndicaNfeGerada(f.status) && !f.nfe_saida_id) {
    return 'Status do faturamento indica NF-e gerada, mas nenhuma NF-e vinculada foi localizada. Verifique o histórico.';
  }
  return null;
}

export function linhaFaturamentoNfeAmigavel(f: FaturamentoNfeLinha): string {
  const numFat = f.numero_faturamento || `#${f.faturamento_id}`;
  if (!f.nfe_saida_id) {
    if (faturamentoIndicaNfeGerada(f.status)) {
      return `${numFat} — NF-e gerada (verificar vínculo)`;
    }
    return `${numFat} — ${getFaturamentoStatusLabel(f.status)}`;
  }
  const caso = classificarNfeResumoPedido(f);
  if (caso === 'autorizada_homolog') {
    return `${numFat} — NF-e autorizada em homologação`;
  }
  if (caso === 'autorizada_producao') {
    return `${numFat} — NF-e autorizada`;
  }
  if (caso === 'cancelada') {
    return `${numFat} — NF-e cancelada (sem validade fiscal)`;
  }
  if (caso === 'rascunho') {
    return `${numFat} — NF-e em rascunho`;
  }
  return `${numFat} — ${formatNFeTitulo(f)}`;
}

export function pedidoComercialFaturado(status: string | undefined | null): boolean {
  return (status || '').trim().toUpperCase() === 'FATURADO';
}

export function pedidoFaturadoSemAtendimento(
  pedidoStatus: string | undefined | null,
  resumo?: ResumoAtendimentoOperacional | null,
): boolean {
  if (!pedidoComercialFaturado(pedidoStatus)) return false;
  if (!resumo) return true;
  return !resumo.tem_alocacao;
}

export const MSG_ATENDIMENTO_NAO_DEFINIDO =
  'Atendimento operacional ainda não definido. Use esta seção para informar retirada no fornecedor, entrega direta, entrada pendente ou entrada conciliada.';

export const MSG_PEDIDO_FATURADO_SEM_ATENDIMENTO =
  'Pedido faturado sem atendimento operacional definido. Esta informação é importante para acompanhamento, mas não bloqueia a operação.';

export const MSG_ALERTA_FATURAMENTO_SEM_ATENDIMENTO =
  'Pedido faturado sem atendimento operacional definido. Defina retirada no fornecedor, entrega direta, entrada pendente ou entrada conciliada para melhorar o acompanhamento.';

export function isPedidoTabEditable(
  tab: string,
  pedidoStatus: string | undefined | null,
  isNovoPedido: boolean,
): boolean {
  if (isNovoPedido) return tab !== 'faturamento' && tab !== 'atendimento' && tab !== 'fiscal';
  if (tab === 'historico') return true;
  if (tab === 'faturamento' || tab === 'atendimento' || tab === 'fiscal') return false;
  const bloqueado = pedidoComercialFaturado(pedidoStatus);
  if (tab === 'itens' || tab === 'resumo') return !bloqueado;
  return false;
}

export type PedidoModalFooterConfig = {
  primaryLabel: string;
  primaryKind: 'save' | 'close';
  showPedidoPdf: boolean;
};

export function getPedidoModalFooterActions(
  activeTab: string,
  opts: { pedidoId?: number; pedidoStatus: string; isNovoPedido: boolean },
): PedidoModalFooterConfig {
  const showPedidoPdf = Boolean(opts.pedidoId);
  if (activeTab === 'historico' && opts.pedidoId) {
    return { primaryLabel: 'Salvar observações', primaryKind: 'save', showPedidoPdf };
  }
  if (!isPedidoTabEditable(activeTab, opts.pedidoStatus, opts.isNovoPedido)) {
    return { primaryLabel: 'Fechar', primaryKind: 'close', showPedidoPdf };
  }
  return { primaryLabel: 'Salvar', primaryKind: 'save', showPedidoPdf };
}

export function badgeHistoricoNfe(h: HistoricoNfeSaidaPedido) {
  return badgeNfeSaidaStatus(h.status);
}

export function getHistoricoNfePapelBadge(
  papel: HistoricoNfeSaidaPedido['papel_fiscal'],
): string | null {
  if (papel === 'ativa') return 'autorizada';
  if (papel === 'historico') return 'cancelada';
  if (papel === 'pendente') return 'rascunho';
  if (papel === 'rejeitada') return 'rejeitada_homologacao';
  return null;
}

export function classificarHistoricoNfePedido(h: HistoricoNfeSaidaPedido): NfeResumoPedidoCaso {
  if (isNfeCanceladaOperacional({ nfe_saida_status: h.status }) || h.papel_fiscal === 'historico') {
    return 'cancelada';
  }
  const sefaz = (h.status_emissao_sefaz || '').trim().toUpperCase();
  const st = (h.status || '').trim().toUpperCase();
  if (sefaz === 'AUTORIZADA_HOMOLOGACAO' || st === 'AUTORIZADA_HOMOLOGACAO') return 'autorizada_homolog';
  if (sefaz === 'AUTORIZADA_PRODUCAO' || st === 'AUTORIZADA' || h.papel_fiscal === 'ativa') {
    return 'autorizada_producao';
  }
  if (h.papel_fiscal === 'rejeitada' || st.includes('REJEIT') || sefaz.includes('REJEIT')) return 'rejeitada';
  return 'rascunho';
}

export function historicoNfeTitulo(h: HistoricoNfeSaidaPedido): string {
  if (h.titulo_exibicao?.trim()) return h.titulo_exibicao.trim();
  return formatNFeTitulo({
    nfe_titulo_exibicao: h.titulo_exibicao,
    nfe_numero_fiscal: h.numero_fiscal,
    nfe_serie_fiscal: h.serie_fiscal,
    nfe_status_emissao_sefaz: h.status_emissao_sefaz,
    nfe_saida_status: h.status,
    nfe_saida_numero: h.numero,
  });
}

export function nfeTemDanfeHomologacao(linha: {
  nfe_status_emissao_sefaz?: string;
  nfe_saida_status?: string;
}): boolean {
  return isAutorizadaHomologacao({
    status: linha.nfe_saida_status,
    resumo_emissao_sefaz: { status_emissao_sefaz: linha.nfe_status_emissao_sefaz },
  });
}

export type NFePedidoDisplay = {
  titulo: string;
  statusFiscalLabel: string;
  ambienteLabel: string;
  badges: string[];
  referenciaInterna: string | null;
  cstat: string;
  numero: string;
  serie: string;
};

/** Identidade fiscal unificada (modal + PDF frontend se aplicável). */
export function formatNFePedidoDisplay(linha: FaturamentoNfeLinha): NFePedidoDisplay {
  const caso = classificarNfeResumoPedido(linha);
  const badgesLabels: string[] = [];
  if (caso === 'autorizada_homolog') {
    badgesLabels.push('Homologação', 'Autorizada homologação', 'Sem valor fiscal', 'Fora da apuração');
  } else if (caso === 'autorizada_producao') {
    badgesLabels.push('Produção', 'Autorizada', 'Apura');
  } else if (caso === 'rejeitada') {
    badgesLabels.push('Rejeitada');
  } else if (caso === 'cancelada') {
    badgesLabels.push('Cancelada');
  } else if (caso === 'rascunho') {
    badgesLabels.push('Rascunho');
  }
  return {
    titulo: tituloResumoNfePedido(linha),
    statusFiscalLabel: getNfeEmissaoSefazLabel(
      linha.nfe_status_emissao_sefaz || linha.nfe_saida_status,
      linha.nfe_saida_status,
    ),
    ambienteLabel:
      linha.nfe_status_emissao_sefaz === 'AUTORIZADA_HOMOLOGACAO' ? 'Homologação' : '',
    badges: badgesLabels,
    referenciaInterna: referenciaInternaNfe(linha),
    cstat: (linha.nfe_cstat || '').trim(),
    numero: (linha.nfe_numero_fiscal || '').trim(),
    serie: (linha.nfe_serie_fiscal || '').trim(),
  };
}

export function getStatusItemLabel(status: string | undefined | null): string {
  const s = (status || '').trim().toUpperCase();
  const map: Record<string, string> = {
    PENDENTE: 'Pendente',
    PARCIAL: 'Parcial',
    FATURADO: 'Faturado',
    CANCELADO: 'Cancelado',
  };
  return map[s] || s || 'Pendente';
}

export function tokenStatusComercialPedido(status: string | undefined | null): string {
  const s = (status || '').trim().toUpperCase();
  if (s === 'FATURADO') return 'faturado';
  if (s === 'PARCIALMENTE_FATURADO' || s === 'PARCIAL') return 'parcialmente_faturado';
  if (s === 'EM_FATURAMENTO') return 'em_faturamento';
  return 'pendente_faturamento';
}
