import type { ResultadoFiscalEntrada } from '@/types';

export const LABEL_DIVERGENCIA_CONFERENCIA: Record<string, string> = {
  produto_diferente_pedido: 'Produto diferente do pedido',
  unidade_diferente: 'Unidade diferente do pedido',
  quantidade_diferente: 'Quantidade diferente do pedido',
  preco_diferente: 'Preço unitário diferente do pedido',
  ncm_divergente_nf_produto: 'NCM da NF diferente do produto cadastrado',
};

export function labelDivergenciaConferencia(codigo: string): string {
  return LABEL_DIVERGENCIA_CONFERENCIA[codigo] || codigo;
}

/** Score mínimo para exibir botão "Aplicar sugestão" (alinhado ao backend). */
export const SCORE_SUGESTAO_ITEM_PEDIDO_ALTO = 40;

export function labelSugestaoItemPedidoCurta(sugestao: {
  produto_codigo: string;
  descricao: string;
}): string {
  const codigo = sugestao.produto_codigo || '—';
  const desc = sugestao.descricao || '—';
  return `${codigo} · ${desc}`;
}

export const LABEL_STATUS_QUANTITATIVO_PEDIDO: Record<string, string> = {
  nao_vinculado: 'Não vinculado',
  parcial: 'Parcial',
  completo: 'Completo',
  excedente: 'Excedente',
};

export const LABEL_ALERTA_RESUMO_QUANTITATIVO: Record<string, string> = {
  item_pedido_duplicado_na_nf:
    'Item do pedido vinculado em mais de uma linha da NF. Confira se é divisão por lote/corrida.',
  quantidade_nf_menor_que_pedido: 'Quantidade vinculada na NF é menor que a quantidade do pedido.',
  quantidade_nf_maior_que_pedido: 'Quantidade vinculada na NF excede a quantidade do pedido.',
};

export function labelStatusQuantitativoPedido(codigo: string): string {
  return LABEL_STATUS_QUANTITATIVO_PEDIDO[codigo] || codigo;
}

export function labelAlertaResumoQuantitativo(codigo: string): string {
  return LABEL_ALERTA_RESUMO_QUANTITATIVO[codigo] || codigo;
}

export const LABEL_STATUS_SALDO_GLOBAL_PEDIDO: Record<string, string> = {
  pendente: 'Pendente',
  parcial: 'Parcial',
  completo: 'Completo',
  excedente: 'Excedente',
};

export function labelStatusSaldoGlobalPedido(codigo: string): string {
  return LABEL_STATUS_SALDO_GLOBAL_PEDIDO[codigo] || codigo;
}

export const NOTA_SALDO_CONFERENCIA_PEDIDO =
  'Este saldo é calculado pelas conferências vinculadas ao pedido. Não representa movimentação de estoque.';

export const LABEL_STATUS_CONFERENCIA_ITEM: Record<string, string> = {
  PENDENTE_PRODUTO: 'Pendente produto',
  PRODUTO_VINCULADO: 'Produto vinculado',
  CONFERIDO: 'Conferido',
  DIVERGENTE: 'Divergente',
  IGNORADO: 'Ignorado',
};

export function labelStatusConferenciaItem(status: string): string {
  return LABEL_STATUS_CONFERENCIA_ITEM[status] || status;
}

const LABEL_STATUS_CONFERENCIA_CABECALHO: Record<string, string> = {
  PENDENTE: 'Em conferência',
  PREPARADA: 'Conferência finalizada',
  CONFERIDA: 'Conferida',
  CANCELADA: 'Cancelada',
};

/** Rótulo amigável do status do cabeçalho da conferência NF-e entrada (valor técnico permanece na API). */
export function labelStatusConferenciaCabecalho(status: string | undefined | null): string {
  const key = (status || '').trim().toUpperCase();
  return LABEL_STATUS_CONFERENCIA_CABECALHO[key] || status || '—';
}

/** Central DF-e / inbox: rótulo de entrada quando a conferência foi finalizada (status PREPARADO). */
export function labelStatusEntradaNfeConferenciaFinalizada(
  statusEntrada: string | undefined | null,
  labelApi?: string | null,
): string {
  const st = (statusEntrada || '').trim().toUpperCase();
  if (st === 'PREPARADO' || (labelApi || '').trim() === 'Preparado') {
    return 'Conferência finalizada';
  }
  return (labelApi || '').trim() || statusEntrada || '—';
}

