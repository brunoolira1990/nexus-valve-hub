/** ERP 4.0.14.x — DF-e recebidos (UI). */
import { type ReactElement } from 'react';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import CentralDfe from '@/pages/CentralDfe';

const { docPendente, paginatedWithData } = vi.hoisted(() => {
  const doc = {
    id: 1,
    tipo_documento: 'NFE_ENTRADA' as const,
    chave_resumida: '1111…1111',
    chave_acesso: '1'.repeat(44),
    numero: '10',
    serie: '1',
    data_emissao: '2026-05-01',
    data_importacao: '2026-05-02T10:00:00',
    emitente_nome: 'Fornecedor Teste',
    emitente_cnpj: '11111111000111',
    uf: 'SP',
    valor_total: '100.00',
    status_entrada: 'PENDENTE_ENTRADA',
    status_entrada_label: 'Pendente de entrada',
    tipo_label: 'NF-e Fornecedor',
    detalhe_rota: '/nfe-entrada-historica-importada',
    empresa_id: 1,
  };

  return {
    docPendente: doc,
    paginatedWithData: {
      items: [doc],
      count: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
      search: '',
      setSearch: vi.fn(),
      setPage: vi.fn(),
      setPageSize: vi.fn(),
      filters: {} as Record<string, string>,
      setFilter: vi.fn(),
      setFilters: vi.fn(),
      loading: false,
      error: null as string | null,
      reload: vi.fn(),
    },
  };
});

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

function renderWithRouter(ui: ReactElement) {
  return render(
    <MemoryRouter future={routerFuture}>
      {ui}
    </MemoryRouter>,
  );
}

vi.mock('@/hooks/useAppContexto', () => ({
  useAppContexto: () => ({
    contexto: {
      empresa: { id: 1, nome_exibicao: 'Nexus Teste', cnpj: '11.111.111/0001-11' },
      usuario: { id: 1, nome: 'Admin' },
    },
    loading: false,
    refresh: vi.fn(),
  }),
}));

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: vi.fn(() => paginatedWithData),
}));

vi.mock('@/components/fiscal/CTeHistoricoDetalheModal', () => ({
  CTeHistoricoDetalheModal: () => null,
}));

vi.mock('@/services/api/centralDfe', () => ({
  centralDfeService: {
    listPaginated: vi.fn().mockResolvedValue({
      count: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
      next: null,
      previous: null,
      results: [docPendente],
      resumo: {
        total: 1,
        pendentes_entrada: 1,
        nfe_fornecedores: 1,
        cte_transportadoras: 0,
        divergentes: 0,
        ignorados: 0,
        ja_tratados: 0,
      },
      empresa: { id: 1, razao_social: 'Nexus Teste', cnpj: '11.111.111/0001-11' },
    }),
  },
}));

describe('CentralDfe', () => {
  afterEach(() => cleanup());

  it('renderiza título DF-e Recebidos e documento pendente', async () => {
    renderWithRouter(<CentralDfe />);
    expect(screen.getByRole('heading', { name: /DF-e Recebidos/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('10 / 1')).toBeInTheDocument();
      expect(screen.getByText('Fornecedor Teste')).toBeInTheDocument();
      expect(screen.getByText(/Pendente de entrada/i)).toBeInTheDocument();
    });
  });

  it('estado vazio quando lista sem itens', async () => {
    const { usePaginatedList } = await import('@/hooks/usePaginatedList');
    vi.mocked(usePaginatedList).mockReturnValueOnce({
      ...paginatedWithData,
      items: [],
      count: 0,
      totalPages: 0,
    });
    renderWithRouter(<CentralDfe />);
    expect(screen.getByText(/Nenhum DF-e pendente encontrado/i)).toBeInTheDocument();
  });
});
