import type { CotacaoFornecedorRespostaItem, CotacaoFornecedorStatus, CotacaoRespostaStatus } from '@/types';

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
