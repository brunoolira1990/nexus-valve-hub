import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';

export interface AtendimentoOperacionalRef {
  id: number;
  numero?: string;
  numero_faturamento?: string;
  titulo?: string;
  nome?: string;
  codigo?: string;
  descricao?: string;
  status_conferencia?: string;
}

export interface AtendimentoOperacionalItem {
  id: number;
  pedido_venda: { id: number; numero: string } | null;
  faturamento: { id: number; numero_faturamento: string } | null;
  nfe_saida: { id: number; titulo: string } | null;
  cliente: { id: number; nome: string } | null;
  produto: { id: number; codigo: string; descricao: string };
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
  fornecedor: { id: number; nome: string } | null;
  pedido_compra: { id: number; numero: string } | null;
  nfe_entrada: { id: number; numero: string; status_conferencia?: string } | null;
  cte: { id: number; numero: string; status_conferencia?: string } | null;
  badges: ResumoAtendimentoOperacional['badges'];
  alertas: string[];
  observacao_operacional: string;
  criado_em?: string | null;
}

export interface AtendimentosOperacionaisKpis {
  total: number;
  entradas_pendentes: number;
  entradas_conciliadas: number;
  retiradas_fornecedor: number;
  entregas_diretas: number;
  sem_compra_vinculada: number;
  com_cte_conferido: number;
}

export interface AtendimentosOperacionaisListResponse {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: AtendimentoOperacionalItem[];
  kpis?: AtendimentosOperacionaisKpis;
}
