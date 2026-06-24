import type {
  ProdutoPainelResumo,
  ProdutoPainelResumoUltimaCompra,
  ProdutoPainelResumoUltimaCorrida,
  ProdutoPainelResumoUltimaNfEntrada,
  ProdutoPainelResumoUltimaNfSaida,
  ProdutoPainelResumoUltimaVenda,
  ProdutoPainelResumoUltimoCq,
} from '@/types';

export type PainelDocumentoLink = {
  label: string;
  to: string;
};

export function painelValorExibicao(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

export function buildPainelCompraLinks(block: ProdutoPainelResumoUltimaCompra | null): PainelDocumentoLink[] {
  if (!block) return [];
  const links: PainelDocumentoLink[] = [];
  if (block.pedido_compra_id) {
    links.push({ label: `Pedido ${block.pedido_compra_numero || block.pedido_compra_id}`, to: '/pedidos-compra' });
  }
  if (block.nf_entrada_id) {
    links.push({ label: `NF entrada ${block.nf_entrada_numero || block.nf_entrada_id}`, to: '/nfe-entrada' });
  }
  if (block.nf_entrada_historica_id) {
    links.push({
      label: `Conferência NF ${block.nf_entrada_numero || block.nf_entrada_historica_id}`,
      to: `/nfe-entrada/${block.nf_entrada_historica_id}/conferencia`,
    });
  }
  return links;
}

export function buildPainelVendaLinks(block: ProdutoPainelResumoUltimaVenda | null): PainelDocumentoLink[] {
  if (!block) return [];
  const links: PainelDocumentoLink[] = [];
  if (block.pedido_id) {
    links.push({
      label: `Pedido ${block.pedido_numero || block.pedido_id}`,
      to: `/pedidos-venda?pedido=${block.pedido_id}`,
    });
  }
  if (block.nf_id) {
    links.push({ label: `NF saída ${block.nf || block.nf_id}`, to: `/nfe-saida?nfe=${block.nf_id}` });
  }
  return links;
}

export function buildPainelNfEntradaLinks(block: ProdutoPainelResumoUltimaNfEntrada | null): PainelDocumentoLink[] {
  if (!block) return [];
  if (block.nf_entrada_historica_id) {
    return [{
      label: `Conferência NF ${block.numero}`,
      to: `/nfe-entrada/${block.nf_entrada_historica_id}/conferencia`,
    }];
  }
  if (block.nf_entrada_id) {
    return [{ label: `NF entrada ${block.numero}`, to: '/nfe-entrada' }];
  }
  return [];
}

export function buildPainelNfSaidaLinks(block: ProdutoPainelResumoUltimaNfSaida | null): PainelDocumentoLink[] {
  if (!block?.nf_id) return [];
  return [{ label: `NF saída ${block.numero}`, to: `/nfe-saida?nfe=${block.nf_id}` }];
}

export function buildPainelCqLinks(block: ProdutoPainelResumoUltimoCq | null): PainelDocumentoLink[] {
  if (!block?.certificado_qualidade_id) return [];
  return [{ label: `CQ ${block.numero}`, to: '/certificados' }];
}

export function buildPainelCorridaLinks(block: ProdutoPainelResumoUltimaCorrida | null): PainelDocumentoLink[] {
  if (!block?.corrida) return [];
  return [{ label: `Corrida ${block.corrida}`, to: '/corridas' }];
}

export const PAINEL_SEM_HISTORICO = 'Sem registro para este produto.';

export function produtoPainelTemHistorico(resumo: ProdutoPainelResumo): boolean {
  return Boolean(
    resumo.ultima_compra
    || resumo.ultima_venda
    || resumo.ultima_nf_entrada
    || resumo.ultima_nf_saida
    || resumo.ultimo_cq
    || resumo.ultima_corrida,
  );
}
