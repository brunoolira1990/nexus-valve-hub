/**
 * View-model do Painel Interno V1 — derivado exclusivamente de snapshot_indicadores.
 * Não consulta APIs nem o relógio do navegador para recência.
 */

export const MSG_SEM_CICLOS_RECEBIMENTO =
  'Sem ciclos de recebimento registrados no Nexus. Pontualidade e comportamento de pagamento indisponíveis.';

export const MSG_DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT =
  'Informação de recebimentos não disponível neste snapshot.';

export const MSG_QUALIDADE_BASE =
  'Qualidade dos dados indica a confiabilidade da base utilizada e não representa aprovação de crédito.';

export type QualidadePainelV1 = 'INSUFICIENTE' | 'BAIXA' | 'MEDIA';

export type ComportamentoPagamentoCodigo =
  | 'SEM_CICLOS_RECEBIMENTO'
  | 'DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT'
  | 'METRICAS_DISPONIVEIS';

export type FonteComercialPainel =
  | 'NFE_SAIDA_PRODUCAO'
  | 'PEDIDO_VENDA'
  | 'INDISPONIVEL'
  | 'DESCONHECIDA';

type PeriodoBaixasSnap = {
  quantidade_baixas_analisadas?: number;
  pontualidade_quantidade?: { disponivel?: boolean; valor?: string | number | null };
};

type SnapshotLike = {
  schema_versao?: number;
  data_corte?: string;
  qualidade_dados?: string;
  resumo_restrito?: boolean;
  qualidade?: {
    status?: string;
    mensagem?: string;
    fonte_historico_comercial?: string;
    baixas_analisadas?: number;
    divergencias?: { codigo?: string; motivo: string }[];
  };
  indicadores?: {
    comercial?: {
      fonte?: string;
      fonte_historico_comercial?: string;
      motivo_fallback_comercial?: string | null;
      limitacao?: string | null;
      tempo_relacionamento_dias?: number | null;
      periodos?: Record<
        string,
        {
          quantidade_vendas?: number;
          primeira_compra?: string | null;
          ultima_compra?: string | null;
        }
      >;
    };
    baixas?: { periodos?: Record<string, PeriodoBaixasSnap>; total_baixas_cliente?: number };
  };
  percentual_pontualidade?: { disponivel?: boolean };
};

function parseIsoDateOnly(iso: string | null | undefined): Date | null {
  if (!iso || typeof iso !== 'string') return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (!y || !mo || !d) return null;
  return new Date(Date.UTC(y, mo - 1, d));
}

/** Diferença em dias de calendário: dataBase − ultimaOperacao (sem Date.now). */
export function calcularRecenciaDias(
  dataCorteIso: string | null | undefined,
  ultimaOperacaoIso: string | null | undefined,
): number | null {
  const base = parseIsoDateOnly(dataCorteIso);
  const ultima = parseIsoDateOnly(ultimaOperacaoIso);
  if (!base || !ultima) return null;
  const ms = base.getTime() - ultima.getTime();
  return Math.round(ms / 86_400_000);
}

export function normalizarFonteComercial(fonte: string | null | undefined): FonteComercialPainel {
  const f = (fonte || '').trim().toUpperCase();
  if (f === 'NFE_SAIDA_PRODUCAO' || f === 'NFE_SAIDA') return 'NFE_SAIDA_PRODUCAO';
  if (f === 'PEDIDO_VENDA') return 'PEDIDO_VENDA';
  if (f === 'INDISPONIVEL' || !f) return 'INDISPONIVEL';
  return 'DESCONHECIDA';
}

export function labelFonteComercial(fonte: FonteComercialPainel): string {
  if (fonte === 'NFE_SAIDA_PRODUCAO') return 'NF-e de saída autorizada em produção';
  if (fonte === 'PEDIDO_VENDA') return 'Pedido de Venda (fonte parcial)';
  if (fonte === 'INDISPONIVEL') return 'Indisponível';
  return 'Fonte não identificada';
}

/** Rótulo de UI — MÉDIA com acento; código interno permanece MEDIA. */
export function labelQualidadePainelV1(status: QualidadePainelV1): string {
  if (status === 'MEDIA') return 'MÉDIA';
  return status;
}

/**
 * Mapeamento determinístico V1. Nunca retorna ALTA.
 * Fonte Pedido limita a BAIXA (exceto INSUFICIENTE).
 */
export function mapQualidadePainelV1(
  statusB1: string | null | undefined,
  fonte: FonteComercialPainel,
): { status: QualidadePainelV1; alertaDivergente: boolean } {
  const raw = (statusB1 || '').trim().toUpperCase();
  let status: QualidadePainelV1;
  let alertaDivergente = false;

  if (raw === 'INSUFICIENTE') {
    status = 'INSUFICIENTE';
  } else if (raw === 'DIVERGENTE') {
    status = 'BAIXA';
    alertaDivergente = true;
  } else if (raw === 'PARCIAL') {
    status = 'BAIXA';
  } else if (raw === 'COMPLETA') {
    status = 'MEDIA';
  } else if (!raw) {
    status = 'INSUFICIENTE';
  } else {
    // Status desconhecido: não inventar ALTA
    status = 'BAIXA';
  }

  if (fonte === 'PEDIDO_VENDA' && status !== 'INSUFICIENTE') {
    status = 'BAIXA';
  }

  return { status, alertaDivergente };
}

