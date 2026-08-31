import {
  baixarCommercialPdf,
  PEDIDO_COMPRA_PDF_CONFIG,
  PEDIDO_VENDA_PDF_CONFIG,
  PROPOSTA_PDF_CONFIG,
  visualizarCommercialPdf,
} from '@/lib/commercialPdfDownload';
import { normalizePedidoVendaRow } from '@/lib/pedidoVendaId';
import { sanitizePropostaRestForApi, stripPropostaItensForApi } from '@/lib/propostaApiPayload';
import api from './config';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';
import type {
  ConfirmarFaturamentoPedidoResponse,
  ConverterPropostaPedidoResponse,
  GerarPedidoPropostaPayload,
  RecuperarPropostaResponse,
  CriarFaturamentoPedidoResponse,
  GerarNFeSaidaFaturamentoResponse,
  HistoricoHomologacaoFiscalProposta,
  HistoricoComercialProposta,
  ResumoFaturamentoPedido,
  HomologacaoFiscalPropostaPayload,
  ItemPedido,
  ItemProposta,
  PedidoCompra,
  PedidoVenda,
  Proposta,
  CotacaoFornecedor,
  CotacaoComparativo,
  CotacaoFornecedorRespostaItem,
} from '@/types';

function stripPropostaPayload(data: Record<string, unknown>) {
  const { valor_total: _vt, ...rest } = data;
  return sanitizePropostaRestForApi(rest);
}

function stripPedidoItens(itens: ItemPedido[]) {
  return itens.map(({ id: _id, produto_nome: _p, corrida_numero: _c, ...rest }) => rest);
}

function stripPedidoVendaPayload(data: Record<string, unknown>) {
  const { cliente_nome: _cn, valor_total: _vt, empresa_emitente_nome: _en, ...rest } = data;
  return rest;
}

const propostasPath = 'propostas/';
const pvPath = 'pedidos-venda/';
const pcPath = 'pedidos-compra/';

type ListResponse<T> = T[] | { results?: T[] };

function unwrapPedidoVendaList(payload: ListResponse<PedidoVenda> | null | undefined): PedidoVenda[] {
  let rows: PedidoVenda[] = [];
  if (Array.isArray(payload)) {
    rows = payload;
  } else if (payload && Array.isArray(payload.results)) {
    rows = payload.results;
  }
  return rows.map((row) => normalizePedidoVendaRow(row));
}

export type ReferenciaComercialFreteResponse = {
  periodo_utilizado: Record<string, string | undefined>;
  empresa_utilizada: { empresa_id: number | null };
  referencia_historica: {
    frete_medio_observado: number | null;
    peso_frete_sobre_faturamento: number | null;
    valor_total_fretes_periodo: number;
    quantidade_ctes_validos: number;
    transportadora_referencia: { transportadora_id: number; transportadora_nome: string } | null;
    frete_medio_por_transportadora: {
      transportadora_nome: string;
      quantidade_ctes: number;
      valor_total_fretes: number;
      frete_medio: number;
      participacao_pct: number | null;
    }[];
  };
  mensagem: string;
  tem_base_historica: boolean;
};

export type ReferenciaComercialCustoCompraResponse = {
  periodo_utilizado: Record<string, string | undefined>;
  empresa_utilizada: { empresa_id: number | null };
  referencia_historica: {
    custo_medio_observado: number | null;
    ultimo_custo_observado: number | null;
    quantidade_notas_base: number;
    quantidade_itens_base: number;
    fornecedor_referencia: string | null;
    produto_referencia: { produto_id: number | null; ncm_utilizado: string | null };
  };
  tem_base_historica: boolean;
  mensagem: string;
};

