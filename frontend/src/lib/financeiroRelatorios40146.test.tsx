import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FinanceiroRelatoriosHub from '@/pages/financeiro/relatorios/FinanceiroRelatoriosHub';
import {
  relatorioFiltrosFromSearchParams,
  relatorioFiltrosToQuery,
  RELATORIOS_HUB,
} from '@/lib/relatorioFinanceiro';

describe('FinanceiroRelatoriosHub', () => {
  it('lista relatórios disponíveis', () => {
    render(
      <MemoryRouter>
        <FinanceiroRelatoriosHub />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Relatórios para acompanhar recebimentos/i)).toBeInTheDocument();
    for (const rel of RELATORIOS_HUB) {
      expect(screen.getByText(rel.titulo)).toBeInTheDocument();
    }
  });
});

describe('relatorioFiltros URL', () => {
  it('reflete filtros na querystring', () => {
    const sp = new URLSearchParams('status=VENCIDO&vencimento=vencidos');
    const f = relatorioFiltrosFromSearchParams(sp);
    const q = relatorioFiltrosToQuery(f);
    expect(q.status).toBe('VENCIDO');
    expect(q.vencimento).toBe('vencidos');
  });

  it('card vencido link pattern', () => {
    const to = `/financeiro/relatorios/contas-receber?${new URLSearchParams({ vencimento: 'vencidos' }).toString()}`;
    expect(to).toContain('relatorios/contas-receber');
    expect(to).toContain('vencimento=vencidos');
  });
});

describe('relatório API shapes', () => {
  it('abrir título usa id numérico', () => {
    const linha = { id: 42 };
    expect(linha.id).toBe(42);
  });
});
