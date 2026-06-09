/** Helpers UI — equivalência/composição na conferência NF-e entrada. */

export type NivelConfiancaEquivalencia = 'alta' | 'media' | 'baixa';

export type SugestaoEquivalenciaConferencia = {
  tipo: string;
  confianca: number;
  nivel_confianca: NivelConfiancaEquivalencia;
  produto_interno_id: number;
  produto_interno_codigo?: string;
  produto_interno_descricao?: string;
  item_pedido_compra_id?: number | null;
  quantidade_equivalente?: string;
  valor_total_agrupado?: string;
  valor_pedido_referencia?: string;
  diferenca_valor?: string;
  dentro_tolerancia?: boolean;
  itens_nfe_conferencia_ids?: number[];
  itens_nfe?: Array<{
    codigo_fornecedor?: string;
    descricao?: string;
    quantidade?: string;
    valor_total?: string;
  }>;
  motivos?: string[];
  alerta_filial?: string | null;
  tipo_composicao?: string | null;
};

export type EquivalenciasConferenciaPayload = {
  sugestoes: SugestaoEquivalenciaConferencia[];
  agrupamentos: unknown[];
  comparacao_pedido_nf?: {
    valor_produtos_pedido?: string;
    valor_produtos_nf?: string;
    diferenca_produtos?: string;
    mensagem?: string;
  } | null;
  aviso_estoque: string;
};

export function badgeConfiancaEquivalencia(nivel: NivelConfiancaEquivalencia | string): {
  label: string;
  className: string;
} {
  const n = (nivel || '').toLowerCase();
  if (n === 'alta') return { label: 'Sugestão do sistema — Alta', className: 'erp-badge-success' };
  if (n === 'media') return { label: 'Sugestão do sistema — Média', className: 'erp-badge-warning' };
  return { label: 'Sugestão do sistema — Baixa', className: 'erp-badge-danger' };
}

export function labelTipoEquivalencia(tipo: string): string {
  const t = (tipo || '').toLowerCase();
  if (t === 'equivalencia_composta') return 'Itens do fornecedor agrupados';
  if (t === 'equivalencia_simples') return 'Vínculo simples';
  if (t === 'montagem_planejada') return 'Montagem planejada';
  return tipo || 'Equivalência';
}

export function labelTipoComposicao(tipo: string): string {
  const map: Record<string, string> = {
    KIT_COMERCIAL: 'Kit comercial',
    MONTAGEM_SIMPLES: 'Montagem simples',
    MONTAGEM_ROSCADA: 'Montagem roscada',
    MONTAGEM_SOLDADA: 'Montagem soldada',
    MONTAGEM_SERVICO_INTERNO: 'Montagem com serviço interno',
    MONTAGEM_TERCEIRIZADA: 'Montagem terceirizada',
    BENEFICIAMENTO: 'Beneficiamento',
  };
  return map[tipo] || tipo;
}

export function formatMoedaBRL(v: string | number | undefined | null): string {
  const n = Number(v ?? 0);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function exigeMotivoDivergencia(sug: SugestaoEquivalenciaConferencia, tolerancia = 0.05): boolean {
  if (sug.dentro_tolerancia) return false;
  const diff = Math.abs(Number(sug.diferenca_valor ?? 0));
  return diff > tolerancia;
}

export const AVISO_EQUIVALENCIA_SEM_ESTOQUE =
  'Equivalência confirmada para conferência. Movimentação de estoque ou montagem real será feita em fase própria.';

export const AVISO_COMPOSICAO_SEM_ESTOQUE =
  'Composição cadastral — não movimenta estoque automaticamente nesta fase.';
