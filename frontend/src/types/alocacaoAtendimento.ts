import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';
import type { AlocacaoVinculosExibicao } from '@/types/alocacaoAtendimentoOpcoes';

export type AlocacaoAtendimento = {
  id: number;
  pedido_venda_item_id: number | null;
  faturamento_item_id: number | null;
  item_nf_saida_id: number | null;
  produto_id: number;
  produto_nome: string;
  produto_codigo: string;
  pedido_venda_numero: string;
  quantidade_necessaria: string;
  quantidade_atendida: string;
  quantidade_pendente: string;
  tipo_atendimento: string;
  tipo_atendimento_label: string;
  status_entrada_fiscal: string;
  status_entrada_fiscal_label: string;
  origem_fisica: string;
  origem_fisica_label: string;
  destino_fisico: string;
  destino_fisico_label: string;
  pedido_compra_item_id: number | null;
  nf_entrada_item_id: number | null;
  nf_entrada_historica_item_id: number | null;
  cte_historico_importado_id: number | null;
  fornecedor_id: number | null;
  observacao_operacional: string;
  badges: { label: string; status: string; variant: string }[];
  vinculos?: AlocacaoVinculosExibicao;
  criado_em: string;
  atualizado_em: string;
};

export type AlocacaoAtendimentoPayload = {
  pedido_venda_item_id?: number | null;
  faturamento_item_id?: number | null;
  item_nf_saida_id?: number | null;
  produto_id: number;
  quantidade_necessaria: string;
  quantidade_atendida: string;
  quantidade_pendente: string;
  tipo_atendimento: string;
  status_entrada_fiscal: string;
  origem_fisica: string;
  destino_fisico: string;
  pedido_compra_item_id?: number | null;
  nf_entrada_item_id?: number | null;
  nf_entrada_historica_item_id?: number | null;
  cte_historico_importado_id?: number | null;
  fornecedor_id?: number | null;
  observacao_operacional?: string;
};

export type AlocacoesAtendimentoListResponse = {
  alocacoes: AlocacaoAtendimento[];
  count: number;
  resumo_atendimento_operacional: ResumoAtendimentoOperacional;
};

export const TIPOS_ATENDIMENTO = [
  { value: 'NAO_DEFINIDO', label: 'Não definido' },
  { value: 'ESTOQUE_PROPRIO', label: 'Estoque próprio' },
  { value: 'ENTRADA_CONCILIADA', label: 'Modo: entrada × venda' },
  { value: 'RETIRADA_FORNECEDOR', label: 'Retirada no fornecedor' },
  { value: 'ENTREGA_DIRETA_FORNECEDOR_CLIENTE', label: 'Entrega direta fornecedor → cliente' },
  { value: 'RETIRADA_FORNECEDOR_TRANSPORTADORA', label: 'Retirada fornecedor → transportadora' },
  { value: 'COMPRA_VINCULADA', label: 'Compra vinculada' },
  { value: 'MISTO', label: 'Misto' },
] as const;

export const STATUS_ENTRADA_FISCAL = [
  { value: 'NAO_APLICAVEL', label: 'Não aplicável' },
  { value: 'PENDENTE', label: 'Status fiscal: pendente' },
  { value: 'RECEBIDA', label: 'Status fiscal: recebida' },
  { value: 'CONCILIADA', label: 'Status fiscal: conciliada' },
  { value: 'DIVERGENTE', label: 'Status fiscal: divergente' },
  { value: 'CANCELADA', label: 'Status fiscal: cancelada' },
] as const;

export const ORIGEM_FISICA = [
  { value: 'NAO_DEFINIDA', label: 'Não definida' },
  { value: 'ESTOQUE_PROPRIO', label: 'Estoque próprio' },
  { value: 'FORNECEDOR', label: 'Fornecedor' },
  { value: 'TRANSPORTADORA', label: 'Transportadora' },
  { value: 'CLIENTE', label: 'Cliente' },
  { value: 'TERCEIRO', label: 'Terceiro' },
] as const;

export const DESTINO_FISICO = [
  { value: 'NAO_DEFINIDO', label: 'Não definido' },
  { value: 'CLIENTE', label: 'Cliente' },
  { value: 'TRANSPORTADORA', label: 'Transportadora' },
  { value: 'ESTOQUE_PROPRIO', label: 'Estoque próprio' },
  { value: 'TERCEIRO', label: 'Terceiro' },
] as const;
