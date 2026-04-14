import api from './config';
import type { ItemPedido, ItemProposta, PedidoCompra, PedidoVenda, Proposta } from '@/types';

function stripPropostaItens(itens: ItemProposta[]) {
  return itens.map(({ id: _id, produto_nome: _p, ...rest }) => rest);
}

function stripPedidoItens(itens: ItemPedido[]) {
  return itens.map(({ id: _id, produto_nome: _p, corrida_numero: _c, ...rest }) => rest);
}

const propostasPath = 'propostas/';
const pvPath = 'pedidos-venda/';
const pcPath = 'pedidos-compra/';

export const propostasService = {
  getAll: async () => (await api.get<Proposta[]>(propostasPath)).data,
  getById: async (id: number) => (await api.get<Proposta>(`${propostasPath}${id}/`)).data,
  create: async (data: Omit<Proposta, 'id'>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<Proposta>(propostasPath, {
        ...rest,
        itens: stripPropostaItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<Proposta>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...rest };
    if (itens) payload.itens = stripPropostaItens(itens);
    return (await api.patch<Proposta>(`${propostasPath}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${propostasPath}${id}/`);
  },
};

export const pedidosVendaService = {
  getAll: async () => (await api.get<PedidoVenda[]>(pvPath)).data,
  getById: async (id: number) => (await api.get<PedidoVenda>(`${pvPath}${id}/`)).data,
  create: async (data: Omit<PedidoVenda, 'id'>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<PedidoVenda>(pvPath, {
        ...rest,
        itens: stripPedidoItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<PedidoVenda>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...rest };
    if (itens) payload.itens = stripPedidoItens(itens);
    return (await api.patch<PedidoVenda>(`${pvPath}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${pvPath}${id}/`);
  },
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
};
