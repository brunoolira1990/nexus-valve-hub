/**
 * Condições de exibição do bloco «Alocar para venda» na conferência NF-e entrada.
 *
 * O bloco deve ficar na coluna «Produto cadastrado» (larga o bastante).
 * Não depende de: Pedido de Compra, estoque aplicado, status PREPARADA/CONFERIDA,
 * nem de truthiness de quantidade_estoque_calculada.
 */
export function deveExibirBlocoAlocarEntradaVenda(item: {
  produto_id?: number | null;
  status?: string | null;
}): boolean {
  return item.produto_id != null && item.status !== 'IGNORADO';
}

export function deveOrientarVincularProdutoParaAlocacao(item: {
  produto_id?: number | null;
  status?: string | null;
}): boolean {
  return item.produto_id == null && item.status !== 'IGNORADO';
}
