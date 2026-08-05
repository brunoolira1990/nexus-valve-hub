/** Tipos da Fase 1 — conciliação operacional NF-e Entrada × Pedido de Venda. */

export type EstadoOperacionalEntradaVenda =
  | 'SEM_ALOCACAO'
  | 'PARCIAL'
  | 'CONCILIADO'
  | 'DIVERGENTE';

export type OpcaoPedidoVendaItemAlocacao = {
  id: number;
  pedido_venda_id: number | null;
  pedido_venda_numero: string;
  cliente_nome: string;
  produto_id: number | null;
  produto_codigo: string;
  produto_nome: string;
  quantidade_necessaria: string;
  unidade_necessidade?: string;
  fonte_necessidade?: string;
  quantidade_ja_alocada: string;
  saldo_destino: string;
  faturamento_id: number | null;
  faturamento_numero: string | null;
  nfe_saida_id: number | null;
  nfe_saida_numero: string | null;
  documentos_relacionados?: {
    faturamentos: { faturamento_item_id: number; faturamento_id: number; numero: string }[];
    nfes_saida: {
      item_nf_saida_id: number;
      nfe_saida_id: number;
      numero: string;
      faturamento_item_id: number;
    }[];
    cadeia_ambigua: boolean;
  };
  label: string;
};

export type AlocacaoEntradaVendaResumoItem = {
  id: number;
  pedido_venda_item_id: number | null;
  pedido_venda_id: number | null;
  pedido_venda_numero: string;
  cliente_nome: string;
  produto_id: number | null;
  produto_codigo: string;
  produto_nome: string;
  quantidade_alocada: string;
  necessidade_destino: string;
  total_alocado_destino: string;
  saldo_destino: string;
  status_entrada_fiscal?: string;
  tipo_atendimento?: string;
  faturamento_id: number | null;
  faturamento_numero: string | null;
  nfe_saida_id: number | null;
  nfe_saida_numero: string | null;
  criado_em: string | null;
  atualizado_em: string | null;
};

export type ResumoEntradaVenda = {
  item_conferencia_id: number;
  nf_entrada_historica_item_id: number;
  produto_id: number | null;
  produto_codigo: string;
  produto_nome: string;
  unidade_estoque_calculada: string;
  quantidade_disponivel: string;
  total_alocado: string;
  saldo_entrada: string;
  estado_operacional: EstadoOperacionalEntradaVenda;
  estoque_aplicado: boolean;
  aviso_estoque: string | null;
  aviso_operacional: string;
  alocacoes: AlocacaoEntradaVendaResumoItem[];
};

export const LABEL_ESTADO_OPERACIONAL: Record<EstadoOperacionalEntradaVenda, string> = {
  SEM_ALOCACAO: 'Qty: sem alocação',
  PARCIAL: 'Qty: parcial',
  CONCILIADO: 'Qty: conciliado',
  DIVERGENTE: 'Qty: divergente',
};

export type AlocacaoAtendimentoEvento = {
  id: number;
  evento: string;
  alocacao_id_snapshot: number;
  ator_id_snapshot: number | null;
  ator_rotulo_snapshot: string;
  nf_entrada_historica_item_id_snapshot: number | null;
  pedido_venda_item_id_snapshot: number | null;
  motivo: string;
  criado_em: string;
};
