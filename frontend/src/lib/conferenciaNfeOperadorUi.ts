/**
 * UX de operador — conferência NF-e entrada.
 * Mantém valores técnicos da API; só decide o que destacar e como falar.
 */

import type { ItemConferenciaNFeEntrada, NFeEntradaConferencia } from '@/types';
import { labelStatusConferenciaCabecalho } from '@/lib/conferenciaNfeLabels';

export type ProgressoConferenciaOperador = {
  totalItens: number;
  itensAtivos: number;
  produtosOk: number;
  produtosFaltando: number;
  fiscalBloqueado: number;
  fiscalSemRegra: number;
  divergentes: number;
  ignorados: number;
};

/** Uso/consumo e regras com movimenta_estoque=false não exigem produto cadastrado. */
export function itemExigeProduto(it: ItemConferenciaNFeEntrada): boolean {
  if (it.status === 'IGNORADO') return false;
  if (it.resultado_fiscal?.movimenta_estoque === false) return false;
  if ((it.elegibilidade_estoque?.status || '').toUpperCase() === 'NAO_MOVIMENTA') return false;
  return true;
}

export function itemPendenteProduto(it: ItemConferenciaNFeEntrada): boolean {
  if (it.status === 'IGNORADO') return false;
  if (!itemExigeProduto(it)) return false;
  return !it.produto_id || it.status === 'PENDENTE_PRODUTO';
}

export function itemComProblemaOperador(it: ItemConferenciaNFeEntrada): boolean {
  if (it.status === 'IGNORADO') return false;
  if (itemPendenteProduto(it)) return true;
  if (it.status === 'DIVERGENTE') return true;
  const stFiscal = (it.resultado_fiscal?.status || '').toUpperCase();
  if (stFiscal === 'BLOQUEADO' || stFiscal === 'SEM_REGRA') return true;
  const elig = (it.elegibilidade_estoque?.status || '').toUpperCase();
  if (elig === 'BLOQUEADO') return true;
  return false;
}

export function computarProgressoConferencia(
  dados: NFeEntradaConferencia | null | undefined,
): ProgressoConferenciaOperador {
  const itens = dados?.itens || [];
  const ativos = itens.filter((it) => it.status !== 'IGNORADO');
  return {
    totalItens: itens.length,
    itensAtivos: ativos.length,
    produtosOk: ativos.filter((it) => !itemPendenteProduto(it)).length,
    produtosFaltando: ativos.filter((it) => itemPendenteProduto(it)).length,
    fiscalBloqueado: Number(dados?.resumo_fiscal?.bloqueado || 0),
    fiscalSemRegra: Number(dados?.resumo_fiscal?.sem_regra || 0),
    divergentes: ativos.filter((it) => it.status === 'DIVERGENTE').length,
    ignorados: itens.filter((it) => it.status === 'IGNORADO').length,
  };
}

/** Uma frase clara: o que o operador deve fazer agora. */
export function proximoPassoOperador(
  dados: NFeEntradaConferencia | null | undefined,
  progresso: ProgressoConferenciaOperador,
): string {
  if (!dados) return 'Carregando a nota…';
  const status = (dados.status || '').toUpperCase();
  if (status === 'CANCELADA') return 'Esta entrada foi cancelada.';
  if (status === 'PREPARADA' || status === 'CONFERIDA') {
    if (dados.estoque_aplicado_em) {
      return 'Conferência concluída e estoque já aplicado.';
    }
    return 'Conferência finalizada. Se precisar, aplique o estoque ou gere o financeiro.';
  }
  if (progresso.produtosFaltando > 0) {
    const n = progresso.produtosFaltando;
    return n === 1
      ? 'Vincule o produto que falta para continuar.'
      : `Vincule os ${n} produtos que faltam para continuar.`;
  }
  if (progresso.fiscalBloqueado > 0) {
    return 'Há itens bloqueados no fiscal — revise com o responsável antes de finalizar.';
  }
  if (progresso.fiscalSemRegra > 0) {
    return 'Há itens sem regra fiscal — cadastre a regra ou peça ajuda ao fiscal.';
  }
  if (progresso.divergentes > 0) {
    return 'Há divergências com o pedido — confira quantidades/preços ou aceite as divergências.';
  }
  if (!dados.data_entrada) {
    return 'Informe a data de entrada e finalize a conferência.';
  }
  return 'Tudo certo para finalizar a conferência.';
}

export function labelStatusItemOperador(status: string): string {
  const map: Record<string, string> = {
    PENDENTE_PRODUTO: 'Falta vincular produto',
    PRODUTO_VINCULADO: 'Produto ok',
    CONFERIDO: 'Ok',
    DIVERGENTE: 'Diferença no pedido',
    IGNORADO: 'Ignorado',
  };
  return map[status] || status;
}

export function labelStatusCabecalhoOperador(status: string | undefined | null): string {
  return labelStatusConferenciaCabecalho(status);
}

export function filtrarItensOperador(
  itens: ItemConferenciaNFeEntrada[],
  soPendencias: boolean,
): ItemConferenciaNFeEntrada[] {
  if (!soPendencias) return itens;
  return itens.filter((it) => itemComProblemaOperador(it));
}

/** Ao vincular item do pedido, preenche produto se ainda estiver vazio. */
export function patchVinculoItemPedido(params: {
  item: Pick<ItemConferenciaNFeEntrada, 'produto_id'>;
  itemPedidoId: number | null;
  produtoIdDoPedido: number | null | undefined;
}): Partial<ItemConferenciaNFeEntrada> {
  const { item, itemPedidoId, produtoIdDoPedido } = params;
  const patch: Partial<ItemConferenciaNFeEntrada> = {
    item_pedido_compra_id: itemPedidoId,
  };
  if (itemPedidoId && !item.produto_id && produtoIdDoPedido) {
    patch.produto_id = produtoIdDoPedido;
  }
  return patch;
}