export const propostasService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<Proposta>>(propostasPath, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<Proposta[] | PaginatedResponse<Proposta>>(propostasPath, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<Proposta>(`${propostasPath}${id}/`)).data,
  sugestaoNova: async (vendedorId?: number | null) =>
    (
      await api.get<{ mensagem_comercial: string }>(`${propostasPath}sugestao-nova/`, {
        params: vendedorId ? { vendedor_id: vendedorId } : undefined,
      })
    ).data,
  create: async (data: Omit<Proposta, 'id'>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<Proposta>(propostasPath, {
        ...stripPropostaPayload(rest as Record<string, unknown>),
        itens: stripPropostaItensForApi(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<Proposta>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...stripPropostaPayload(rest as Record<string, unknown>) };
    if (itens) payload.itens = stripPropostaItensForApi(itens);
    return (await api.patch<Proposta>(`${propostasPath}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${propostasPath}${id}/`);
  },
  convertToPedido: async (id: number) =>
    (await api.post<ConverterPropostaPedidoResponse>(`${propostasPath}${id}/converter-pedido/`, {})).data,
  gerarPedido: async (id: number, payload: GerarPedidoPropostaPayload) =>
    (await api.post<ConverterPropostaPedidoResponse>(`${propostasPath}${id}/gerar-pedido/`, payload)).data,
  recuperar: async (id: number, payload: { motivo: string }) =>
    (await api.post<RecuperarPropostaResponse>(`${propostasPath}${id}/recuperar/`, payload)).data,
  historicoComercial: async (id: number) =>
    (await api.get<HistoricoComercialProposta>(`${propostasPath}${id}/historico-comercial/`)).data,
  homologacaoFiscalResumo: async (id: number) =>
    (await api.get<HomologacaoFiscalPropostaPayload>(`${propostasPath}${id}/homologar-cenario-fiscal/resumo/`))
      .data,
  homologacaoFiscalIniciar: async (
    id: number,
    body: { cenario_fiscal_saida_id?: number | null; observacao?: string },
  ) =>
    (
      await api.post<HomologacaoFiscalPropostaPayload>(
        `${propostasPath}${id}/homologar-cenario-fiscal/iniciar/`,
        body,
      )
    ).data,
  homologacaoFiscalAprovar: async (id: number, body: { observacao?: string }) =>
    (
      await api.post<HomologacaoFiscalPropostaPayload>(
        `${propostasPath}${id}/homologar-cenario-fiscal/aprovar/`,
        body,
      )
    ).data,
  homologacaoFiscalReprovar: async (id: number, body: { observacao?: string }) =>
    (
      await api.post<HomologacaoFiscalPropostaPayload>(
        `${propostasPath}${id}/homologar-cenario-fiscal/reprovar/`,
        body,
      )
    ).data,
  homologacaoFiscalVoltarLegado: async (id: number, body: { observacao?: string }) =>
    (
      await api.post<HomologacaoFiscalPropostaPayload>(
        `${propostasPath}${id}/homologar-cenario-fiscal/voltar-legado/`,
        body,
      )
    ).data,
  homologacaoFiscalRecalcular: async (id: number) =>
    (
      await api.post<HomologacaoFiscalPropostaPayload>(
        `${propostasPath}${id}/homologar-cenario-fiscal/recalcular/`,
        {},
      )
    ).data,
  homologacaoFiscalHistorico: async (id: number) =>
    (
      await api.get<HistoricoHomologacaoFiscalProposta>(
        `${propostasPath}${id}/homologar-cenario-fiscal/historico/`,
      )
    ).data,
  apoioGerencial: async (query: URLSearchParams) =>
    (await api.get<{
      referencia_historica: {
        frete_medio_sobre_faturamento_pct: number | null;
        frete_medio_valor: number;
        carga_tributaria_media_vendas_pct: number | null;
        custo_medio_compra_observado_por_nota: number;
        custo_medio_compra_observado_produto: number | null;
        margem_referencia_observada_pct: number;
      };
      comparativo_periodo: {
        faturamento: number;
        compras: number;
        fretes: number;
        diferenca_venda_compra: number;
      };
      mensagens: { contexto: string; rotulo_referencia: string };
    }>(`${propostasPath}apoio-gerencial/?${query.toString()}`)).data,
  referenciaComercialFrete: async (
    query: URLSearchParams,
  ): Promise<ReferenciaComercialFreteResponse | null> => {
    try {
      return (await api.get<ReferenciaComercialFreteResponse>(`${propostasPath}referencia-comercial-frete/?${query.toString()}`))
        .data;
    } catch {
      return null;
    }
  },
  referenciaComercialCustoCompra: async (
    query: URLSearchParams,
  ): Promise<ReferenciaComercialCustoCompraResponse | null> => {
    try {
      return (
        await api.get<ReferenciaComercialCustoCompraResponse>(`${propostasPath}referencia-comercial-custo-compra/?${query.toString()}`)
      ).data;
    } catch {
      return null;
    }
  },
  search: async (term: string, limit = 20) =>
    (
      await api.get<{ results?: Proposta[] } | Proposta[]>(propostasPath, {
        params: { search: term, limit },
      })
    ).data,
  visualizarPdf: (id: number, numeroRef: string, previewTab?: Window | null) =>
    visualizarCommercialPdf(PROPOSTA_PDF_CONFIG, id, numeroRef, previewTab),
  /** @deprecated use visualizarPdf */
  gerarPdf: (id: number, numeroRef: string, previewTab?: Window | null) =>
    visualizarCommercialPdf(PROPOSTA_PDF_CONFIG, id, numeroRef, previewTab),
  baixarPdf: (id: number, numeroRef: string) => baixarCommercialPdf(PROPOSTA_PDF_CONFIG, id, numeroRef),
};

export const cotacoesFornecedoresService = {
  list: async (params?: { proposta_id?: number; status?: string }) => {
    const response = await api.get<CotacaoFornecedor[] | PaginatedResponse<CotacaoFornecedor>>('cotacoes-fornecedores/', { params });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<CotacaoFornecedor>(`cotacoes-fornecedores/${id}/`)).data,
  create: async (data: { proposta?: number | null; data?: string; prazo_resposta?: string | null; observacao?: string }) =>
    (await api.post<CotacaoFornecedor>('cotacoes-fornecedores/', data)).data,
  addItem: async (id: number, data: { item_proposta_id?: number; produto_id?: number; descricao_item?: string; unidade?: string; quantidade?: number; observacao_tecnica?: string }) =>
    (await api.post(`cotacoes-fornecedores/${id}/itens/`, data)).data,
  addParticipante: async (id: number, fornecedor_id: number) =>
    (await api.post(`cotacoes-fornecedores/${id}/participantes/`, { fornecedor_id })).data,
  resposta: async (id: number, data: Record<string, unknown>) =>
    (await api.post<CotacaoFornecedorRespostaItem>(`cotacoes-fornecedores/${id}/respostas/`, data)).data,
  comparativo: async (id: number) =>
    (await api.get<CotacaoComparativo>(`cotacoes-fornecedores/${id}/comparativo/`)).data,
  historico: async (id: number) =>
    (await api.get<import('@/types').CotacaoFornecedorHistorico[]>(`cotacoes-fornecedores/${id}/historico/`)).data,
  selecionarReferencia: async (id: number, resposta_id: number) =>
    (await api.post<CotacaoFornecedorRespostaItem>(`cotacoes-fornecedores/${id}/selecionar-referencia/`, { resposta_id })).data,
  cancelar: async (id: number) =>
    (await api.post<CotacaoFornecedor>(`cotacoes-fornecedores/${id}/cancelar/`, {})).data,
};

export const pedidosVendaService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<PedidoVenda>>(pvPath, {
      params: buildListParams(params),
    });
    return {
      ...response.data,
      results: unwrapPedidoVendaList(response.data),
    };
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<ListResponse<PedidoVenda>>(pvPath, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapPedidoVendaList(response.data);
  },
  getById: async (id: number) => (await api.get<PedidoVenda>(`${pvPath}${id}/`)).data,
  create: async (data: Omit<PedidoVenda, 'id'>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<PedidoVenda>(pvPath, {
        ...stripPedidoVendaPayload(rest as Record<string, unknown>),
        itens: stripPedidoItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<PedidoVenda>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...stripPedidoVendaPayload(rest as Record<string, unknown>) };
    if (itens) payload.itens = stripPedidoItens(itens);
    return (await api.patch<PedidoVenda>(`${pvPath}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${pvPath}${id}/`);
  },
  resumoFaturamento: async (id: number) =>
    (await api.get<ResumoFaturamentoPedido>(`${pvPath}${id}/resumo-faturamento/`)).data,
  recalcularTotaisPedido: async (id: number) =>
    (await api.post<ResumoFaturamentoPedido>(`${pvPath}${id}/recalcular-totais/`, {})).data,
  criarFaturamento: async (
    id: number,
    body: { observacao?: string; itens: { item_pedido_id: number; quantidade: string }[] },
  ) => (await api.post<CriarFaturamentoPedidoResponse>(`${pvPath}${id}/faturamentos/`, body)).data,
  confirmarFaturamento: async (pedidoId: number, faturamentoId: number) =>
    (
      await api.post<ConfirmarFaturamentoPedidoResponse>(
        `${pvPath}${pedidoId}/faturamentos/${faturamentoId}/confirmar/`,
        {},
      )
    ).data,
  cancelarFaturamento: async (pedidoId: number, faturamentoId: number) =>
    (await api.post<{ mensagens: string[] }>(`${pvPath}${pedidoId}/faturamentos/${faturamentoId}/cancelar/`, {}))
      .data,
  estornarFaturamento: async (pedidoId: number, faturamentoId: number, body?: { motivo?: string }) =>
    (
      await api.post<{ mensagens: string[]; pedido_status?: string }>(
        `${pvPath}${pedidoId}/faturamentos/${faturamentoId}/estornar/`,
        body ?? {},
      )
    ).data,
  repararVinculoNfeFaturamento: async (pedidoId: number, faturamentoId: number) =>
    (
      await api.post<{ mensagens: string[]; nfe_saida_id?: number | null; reparado?: boolean }>(
        `${pvPath}${pedidoId}/faturamentos/${faturamentoId}/reparar-vinculo-nfe/`,
        {},
      )
    ).data,
  gerarNfeSaidaFaturamento: async (
    pedidoId: number,
    faturamentoId: number,
    body?: { observacao?: string },
  ) =>
    (
      await api.post<GerarNFeSaidaFaturamentoResponse>(
        `${pvPath}${pedidoId}/faturamentos/${faturamentoId}/gerar-nfe-saida/`,
        body ?? {},
      )
    ).data,
  apoioGerencial: async (query: URLSearchParams) =>
    (await api.get<{
      referencia_historica: {
        frete_medio_sobre_faturamento_pct: number | null;
        frete_medio_valor: number;
        carga_tributaria_media_vendas_pct: number | null;
        custo_medio_compra_observado_por_nota: number;
        custo_medio_compra_observado_produto: number | null;
        margem_referencia_observada_pct: number;
      };
      comparativo_periodo: {
        faturamento: number;
        compras: number;
        fretes: number;
        diferenca_venda_compra: number;
      };
      mensagens: { contexto: string; rotulo_referencia: string };
    }>(`${pvPath}apoio-gerencial/?${query.toString()}`)).data,
  referenciaComercialFrete: async (
    query: URLSearchParams,
  ): Promise<ReferenciaComercialFreteResponse | null> => {
    try {
      return (await api.get<ReferenciaComercialFreteResponse>(`${pvPath}referencia-comercial-frete/?${query.toString()}`)).data;
    } catch {
      return null;
    }
  },
  referenciaComercialCustoCompra: async (
    query: URLSearchParams,
  ): Promise<ReferenciaComercialCustoCompraResponse | null> => {
    try {
      return (
        await api.get<ReferenciaComercialCustoCompraResponse>(`${pvPath}referencia-comercial-custo-compra/?${query.toString()}`)
      ).data;
    } catch {
      return null;
    }
  },
  search: async (term: string, limit = 20) =>
    (
      await api.get<{ results?: PedidoVenda[] } | PedidoVenda[]>(pvPath, {
        params: { search: term, limit },
      })
    ).data,
  visualizarPdf: (
    id: number,
    numeroRef: string,
    previewTab?: Window | null,
    invalidIdMessage?: string,
  ) => visualizarCommercialPdf(PEDIDO_VENDA_PDF_CONFIG, id, numeroRef, previewTab, invalidIdMessage),
  /** @deprecated use visualizarPdf */
  gerarPdf: (
    id: number,
    numeroRef: string,
    previewTab?: Window | null,
    invalidIdMessage?: string,
  ) => visualizarCommercialPdf(PEDIDO_VENDA_PDF_CONFIG, id, numeroRef, previewTab, invalidIdMessage),
  baixarPdf: (id: number, numeroRef: string, invalidIdMessage?: string) =>
    baixarCommercialPdf(PEDIDO_VENDA_PDF_CONFIG, id, numeroRef, invalidIdMessage),
};

export const pedidosCompraService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<PedidoCompra>>(pcPath, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<PedidoCompra[] | PaginatedResponse<PedidoCompra>>(pcPath, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<PedidoCompra>(`${pcPath}${id}/`)).data,
  create: async (data: Omit<PedidoCompra, 'id'>) => {
    const {
      fornecedor_nome: _fn,
      valor_total: _vt,
      itens,
      id: _id,
      numero: _num,
      resumo_financeiro_pedido: _rf,
      ...rest
    } = data as Omit<PedidoCompra, 'id'> & Record<string, unknown>;
    return (
      await api.post<PedidoCompra>(pcPath, {
        ...rest,
        itens: stripPedidoItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<PedidoCompra>) => {
    const {
      fornecedor_nome: _fn,
      valor_total: _vt,
      itens,
      numero: _num,
      resumo_financeiro_pedido: _rf,
      ...rest
    } = data as Partial<PedidoCompra> & Record<string, unknown>;
    const payload: Record<string, unknown> = { ...rest };
    if (itens) payload.itens = stripPedidoItens(itens);
    return (await api.patch<PedidoCompra>(`${pcPath}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${pcPath}${id}/`);
  },
  search: async (term: string, limit = 20) =>
    (
      await api.get<{ results?: PedidoCompra[] } | PedidoCompra[]>(pcPath, {
        params: { search: term, limit },
      })
    ).data,
  visualizarPdf: (id: number, numeroRef: string, previewTab?: Window | null) =>
    visualizarCommercialPdf(PEDIDO_COMPRA_PDF_CONFIG, id, numeroRef, previewTab),
  /** @deprecated use visualizarPdf */
  gerarPdf: (id: number, numeroRef: string, previewTab?: Window | null) =>
    visualizarCommercialPdf(PEDIDO_COMPRA_PDF_CONFIG, id, numeroRef, previewTab),
  baixarPdf: (id: number, numeroRef: string) =>
    baixarCommercialPdf(PEDIDO_COMPRA_PDF_CONFIG, id, numeroRef),
  /** @deprecated use visualizarPdf */
  openPdfInNewTab: (id: number, numeroRef: string, previewTab?: Window | null) =>
    visualizarCommercialPdf(PEDIDO_COMPRA_PDF_CONFIG, id, numeroRef, previewTab),
};
