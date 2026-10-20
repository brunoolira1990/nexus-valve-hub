import { describe, expect, it } from 'vitest';
import { podeSincronizarSefazLinha } from '@/lib/nfeSaidaAcoesMatriz';

const CHAVE = '35261012345678000199550010000000911000000915';

describe('podeSincronizarSefazLinha', () => {
  it('mostra o botão na nota travada em RASCUNHO após timeout de transmissão', () => {
    expect(
      podeSincronizarSefazLinha({
        status: 'RASCUNHO',
        status_emissao_sefaz: 'ERRO_TRANSMISSAO',
        chave_acesso: CHAVE,
      }),
    ).toBe(true);
  });

  it('mostra o botão para rejeitada com chave (caso da Rejeição 204)', () => {
    expect(
      podeSincronizarSefazLinha({
        status: 'RASCUNHO',
        status_emissao_sefaz: 'REJEITADA_PRODUCAO',
        chave_acesso: CHAVE,
      }),
    ).toBe(true);
  });

  it('esconde o botão do rascunho que ainda não foi transmitido (sem chave)', () => {
    expect(podeSincronizarSefazLinha({ status: 'RASCUNHO', status_emissao_sefaz: '' })).toBe(false);
    expect(podeSincronizarSefazLinha({ status: 'RASCUNHO', chave_acesso: CHAVE.slice(0, 43) })).toBe(false);
  });

  it('esconde o botão quando já autorizada ou cancelada', () => {
    expect(
      podeSincronizarSefazLinha({
        status: 'AUTORIZADA_PRODUCAO',
        status_emissao_sefaz: 'AUTORIZADA_PRODUCAO',
        chave_acesso: CHAVE,
      }),
    ).toBe(false);
    expect(
      podeSincronizarSefazLinha({ status: 'CANCELADA', status_emissao_sefaz: 'AUTORIZADA_PRODUCAO', chave_acesso: CHAVE }),
    ).toBe(false);
  });
});
