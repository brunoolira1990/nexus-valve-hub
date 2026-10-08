import { describe, expect, it } from 'vitest';

import type { ItemConferenciaNFeEntrada, NFeEntradaConferencia } from '@/types';
import {
  computarProgressoConferencia,
  itemExigeProduto,
  itemPendenteProduto,
  proximoPassoOperador,
} from '@/lib/conferenciaNfeOperadorUi';

function item(partial: Partial<ItemConferenciaNFeEntrada>): ItemConferenciaNFeEntrada {
  return {
    id: 1,
    n_item: 1,
    status: 'PENDENTE_PRODUTO',
    produto_id: null,
    ...partial,
  } as ItemConferenciaNFeEntrada;
}

describe('conferenciaNfeOperadorUi — uso e consumo', () => {
  it('não exige produto quando regra não movimenta estoque', () => {
    const it = item({
      resultado_fiscal: { movimenta_estoque: false } as ItemConferenciaNFeEntrada['resultado_fiscal'],
    });
    expect(itemExigeProduto(it)).toBe(false);
    expect(itemPendenteProduto(it)).toBe(false);
  });

  it('não exige produto quando elegibilidade é NAO_MOVIMENTA', () => {
    const it = item({
      elegibilidade_estoque: {
        status: 'NAO_MOVIMENTA',
        movimenta_estoque: false,
      } as ItemConferenciaNFeEntrada['elegibilidade_estoque'],
    });
    expect(itemExigeProduto(it)).toBe(false);
    expect(itemPendenteProduto(it)).toBe(false);
  });

  it('ainda exige produto quando movimenta estoque', () => {
    const it = item({
      resultado_fiscal: { movimenta_estoque: true } as ItemConferenciaNFeEntrada['resultado_fiscal'],
    });
    expect(itemExigeProduto(it)).toBe(true);
    expect(itemPendenteProduto(it)).toBe(true);
  });

  it('progresso e próximo passo não pedem produto em uso/consumo', () => {
    const dados = {
      status: 'EM_CONFERENCIA',
      data_entrada: '2026-06-01',
      itens: [
        item({
          id: 1,
          status: 'CONFERIDO',
          produto_id: null,
          resultado_fiscal: { movimenta_estoque: false } as ItemConferenciaNFeEntrada['resultado_fiscal'],
        }),
      ],
      resumo_fiscal: { bloqueado: 0, sem_regra: 0 },
    } as NFeEntradaConferencia;
    const progresso = computarProgressoConferencia(dados);
    expect(progresso.produtosFaltando).toBe(0);
    expect(progresso.produtosOk).toBe(1);
    expect(proximoPassoOperador(dados, progresso)).toBe('Tudo certo para finalizar a conferência.');
  });
});
