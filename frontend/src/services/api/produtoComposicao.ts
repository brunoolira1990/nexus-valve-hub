import api from './config';
import { unwrapListResults, type PaginatedResponse } from '@/lib/apiList';

export type ProdutoComposicaoItem = {
  id?: number;
  componente_produto_id: number;
  componente_codigo?: string;
  componente_descricao?: string;
  quantidade_por_unidade_final: string | number;
  unidade?: string;
  obrigatorio?: boolean;
  permite_substituto?: boolean;
  ordem?: number;
  observacoes?: string;
};

export type ProcessoMontagem = {
  id?: number;
  tipo: string;
  exige_servico?: boolean;
  exige_fornecedor_servico?: boolean;
  gera_produto_acabado?: boolean;
  baixa_componentes?: boolean;
  observacoes?: string;
};

export type ProdutoComposicao = {
  id?: number;
  produto_final_id: number;
  produto_final_codigo?: string;
  nome?: string;
  tipo_composicao: string;
  descricao?: string;
  ativo?: boolean;
  padrao?: boolean;
  permite_alternativa?: boolean;
  permite_comprar_pronto?: boolean;
  permite_montar?: boolean;
  exige_ordem_montagem?: boolean;
  exige_confirmacao?: boolean;
  exige_servico?: boolean;
  tipo_servico?: string;
  observacoes?: string;
  itens?: ProdutoComposicaoItem[];
  processos?: ProcessoMontagem[];
};

const path = 'produto-composicoes/';

export async function listProdutoComposicoes(produtoFinalId: number): Promise<ProdutoComposicao[]> {
  const { data } = await api.get<PaginatedResponse<ProdutoComposicao> | ProdutoComposicao[]>(path, {
    params: { produto_final_id: produtoFinalId, page_size: 100 },
  });
  return unwrapListResults(data);
}

export async function createProdutoComposicao(payload: ProdutoComposicao): Promise<ProdutoComposicao> {
  const { data } = await api.post<ProdutoComposicao>(path, payload);
  return data;
}

export async function updateProdutoComposicao(id: number, payload: Partial<ProdutoComposicao>): Promise<ProdutoComposicao> {
  const { data } = await api.patch<ProdutoComposicao>(`${path}${id}/`, payload);
  return data;
}

export async function deleteProdutoComposicao(id: number): Promise<void> {
  await api.delete(`${path}${id}/`);
}
