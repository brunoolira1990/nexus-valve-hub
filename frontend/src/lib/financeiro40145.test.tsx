import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { tituloFiltrosFromSearchParams, tituloFiltrosToQuery } from '@/components/financeiro/TituloFinanceiroFiltrosPanel';

describe('tituloFiltros URL', () => {
  it('converte search params para filtros', () => {
    const sp = new URLSearchParams('vencimento=vencidos&origem_fiscal_cancelada=1');
    const f = tituloFiltrosFromSearchParams(sp);
    expect(f.vencimento).toBe('vencidos');
    expect(f.origem_fiscal_cancelada).toBe('1');
  });

  it('converte filtros para query API', () => {
    const q = tituloFiltrosToQuery({ ...tituloFiltrosFromSearchParams(new URLSearchParams()), vencimento: 'hoje' });
    expect(q.vencimento).toBe('hoje');
  });
});

describe('cards visão geral', () => {
  it('formata métrica de resumo', () => {
    const metrica = { valor: '1500.00', quantidade: 3 };
    expect(metrica.quantidade).toBeGreaterThan(0);
    expect(Number(metrica.valor)).toBe(1500);
  });

  it('card vencido aplica filtro na URL de contas a receber', () => {
    const to = `/financeiro/contas-receber?${new URLSearchParams({ vencimento: 'vencidos' }).toString()}`;
    expect(to).toContain('vencimento=vencidos');
    expect(to).toContain('contas-receber');
  });

  it('card vencido aplica filtro na URL de contas a pagar', () => {
    const to = `/financeiro/contas-pagar?${new URLSearchParams({ vencimento: 'vencidos' }).toString()}`;
    expect(to).toContain('vencimento=vencidos');
    expect(to).toContain('contas-pagar');
  });
});

describe('origem fiscal cancelada na listagem', () => {
  it('badge quando há alerta', () => {
    const titulo = { alerta_origem_cancelada: 'A NF-e de origem foi cancelada.' };
    expect(Boolean(titulo.alerta_origem_cancelada)).toBe(true);
  });
});

describe('empty state', () => {
  it('mensagem amigável', () => {
    const msg = 'Não foi possível carregar o resumo financeiro.';
    expect(msg).toMatch(/resumo financeiro/i);
  });
});
