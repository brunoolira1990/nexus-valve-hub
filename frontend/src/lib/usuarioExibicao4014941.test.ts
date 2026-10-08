import { describe, expect, it } from 'vitest';
import {
  contextoUsuarioNomePareceStale,
  getUsuarioNomeCurto,
  getUsuarioNomeExibicao,
} from '@/lib/usuarioExibicao';

describe('usuarioExibicao 4014941', () => {
  it('prioriza colaborador_nome sobre username', () => {
    expect(
      getUsuarioNomeExibicao({
        nome_exibicao: 'admin',
        colaborador_nome: 'BRUNO PRADO DE LIRA',
        username: 'admin',
      }),
    ).toBe('BRUNO PRADO DE LIRA');
  });

  it('usa nome_exibicao quando diferente do login', () => {
    expect(
      getUsuarioNomeExibicao({
        nome_exibicao: 'BRUNO PRADO DE LIRA',
        username: 'admin',
      }),
    ).toBe('BRUNO PRADO DE LIRA');
  });

  it('usa username apenas sem colaborador nem nome', () => {
    expect(getUsuarioNomeExibicao({ username: 'admin' })).toBe('admin');
  });

  it('detecta cache stale com colaborador e nome igual ao login', () => {
    expect(
      contextoUsuarioNomePareceStale({
        colaborador_id: 1,
        colaborador_nome: 'BRUNO PRADO DE LIRA',
        nome_exibicao: 'admin',
        username: 'admin',
      }),
    ).toBe(true);
  });

  it('gera nome curto', () => {
    expect(
      getUsuarioNomeCurto({
        nome_exibicao: 'BRUNO PRADO DE LIRA',
        nome_curto: 'BRUNO P.',
      }),
    ).toBe('BRUNO P.');
  });
});
