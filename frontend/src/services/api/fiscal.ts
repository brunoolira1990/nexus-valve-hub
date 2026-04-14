import api from './config';
import type { CTeEntrada, ItemNFe, NFeEntrada, NFeSaida } from '@/types';

function stripNfItens(itens: ItemNFe[]) {
  return itens.map(({ id: _id, produto_nome: _p, corrida_numero: _c, ...rest }) => rest);
}

const nfEnt = 'nf-entradas/';
const nfSai = 'nf-saidas/';
const cte = 'cte-entradas/';

export const nfeEntradasService = {
  getAll: async () => (await api.get<NFeEntrada[]>(nfEnt)).data,
  getById: async (id: number) => (await api.get<NFeEntrada>(`${nfEnt}${id}/`)).data,
  create: async (data: Omit<NFeEntrada, 'id'>) => {
    const { fornecedor_nome: _fn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<NFeEntrada>(nfEnt, {
        ...rest,
        itens: stripNfItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<NFeEntrada>) => {
    const { fornecedor_nome: _fn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...rest };
    if (itens) payload.itens = stripNfItens(itens);
    return (await api.patch<NFeEntrada>(`${nfEnt}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${nfEnt}${id}/`);
  },
};

export const nfeSaidasService = {
  getAll: async () => (await api.get<NFeSaida[]>(nfSai)).data,
  getById: async (id: number) => (await api.get<NFeSaida>(`${nfSai}${id}/`)).data,
  create: async (data: Omit<NFeSaida, 'id'>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<NFeSaida>(nfSai, {
        ...rest,
        itens: stripNfItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<NFeSaida>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...rest };
    if (itens) payload.itens = stripNfItens(itens);
    return (await api.patch<NFeSaida>(`${nfSai}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${nfSai}${id}/`);
  },
};

export const cteEntradasService = {
  getAll: async () => (await api.get<CTeEntrada[]>(cte)).data,
  getById: async (id: number) => (await api.get<CTeEntrada>(`${cte}${id}/`)).data,
  create: async (data: Omit<CTeEntrada, 'id'>) => {
    const { transportadora_nome: _tn, tomador_nome: _tm, ...rest } = data;
    return (await api.post<CTeEntrada>(cte, rest)).data;
  },
  update: async (id: number, data: Partial<CTeEntrada>) => {
    const { transportadora_nome: _tn, tomador_nome: _tm, ...rest } = data;
    return (await api.patch<CTeEntrada>(`${cte}${id}/`, rest)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${cte}${id}/`);
  },
};
