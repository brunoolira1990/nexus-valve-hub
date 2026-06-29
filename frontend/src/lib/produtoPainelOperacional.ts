import type {
  ProdutoPainelFiscalNfEntrada,
  ProdutoPainelHistoricoCompra,
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

type PainelCompraLinkSource =
  | ProdutoPainelResumoUltimaCompra
  | ProdutoPainelHistoricoCompra
  | null;

type PainelNfEntradaLinkSource =
  | ProdutoPainelResumoUltimaNfEntrada
  | ProdutoPainelFiscalNfEntrada
  | null;

export function painelValorExibicao(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

function painelNumeroNfEntrada(block: PainelCompraLinkSource): string | number | undefined {
  if (!block) return undefined;
  if ('nf_entrada_numero' in block && block.nf_entrada_numero) return block.nf_entrada_numero;
  if ('nf' in block && block.nf) return block.nf;
  return undefined;
}

export function buildPainelCompraLinks(block: PainelCompraLinkSource): PainelDocumentoLink[] {
  if (!block) return [];
  const links: PainelDocumentoLink[] = [];
  const nfNumero = painelNumeroNfEntrada(block);
  if (block.pedido_compra_id) {
    links.push({ label: `Pedido ${block.pedido_compra_numero || block.pedido_compra_id}`, to: '/pedidos-compra' });
  }
  if (block.nf_entrada_id) {
    links.push({ label: `Entrada Própria ${nfNumero || block.nf_entrada_id}`, to: '/nfe-entrada' });
  }
  if (block.nf_entrada_historica_id) {
    links.push({
      label: `Conferência NF ${nfNumero || block.nf_entrada_historica_id}`,
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

export function buildPainelNfEntradaLinks(block: PainelNfEntradaLinkSource): PainelDocumentoLink[] {
  if (!block) return [];
  if (block.nf_entrada_historica_id) {
    return [{
      label: `Conferência NF ${block.numero}`,
      to: `/nfe-entrada/${block.nf_entrada_historica_id}/conferencia`,
    }];
  }
  if (block.nf_entrada_id) {
    return [{ label: `Entrada Própria ${block.numero}`, to: '/nfe-entrada' }];
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

export function buildRastreabilidadeCorridaLink(codigo: string): PainelDocumentoLink {
  return { label: `Corrida ${codigo}`, to: '/corridas' };
}

export function buildRastreabilidadeCqLink(id: number, numero: string): PainelDocumentoLink {
  return { label: `CQ ${numero}`, to: '/certificados' };
}

export function buildRastreabilidadeCfLink(id: number, numero: string): PainelDocumentoLink {
  return { label: `CF ${numero}`, to: '/certificados-fornecedor' };
}

export function buildRastreabilidadeNfEntradaLink(id: number, numero: string): PainelDocumentoLink {
  return { label: `Entrada Própria ${numero}`, to: '/nfe-entrada' };
}

export function buildRastreabilidadeNfEntradaConferenciaLink(id: number, numero: string): PainelDocumentoLink {
  return { label: `Conferência NF ${numero}`, to: `/nfe-entrada/${id}/conferencia` };
}

export function buildRastreabilidadeNfSaidaLink(id: number, numero: string): PainelDocumentoLink {
  return { label: `NF saída ${numero}`, to: `/nfe-saida?nfe=${id}` };
}

export const PAINEL_SEM_HISTORICO = 'Sem registro para este produto.';
export const RASTREABILIDADE_SEM_REGISTRO = 'Nenhum registro encontrado.';

export function produtoPainelTemHistorico(resumo: ProdutoPainelResumo): boolean {
  return Boolean(
    resumo.ultima_compra
    || resumo.ultima_venda
    || resumo.ultima_nf_entrada
    || resumo.ultima_nf_saida
    || resumo.ultimo_cq
    || resumo.ultima_corrida
    || (resumo.historico_compras?.length ?? 0) > 0
    || (resumo.historico_vendas?.length ?? 0) > 0
    || resumo.inteligencia_compras
    || resumo.inteligencia_vendas
    || (resumo.qualidade?.certificados?.length ?? 0) > 0
    || (resumo.qualidade?.corridas?.length ?? 0) > 0
    || (resumo.fiscal?.nf_entrada?.length ?? 0) > 0
    || (resumo.fiscal?.nf_saida?.length ?? 0) > 0,
  );
}
