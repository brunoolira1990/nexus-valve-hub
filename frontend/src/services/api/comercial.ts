import api from './config';
import type { ItemPedido, ItemProposta, PedidoCompra, PedidoVenda, Proposta } from '@/types';

function stripPropostaItens(itens: ItemProposta[]) {
  return itens.map(
    ({
      id: _id,
      produto_nome: _p,
      estrategia_formacao: _e,
      alvo_percentual: _a,
      ipi_entrada_valor: _iev,
      custo_carregado: _cc,
      preco_base: _pb,
      percentual_saida_total: _pst,
      valor_carga_saida: _vcs,
      ...rest
    }) => rest,
  );
}

function stripPropostaPayload(data: Record<string, unknown>) {
  const {
    cliente_nome: _cn,
    valor_total: _vt,
    empresa_emitente_nome: _en,
    uf_origem: _uo,
    operacao_fiscal: _of,
    ...rest
  } = data;
  return rest;
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
  getAll: async () => (await api.get<Proposta[]>(propostasPath)).data,
  getById: async (id: number) => (await api.get<Proposta>(`${propostasPath}${id}/`)).data,
  create: async (data: Omit<Proposta, 'id'>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<Proposta>(propostasPath, {
        ...stripPropostaPayload(rest as Record<string, unknown>),
        itens: stripPropostaItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<Proposta>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...stripPropostaPayload(rest as Record<string, unknown>) };
    if (itens) payload.itens = stripPropostaItens(itens);
    return (await api.patch<Proposta>(`${propostasPath}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${propostasPath}${id}/`);
  },
  convertToPedido: async (id: number) =>
    (await api.post<PedidoVenda>(`${propostasPath}${id}/converter-pedido/`, {})).data,
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
};

export const pedidosVendaService = {
  getAll: async () => (await api.get<PedidoVenda[]>(pvPath)).data,
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
};

export const pedidosCompraService = {
  getAll: async () => (await api.get<PedidoCompra[]>(pcPath)).data,
  getById: async (id: number) => (await api.get<PedidoCompra>(`${pcPath}${id}/`)).data,
  create: async (data: Omit<PedidoCompra, 'id'>) => {
    const { fornecedor_nome: _fn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<PedidoCompra>(pcPath, {
        ...rest,
        itens: stripPedidoItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<PedidoCompra>) => {
    const { fornecedor_nome: _fn, valor_total: _vt, itens, ...rest } = data;
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
};
