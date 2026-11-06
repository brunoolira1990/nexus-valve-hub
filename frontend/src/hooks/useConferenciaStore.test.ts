import { describe, expect, it } from 'vitest';

import {
  conferenciaReducer,
  type ConferenciaEstado,
} from '@/hooks/useConferenciaStore';
import type { ItemConferenciaNFeEntrada, NFeEntradaConferencia } from '@/types';

const item: ItemConferenciaNFeEntrada = {
  id: 5,
  item_nfe_historico: 1,
  status: 'PENDENTE_PRODUTO',
  unidade_nf: 'UN',
  quantidade_nf: 10,
  valor_unitario_nf: 5,
  valor_total_nf: 50,
};

const dados: NFeEntradaConferencia = {
  id: 20,
  nf_entrada_historica: 10,
  numero: '123',
  serie: '1',
  data_emissao: '2026-07-01',
  valor_total: 100,
  fornecedor_nome: 'Fornecedor teste',
  fornecedor_cnpj: '00000000000191',
  status: 'PENDENTE',
  divergencias_aceitas: false,
  itens: [item, { ...item, id: 6 }],
} as unknown as NFeEntradaConferencia;

const estado: ConferenciaEstado = {
  dados,
  pedidos: [],
  produtoCache: new Map(),
  erro: '',
  avisoPedido: '',
  busy: false,
};

describe('conferenciaReducer (puro, sem IO)', () => {
  it('UPDATE_ITEM aplica patch imutável na linha-alvo e preserva as demais', () => {
    const proximo = conferenciaReducer(estado, {
      type: 'UPDATE_ITEM',
      itemId: 6,
      patch: { lote: 'LOTE-A' },
    });

    expect(proximo).not.toBe(estado);
    expect(proximo.dados).not.toBe(dados);
    // A lista original não foi mutada.
    expect(estado.dados!.itens[1].lote).toBeUndefined();
    // Só a linha-alvo mudou de identidade.
    expect(proximo.dados!.itens[0]).toBe(dados.itens[0]);
    expect(proximo.dados!.itens[1]).not.toBe(dados.itens[1]);
    expect(proximo.dados!.itens[1].lote).toBe('LOTE-A');
  });

  it('UPDATE_ITEM sem dados no estado é no-op (guard `if (!dados) return` do disco)', () => {
    const vazio: ConferenciaEstado = { ...estado, dados: null };
    expect(conferenciaReducer(vazio, { type: 'UPDATE_ITEM', itemId: 6, patch: { lote: 'X' } })).toBe(vazio);
  });

  it('SET_DADOS substitui o documento e demais hubs ficam intactos', () => {
    const proximo = conferenciaReducer(estado, { type: 'SET_DADOS', dados: { ...dados, status: 'CONFERIDA' } });
    expect(proximo.dados?.status).toBe('CONFERIDA');
    expect(proximo.pedidos).toEqual([]);
    expect(proximo.erro).toBe('');
    expect(proximo.busy).toBe(false);
  });

  it('PATCH_DADOS com dados nulo não cria documento fantasma', () => {
    const vazio: ConferenciaEstado = { ...estado, dados: null };
    expect(conferenciaReducer(vazio, { type: 'PATCH_DADOS', patch: { data_entrada: '2026-07-02' } })).toBe(vazio);
    const comDados = conferenciaReducer(estado, { type: 'PATCH_DADOS', patch: { data_entrada: '2026-07-02' } });
    expect(comDados.dados?.data_entrada).toBe('2026-07-02');
    expect(comDados.dados?.itens[0]).toBe(dados.itens[0]);
  });

  it('UPSERT_PRODUTO_CACHE apenasSeAusente preserva registro já carregado', () => {
    const carregado = { id: 9, codigo_completo: 'P-9', descricao: 'Produto real' };
    const base: ConferenciaEstado = { ...estado, produtoCache: new Map([[9, carregado as never]]) };
    const stub = { id: 9, codigo_completo: '', descricao: 'stub' };

    const mantido = conferenciaReducer(base, { type: 'UPSERT_PRODUTO_CACHE', produto: stub as never, apenasSeAusente: true });
    expect(mantido.produtoCache.get(9)).toBe(carregado);

    const substituido = conferenciaReducer(base, { type: 'UPSERT_PRODUTO_CACHE', produto: stub as never });
    expect(substituido.produtoCache.get(9)).toBe(stub);
  });
});
