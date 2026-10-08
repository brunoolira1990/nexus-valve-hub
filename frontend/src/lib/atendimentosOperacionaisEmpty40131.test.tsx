import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AtendimentosEstoque from '@/pages/AtendimentosEstoque';

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: () => ({
    items: [],
    count: 0,
    page: 1,
    pageSize: 20,
    totalPages: 0,
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    filters: {},
    setFilter: vi.fn(),
    setFilters: vi.fn(),
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

vi.mock('@/services/api/atendimentosOperacionais', () => ({
  atendimentosOperacionaisService: { listPaginated: vi.fn(), get: vi.fn(), kpis: vi.fn() },
}));

vi.mock('@/services/api/alocacaoAtendimento', () => ({
  alocacaoAtendimentoService: { opcoesFornecedores: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/components/comercial/ClienteComercialField', () => ({
  ClienteComercialField: () => null,
}));
vi.mock('@/components/comercial/ProdutoComercialField', () => ({
  ProdutoComercialField: () => null,
}));

describe('ERP 4.0.13.1 — empty state', () => {
  it('mensagem operacional quando lista vazia', () => {
    render(
      <MemoryRouter>
        <AtendimentosEstoque />
      </MemoryRouter>,
    );
    expect(screen.getByText('Nenhum atendimento operacional encontrado.')).toBeInTheDocument();
    expect(screen.getByText(/Crie alocações de atendimento/i)).toBeInTheDocument();
  });
});
