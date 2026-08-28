import { describe, expect, it } from 'vitest';
import { labelStatusCotacao, menorPrecoRespondido, respostaPodeSerSelecionada } from './cotacaoFornecedores';
import type { CotacaoFornecedorRespostaItem } from '@/types';

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
});