function periodoTemBaixasExplicitas(periodos: Record<string, PeriodoBaixasSnap> | undefined): boolean {
  return Boolean(periodos && Object.keys(periodos).length > 0);
}

function somarBaixasAnalisadas(periodos: Record<string, PeriodoBaixasSnap> | undefined): number | null {
  if (!periodoTemBaixasExplicitas(periodos)) return null;
  let max = 0;
  let found = false;
  for (const p of Object.values(periodos || {})) {
    if (typeof p?.quantidade_baixas_analisadas === 'number') {
      found = true;
      max = Math.max(max, p.quantidade_baixas_analisadas);
    }
  }
  return found ? max : null;
}

function temMetricasPontualidadeValidas(snap: SnapshotLike): boolean {
  const b12 = snap.indicadores?.baixas?.periodos?.['12_MESES'];
  if (b12?.pontualidade_quantidade?.disponivel === true && b12.pontualidade_quantidade.valor != null) {
    return true;
  }
  const n = somarBaixasAnalisadas(snap.indicadores?.baixas?.periodos);
  if (n != null && n > 0) return true;
  if (typeof snap.qualidade?.baixas_analisadas === 'number' && snap.qualidade.baixas_analisadas > 0) {
    return true;
  }
  return false;
}

export function classificarComportamentoPagamento(snap: SnapshotLike): {
  codigo: ComportamentoPagamentoCodigo;
  mensagem: string | null;
} {
  const periodos = snap.indicadores?.baixas?.periodos;

  if (temMetricasPontualidadeValidas(snap)) {
    return { codigo: 'METRICAS_DISPONIVEIS', mensagem: null };
  }

  // SEM_CICLOS só com evidência numérica explícita de zero — nunca via ?? 0 / campo ausente.
  const nPeriodo = somarBaixasAnalisadas(periodos);
  const nQualidade = snap.qualidade?.baixas_analisadas;
  const zeroExplicito =
    (typeof nPeriodo === 'number' && nPeriodo === 0) ||
    (typeof nQualidade === 'number' && nQualidade === 0);

  if (zeroExplicito) {
    return { codigo: 'SEM_CICLOS_RECEBIMENTO', mensagem: MSG_SEM_CICLOS_RECEBIMENTO };
  }

  // Schema antigo / períodos sem quantidade / campos ausentes — não tratar como zero
  return {
    codigo: 'DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT',
    mensagem: MSG_DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT,
  };
}

export type PainelInternoV1 = {
  dataBase: string | null;
  fonte: FonteComercialPainel;
  fonteLabel: string;
  avisoFonteParcial: string | null;
  quantidadeOperacoes: number | null;
  primeiraOperacao: string | null;
  ultimaOperacao: string | null;
  tempoRelacionamentoDias: number | null;
  recenciaDias: number | null;
  qualidade: QualidadePainelV1;
  qualidadeB1: string | null;
  alertaDivergente: boolean;
  comportamento: ComportamentoPagamentoCodigo;
  comportamentoMensagem: string | null;
  isV2: boolean;
};

export function mapPainelInternoV1(snapshot: unknown): PainelInternoV1 {
  const snap = (snapshot && typeof snapshot === 'object' ? snapshot : {}) as SnapshotLike;
  const comercial = snap.indicadores?.comercial;
  const fonteRaw =
    comercial?.fonte ||
    comercial?.fonte_historico_comercial ||
    snap.qualidade?.fonte_historico_comercial ||
    null;
  const fonte = normalizarFonteComercial(fonteRaw);
  const total = comercial?.periodos?.TOTAL;
  const dataBase = snap.data_corte ?? null;
  const ultima = total?.ultima_compra ?? null;
  const primeira = total?.primeira_compra ?? null;
  const qtd =
    typeof total?.quantidade_vendas === 'number' ? total.quantidade_vendas : null;
  const statusB1 = snap.qualidade?.status || snap.qualidade_dados || null;
  const { status, alertaDivergente } = mapQualidadePainelV1(statusB1, fonte);
  const comportamento = classificarComportamentoPagamento(snap);

  let avisoFonteParcial: string | null = null;
  if (fonte === 'PEDIDO_VENDA') {
    avisoFonteParcial =
      comercial?.motivo_fallback_comercial ||
      comercial?.limitacao ||
      'Histórico comercial baseado em Pedido de Venda — fonte parcial.';
  }

  const isV2 = snap.schema_versao === 2 && Boolean(snap.indicadores);

  return {
    dataBase,
    fonte,
    fonteLabel: labelFonteComercial(fonte),
    avisoFonteParcial,
    quantidadeOperacoes: qtd,
    primeiraOperacao: primeira,
    ultimaOperacao: ultima,
    tempoRelacionamentoDias:
      typeof comercial?.tempo_relacionamento_dias === 'number'
        ? comercial.tempo_relacionamento_dias
        : null,
    recenciaDias: calcularRecenciaDias(dataBase, ultima),
    qualidade: status,
    qualidadeB1: statusB1,
    alertaDivergente,
    comportamento: comportamento.codigo,
    comportamentoMensagem: comportamento.mensagem,
    isV2,
  };
}
