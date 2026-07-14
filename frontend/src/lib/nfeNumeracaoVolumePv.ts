/**
 * Numeração compacta de volumes a partir do Pedido de Venda (ERP 4.0.14.x).
 * Espelha o helper backend — a fonte definitiva da sugestão é o create do rascunho.
 *
 * PV-AAAAMMDD-NNNN → AAMMDD-NNNN
 */

const RE_NUMERO_PV = /^PV-(\d{4})(\d{2})(\d{2})-(\d{4})$/;

export function compactarNumeroPedidoVenda(numero: string | null | undefined): string | null {
  if (numero == null) return null;
  const bruto = String(numero).trim();
  if (!bruto) return null;
  const m = RE_NUMERO_PV.exec(bruto);
  if (!m) return null;
  const ano = Number(m[1]);
  const mes = Number(m[2]);
  const dia = Number(m[3]);
  const seq = m[4];
  // Validação de data civil (rejeita 29/02 em ano não bissexto, etc.).
  const dt = new Date(Date.UTC(ano, mes - 1, dia));
  if (
    dt.getUTCFullYear() !== ano ||
    dt.getUTCMonth() !== mes - 1 ||
    dt.getUTCDate() !== dia
  ) {
    return null;
  }
  return `${String(ano).slice(2)}${m[2]}${m[3]}-${seq}`;
}

export const MSG_NUMERACAO_SUGERIDA_DO_PV = 'Sugerido a partir do Pedido de Venda.';
export const MSG_NUMERACAO_PADRAO_SUGERIDO =
  'Padrão sugerido: número compacto do Pedido de Venda.';

/** Ajuda discreta na conferência — não afirma origem se o valor divergir do compacto. */
export function textoAjudaNumeracaoVolumes(
  numeracaoAtual: string | null | undefined,
  pedidoNumero: string | null | undefined,
): string {
  const atual = (numeracaoAtual ?? '').trim();
  const compacto = compactarNumeroPedidoVenda(pedidoNumero);
  if (compacto && atual === compacto) {
    return MSG_NUMERACAO_SUGERIDA_DO_PV;
  }
  return MSG_NUMERACAO_PADRAO_SUGERIDO;
}
