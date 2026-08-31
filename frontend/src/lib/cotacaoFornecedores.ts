import type {
  CotacaoFornecedor,
  CotacaoFornecedorItem,
  CotacaoFornecedorRespostaItem,
  CotacaoFornecedorStatus,
  CotacaoRespostaStatus,
} from '@/types';

export const statusCotacaoLabel: Record<string, string> = {
  RASCUNHO: 'Rascunho',
  EM_COTACAO: 'Em cotação',
  PARCIAL: 'Parcial',
  CONCLUIDA: 'Concluída',
  CANCELADA: 'Cancelada',
  PENDENTE: 'Pendente',
  RESPONDIDO: 'Respondido',
  RECUSADO: 'Recusado',
  SEM_RETORNO: 'Sem retorno',
};

export function labelStatusCotacao(status: CotacaoFornecedorStatus | CotacaoRespostaStatus | string): string {
  return statusCotacaoLabel[status] || status;
}

export function respostaPodeSerSelecionada(resposta: Pick<CotacaoFornecedorRespostaItem, 'status_item' | 'preco_unitario'>): boolean {
  return resposta.status_item === 'RESPONDIDO' && resposta.preco_unitario !== null;
}

export function menorPrecoRespondido(respostas: CotacaoFornecedorRespostaItem[]): number | null {
  const precos = respostas
    .filter((resposta) => respostaPodeSerSelecionada(resposta))
    .map((resposta) => Number(resposta.preco_unitario))
    .filter((preco) => Number.isFinite(preco));
  return precos.length ? Math.min(...precos) : null;
}

export type CotacaoOrigem = 'MANUAL' | 'PROPOSTA';
export type CotacaoOrigemFiltro = 'TODAS' | CotacaoOrigem;

export function origemCotacao(cotacao: Pick<CotacaoFornecedor, 'proposta_id'>): CotacaoOrigem {
  return cotacao.proposta_id == null ? 'MANUAL' : 'PROPOSTA';
}

export function labelOrigemCotacao(cotacao: Pick<CotacaoFornecedor, 'proposta_id'>): string {
  return origemCotacao(cotacao) === 'MANUAL' ? 'Manual' : 'Vinculada à Proposta';
}

export function descricaoItemCotacao(item: Pick<CotacaoFornecedorItem, 'id' | 'descricao_item' | 'produto_nome' | 'produto_snapshot'>): string {
  const snapshot = item.produto_snapshot || {};
  const descricaoSnapshot = typeof snapshot.descricao === 'string' ? snapshot.descricao : '';
  return item.descricao_item || item.produto_nome || descricaoSnapshot || `Item #${item.id}`;
}

export function novaCotacaoComPropostaPath(propostaId: number): string {
  return `/cotacoes-fornecedores/nova?proposta_id=${propostaId}`;
}

type FiltrosCotacao = {
  busca: string;
  status: CotacaoFornecedorStatus | 'TODOS';
  origem: CotacaoOrigemFiltro;
};

export function filtrarCotacoes(
  cotacoes: CotacaoFornecedor[],
  filtros: FiltrosCotacao,
  propostaNumeroPorId: Record<number, string> = {},
): CotacaoFornecedor[] {
  const termo = filtros.busca.trim().toLocaleLowerCase('pt-BR');
  return cotacoes.filter((cotacao) => {
    if (filtros.status !== 'TODOS' && cotacao.status !== filtros.status) return false;
    if (filtros.origem !== 'TODAS' && origemCotacao(cotacao) !== filtros.origem) return false;
    if (!termo) return true;
    const proposta = cotacao.proposta_id == null ? '' : propostaNumeroPorId[cotacao.proposta_id] || String(cotacao.proposta_id);
    return [cotacao.numero, cotacao.responsavel_nome, proposta, labelOrigemCotacao(cotacao), labelStatusCotacao(cotacao.status)]
      .join(' ')
      .toLocaleLowerCase('pt-BR')
      .includes(termo);
  });
}
