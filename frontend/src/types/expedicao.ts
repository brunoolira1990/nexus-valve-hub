export const TIPOS_OPERACAO_EXPEDICAO = [
  'ESTOQUE_PROPRIO',
  'RETIRADA_FORNECEDOR',
  'ENTREGA_DIRETA_FORNECEDOR_CLIENTE',
  'RETIRADA_FORNECEDOR_TRANSPORTADORA',
  'MISTO',
  'OUTROS',
] as const;

export type TipoOperacaoExpedicao = (typeof TIPOS_OPERACAO_EXPEDICAO)[number];

export const STATUS_EXPEDICAO = [
  'RASCUNHO',
  'AGUARDANDO_SEPARACAO',
  'AGUARDANDO_RETIRADA_FORNECEDOR',
  'MOTORISTA_ENVIADO',
  'RETIRADO_FORNECEDOR',
  'EM_TRANSITO',
  'ENTREGUE_TRANSPORTADORA',
  'ENTREGUE_CLIENTE',
  'OCORRENCIA',
  'CANCELADO',
] as const;

export type StatusExpedicao = (typeof STATUS_EXPEDICAO)[number];

export type ExpedicaoItem = {
  id: number;
  codigo: string;
  tipo_operacao: TipoOperacaoExpedicao;
  tipo_operacao_label: string;
  status: StatusExpedicao;
  status_label: string;
  cliente: number | null;
  cliente_nome: string;
  fornecedor: number | null;
  fornecedor_nome: string;
  transportadora: number | null;
  transportadora_nome: string;
  motorista_nome: string;
  motorista_documento: string;
  telefone_motorista: string;
  placa_veiculo: string;
  volumes: number;
  peso_bruto: string | null;
  peso_liquido: string | null;
  data_prevista_retirada: string | null;
  data_prevista_entrega: string | null;
  data_hora_retirada_real: string | null;
  data_hora_entrega_real: string | null;
  observacoes: string;
  ocorrencia_descricao: string;
  pedido_venda: number | null;
  pedido_venda_numero: string;
  pedido_compra: number | null;
  pedido_compra_numero: string;
  faturamento: number | null;
  faturamento_numero: string;
  nfe_saida: number | null;
  nfe_saida_numero: string;
  alocacao_atendimento: number | null;
  nfe_entrada: number | null;
  cte_entrada: number | null;
  criado_em: string;
  atualizado_em: string;
};

export type ExpedicaoResumo = {
  total: number;
  aguardando_separacao: number;
  aguardando_retirada_fornecedor: number;
  motorista_enviado: number;
  em_transito: number;
  entregue_cliente: number;
  ocorrencia: number;
  cancelado: number;
  por_status?: Record<string, number>;
};

export type ExpedicaoListResponse = {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: ExpedicaoItem[];
  resumo?: ExpedicaoResumo;
};

export type ExpedicaoPayload = Partial<
  Omit<ExpedicaoItem, 'id' | 'codigo' | 'tipo_operacao_label' | 'status_label' | 'criado_em' | 'atualizado_em'>
> & {
  tipo_operacao: TipoOperacaoExpedicao;
  status: StatusExpedicao;
};
