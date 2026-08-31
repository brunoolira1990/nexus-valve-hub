import { describe, expect, it } from 'vitest';
import {
  filtrarCotacoes,
  labelOrigemCotacao,
  labelStatusCotacao,
  menorPrecoRespondido,
  novaCotacaoComPropostaPath,
  respostaPodeSerSelecionada,
} from './cotacaoFornecedores';
import type { CotacaoFornecedor, CotacaoFornecedorRespostaItem } from '@/types';

const resposta = (patch: Partial<CotacaoFornecedorRespostaItem>): CotacaoFornecedorRespostaItem => ({
  id: 1,
  participante: 1,
  cotacao_item: 1,
  fornecedor_id: 1,
  fornecedor_nome: 'Fornecedor',
  preco_unitario: 10,
  quantidade_atendida: 1,
  prazo_entrega: '',
  condicao_pagamento: '',
  frete: null,
  frete_tipo: '',
  marca_fabricante: '',
  validade: null,
  observacao: '',
  status_item: 'RESPONDIDO',
  selecionada_como_referencia: false,
  selecionada_por: null,
  selecionada_por_nome: '',
  selecionada_em: null,
  ...patch,
});

describe('cotacaoFornecedores', () => {
  it('traduz estados principais sem escolher fornecedor automaticamente', () => {
    expect(labelStatusCotacao('SEM_RETORNO')).toBe('Sem retorno');
    expect(labelStatusCotacao('CONCLUIDA')).toBe('Concluída');
  });

  it('permite selecionar somente resposta respondida com preço', () => {
    expect(respostaPodeSerSelecionada(resposta({ preco_unitario: 20 }))).toBe(true);
    expect(respostaPodeSerSelecionada(resposta({ status_item: 'RECUSADO', preco_unitario: null }))).toBe(false);
  });

  it('calcula menor preço apenas como destaque informativo', () => {
    expect(menorPrecoRespondido([resposta({ preco_unitario: 20 }), resposta({ id: 2, preco_unitario: 18 }), resposta({ id: 3, status_item: 'SEM_RETORNO', preco_unitario: null })])).toBe(18);
    expect(menorPrecoRespondido([resposta({ status_item: 'RECUSADO', preco_unitario: null })])).toBeNull();
  });

  it('identifica origem e monta o atalho contextual da Proposta', () => {
    expect(labelOrigemCotacao({ proposta_id: null })).toBe('Manual');
    expect(labelOrigemCotacao({ proposta_id: 42 })).toBe('Vinculada à Proposta');
    expect(novaCotacaoComPropostaPath(42)).toBe('/cotacoes-fornecedores/nova?proposta_id=42');
  });

  it('filtra a coleção carregada por busca, status e origem', () => {
    const base = {
      data: '2026-08-31', responsavel: 1, prazo_resposta: null, observacao: '', criado_em: '', atualizado_em: '', itens: [], participantes: [],
    };
    const cotacoes = [
      { ...base, id: 1, numero: 'CF-001', proposta_id: null, responsavel_nome: 'Bruno', status: 'RASCUNHO' },
      { ...base, id: 2, numero: 'CF-002', proposta_id: 42, responsavel_nome: 'Ana', status: 'CONCLUIDA' },
    ] as CotacaoFornecedor[];

    expect(filtrarCotacoes(cotacoes, { busca: '', status: 'TODOS', origem: 'MANUAL' })).toEqual([cotacoes[0]]);
    expect(filtrarCotacoes(cotacoes, { busca: 'P-0042', status: 'CONCLUIDA', origem: 'PROPOSTA' }, { 42: 'P-0042' })).toEqual([cotacoes[1]]);
    expect(filtrarCotacoes(cotacoes, { busca: 'Ana', status: 'RASCUNHO', origem: 'TODAS' }, { 42: 'P-0042' })).toEqual([]);
  });
});
