/** Comercial 2.2 — defaults de formulário (espelham o backend). ERP 4.0.13.8 — labels operacionais. */

export { labelPedidoStatusOperacional as labelStatusPedidoVenda } from '@/lib/operationalUi';

export const VALIDADE_DIAS_PADRAO = 15;
export const STATUS_PROPOSTA_INICIAL = 'PENDENTE';
export const STATUS_PROPOSTA_CONVERTIDA = 'CONVERTIDA';
export const STATUS_PEDIDO_VENDA_INICIAL = 'ABERTO';
export const CONDICAO_PAGAMENTO_PADRAO = '30';

export function dataHojeIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function validadePadraoIso(dataBase?: string): string {
  const base = dataBase ? new Date(`${dataBase}T12:00:00`) : new Date();
  base.setDate(base.getDate() + VALIDADE_DIAS_PADRAO);
  return base.toISOString().slice(0, 10);
}

export { labelPropostaStatusOperacional as labelStatusProposta } from '@/lib/operationalUi';
