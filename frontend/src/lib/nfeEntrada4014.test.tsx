import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NFeEntrada from '@/pages/NFeEntrada';
import { nfeEntradasService } from '@/services/api/fiscal';

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: () => ({
    items: [],
    count: 0,
    page: 1,
    pageSize: 25,
    totalPages: 0,
    search: '',
    setSearch: vi.fn(),
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: {
    listPaginated: vi.fn(),
    importarEntradaPropriaEmitida: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

describe('NFeEntrada 4014', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exibe ação Importar entrada própria já emitida separada de Emitir', () => {
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole('button', { name: /Importar entrada própria já emitida/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /^Emitir entrada própria$/i }).length).toBeGreaterThan(0);
  });

  it('abre modal de importação ao clicar na ação', () => {
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getAllByRole('button', { name: /Importar entrada própria já emitida/i })[0]);
    expect(screen.getByText(/XML de NF-e de entrada própria já emitida/i)).toBeInTheDocument();
    expect(nfeEntradasService.importarEntradaPropriaEmitida).not.toHaveBeenCalled();
  });
});