/** Ajusta textos da API que ainda mencionam “preparar estoque” para exibição na UI. */
export function humanizarTextoFinalizarConferencia(texto: string): string {
  return texto
    .replace(
      /antes de finalizar \(preparar estoque/gi,
      'antes de finalizar a conferência',
    )
    .replace(/antes de preparar estoque/gi, 'antes de finalizar a conferência')
    .replace(/impedem preparar estoque/gi, 'impedem finalizar a conferência')
    .replace(/Não foi possível preparar estoque/gi, 'Não foi possível finalizar a conferência')
    .replace(/opcional para preparar\b/gi, 'opcional para finalizar a conferência')
    .replace(/revise antes de preparar\b/gi, 'revise antes de finalizar a conferência')
    .replace(/antes de preparar\b/gi, 'antes de finalizar a conferência')
    .replace(/preparar estoque/gi, 'finalizar a conferência')
    .replace(/marcar conferida ou preparada/gi, 'salvar ou finalizar a conferência')
    .replace(/grava a conferência como PREPARADA/gi, 'finaliza a conferência fiscalmente');
}

/** Aviso de pendências operacionais no bloco financeiro da NF-e entrada. */
export function formatarAvisoPendenciasOperacionaisNfeEntrada(aviso?: string | null): string {
  const fallback =
    'Existem pendências operacionais nesta NF-e. O financeiro pode ser gerado, mas a conferência não foi finalizada e a aplicação de estoque permanece pendente.';
  if (!aviso?.trim()) return fallback;
  return humanizarTextoFinalizarConferencia(
    aviso.replace(
      /estoque, produtos e pedido de compra continuarão pendentes até conferência/gi,
      'a conferência não foi finalizada; produtos e pedido de compra permanecem pendentes',
    ),
  );
}

export function badgeClassStatusConferencia(status: string): string {
  switch (status) {
    case 'CONFERIDO':
      return 'erp-badge-success';
    case 'DIVERGENTE':
      return 'erp-badge-danger';
    case 'IGNORADO':
      return 'erp-badge-info';
    case 'PRODUTO_VINCULADO':
      return 'erp-badge-success';
    default:
      return 'erp-badge-warning';
  }
}

export function labelProdutoLinhaConferencia(p: { codigo_completo?: string; descricao?: string }): string {
  const codigo = (p.codigo_completo || '').trim() || '—';
  const descricao = (p.descricao || '').trim() || '—';
  return `${codigo} · ${descricao}`;
}

export const LABEL_STATUS_FISCAL_ENTRADA: Record<string, string> = {
  OK: 'OK',
  ALERTA: 'Alerta',
  SEM_REGRA: 'Sem regra',
  BLOQUEADO: 'Bloqueado',
};

export function labelStatusFiscalEntrada(status: string): string {
  return LABEL_STATUS_FISCAL_ENTRADA[status] || status;
}

export function divergenciasFiscaisResumo(
  rf: ResultadoFiscalEntrada | undefined,
  max = 3,
): string[] {
  const divs = rf?.divergencias || [];
  return divs.slice(0, max).map((d) => `${d.label}: divergente`);
}

export function badgeClassStatusFiscalEntrada(status: string): string {
  switch (status) {
    case 'OK':
      return 'erp-badge-success';
    case 'ALERTA':
    case 'SEM_REGRA':
      return 'erp-badge-warning';
    case 'BLOQUEADO':
      return 'erp-badge-danger';
    default:
      return 'erp-badge-info';
  }
}

export const LABEL_ELEGIBILIDADE_ESTOQUE: Record<string, string> = {
  APTO: 'Apto para estoque',
  APTO_COM_ALERTA: 'Apto com alerta',
  BLOQUEADO: 'Bloqueado',
  NAO_MOVIMENTA: 'Não movimenta estoque',
};

export function labelElegibilidadeEstoque(status: string): string {
  return LABEL_ELEGIBILIDADE_ESTOQUE[status] || status;
}

export function badgeClassElegibilidadeEstoque(status: string): string {
  switch (status) {
    case 'APTO':
      return 'erp-badge-success';
    case 'APTO_COM_ALERTA':
      return 'erp-badge-warning';
    case 'BLOQUEADO':
      return 'erp-badge-danger';
    case 'NAO_MOVIMENTA':
      return 'erp-badge-info';
    default:
      return 'erp-badge-info';
  }
}

export function labelItemPedidoCompraOption(
  item: {
    id: number;
    produto_id: number;
    produto_nome: string;
    quantidade: number;
    quantidade_negociada?: number;
    unidade_negociada?: string;
    valor_unitario: number;
  },
  codigoProduto?: string,
): string {
  const codigo = codigoProduto || `ID ${item.produto_id}`;
  const qtd = item.quantidade_negociada ?? item.quantidade;
  const un = item.unidade_negociada || '—';
  const valor = Number(item.valor_unitario || 0).toFixed(2);
  return `${codigo} · ${item.produto_nome} · ${Number(qtd).toFixed(3)} ${un} · R$ ${valor}`;
}
