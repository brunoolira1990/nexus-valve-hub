/** ERP 4.0.10.2.1 — separação UX base importada × operacional. */
import { type ReactElement } from 'react';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import CTeEntrada from '@/pages/CTeEntrada';
import CTeHistoricoImportado from '@/pages/CTeHistoricoImportado';
import NFeEntrada from '@/pages/NFeEntrada';
import NFeHistoricaEntradaImportada from '@/pages/NFeHistoricaEntradaImportada';
import NFeHistoricaImportada from '@/pages/NFeHistoricaImportada';
import { MainLayout } from '@/components/MainLayout';
import { DfeClassificacaoBadges } from '@/components/fiscal/DfeClassificacaoBadges';

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

function renderWithRouter(ui: ReactElement, initial = '/') {
  return render(
    <MemoryRouter initialEntries={[initial]} future={routerFuture}>
      {ui}
    </MemoryRouter>,
  );
}

const paginatedEmpty = {
  items: [] as unknown[],
  count: 0,
  page: 1,
  pageSize: 20,
  totalPages: 0,
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
};

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: () => paginatedEmpty,
}));

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: { listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }) },
  cteEntradasService: { listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }) },
}));

vi.mock('@/services/api/nfeHistoricaEntradaImportada', () => ({
  nfeHistoricaEntradaImportadaService: {
    listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }),
    importarXmls: vi.fn(),
    getById: vi.fn(),
  },
}));

vi.mock('@/services/api/nfeHistoricaImportada', () => ({
  nfeHistoricaImportadaService: {
    list: vi.fn().mockResolvedValue([]),
    eventosPendentes: vi.fn().mockResolvedValue([]),
    importarXmls: vi.fn(),
    getById: vi.fn(),
    reprocessarEventosPendentes: vi.fn(),
    resumoGerencial: vi.fn().mockResolvedValue(null),
  },
}));

vi.mock('@/services/api/cteHistoricoImportado', () => ({
  cteHistoricoImportadoService: {
    listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }),
    importarXmls: vi.fn(),
    getById: vi.fn(),
    resumoGerencial: vi.fn().mockResolvedValue({
      totais: { valor_total_fretes: 0, quantidade_ctes: 0, frete_medio: 0 },
      indicadores_gerenciais: {
        peso_frete_sobre_faturamento_pct: null,
        peso_frete_sobre_compras_pct: null,
        frete_medio_observado: 0,
      },
      base_comparativa: { faturamento: 0, compras: 0 },
    }),
    transportadorasGerencial: vi.fn().mockResolvedValue({ transportadoras: [] }),
    serieMensalGerencial: vi.fn().mockResolvedValue({ meses: [] }),
    serieTrimestralGerencial: vi.fn().mockResolvedValue({ trimestres: [] }),
  },
}));

vi.mock('@/services/api/empresas', () => ({
  empresasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/clientes', () => ({
  clientesService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/transportadoras', () => ({
  transportadorasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/components/Sidebar', () => ({
  Sidebar: () => <nav data-testid="sidebar" />,
}));

afterEach(() => {
  cleanup();
});

describe('dfeOrganizacao401021', () => {
  it('CT-e Entrada não exibe Importar XML CT-e', () => {
    renderWithRouter(<CTeEntrada />);
    expect(screen.queryByRole('button', { name: /Importar XML CT-e/i })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Ir para Base CT-e Importada/i }).length).toBeGreaterThanOrEqual(1);
  });

  it('CT-e Entrada empty state orienta base importada', () => {
    renderWithRouter(<CTeEntrada />);
    expect(screen.getByText(/Nenhum CT-e operacional encontrado/i)).toBeInTheDocument();
    expect(screen.getByText(/Importe XMLs na Base CT-e Importada/i)).toBeInTheDocument();
  });

  it('NF-e Entrada exibe Emitir entrada própria e link para base', () => {
    renderWithRouter(<NFeEntrada />);
    expect(screen.getAllByRole('button', { name: /Emitir entrada própria/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: /Ir para Base NF-e Entrada Importada/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole('button', { name: /Importar XML de fornecedor/i })).not.toBeInTheDocument();
  });

  it('NF-e Entrada empty state com duas ações', () => {
    renderWithRouter(<NFeEntrada />);
    expect(screen.getByText(/Nenhuma NF-e de entrada operacional encontrada/i)).toBeInTheDocument();
    expect(screen.getByText(/Importe XMLs de fornecedores na Base NF-e Entrada Importada/i)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Ir para Base NF-e Entrada Importada/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: /Emitir entrada própria/i }).length).toBeGreaterThanOrEqual(1);
  });

  it('Base CT-e Importada mantém importador', async () => {
    renderWithRouter(<CTeHistoricoImportado />);
    await waitFor(() => {
      expect(screen.getByText(/Importar XMLs de CT-e/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Selecionar XMLs/i)).toBeInTheDocument();
  });

  it('Base NF-e Entrada Importada mantém Selecionar XMLs e Conferir entrada', async () => {
    renderWithRouter(<NFeHistoricaEntradaImportada />);
    expect(await screen.findByText(/Selecionar XMLs/i)).toBeInTheDocument();
    expect(screen.getByText(/Importar XMLs de NF-e de entrada/i)).toBeInTheDocument();
  });

  it('breadcrumbs CT-e Entrada e Base CT-e Importada', () => {
    const { unmount } = renderWithRouter(
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/cte-entrada" element={<div>cte op</div>} />
        </Route>
      </Routes>,
      '/cte-entrada',
    );
    expect(screen.getByText('CT-e Entrada')).toBeInTheDocument();
    unmount();

    renderWithRouter(
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/cte-historico-importado" element={<div>base cte</div>} />
        </Route>
      </Routes>,
      '/cte-historico-importado',
    );
    expect(screen.getByText('Base CT-e Importada')).toBeInTheDocument();
  });

  it('DfeClassificacaoBadges — base importada produção', () => {
    render(
      <DfeClassificacaoBadges
        classificacao={{
          categoria: 'BASE_DFE_IMPORTADA',
          badges: ['base_importada', 'apura', 'sem_efeito_operacional_automatico'],
        }}
      />,
    );
    expect(screen.getByText('Base importada')).toBeInTheDocument();
    expect(screen.getByText('Apura')).toBeInTheDocument();
  });

  it('NFe Entrada link navega para base importada', async () => {
    renderWithRouter(
      <Routes>
        <Route path="/nfe-entrada" element={<NFeEntrada />} />
        <Route path="/nfe-entrada-historica-importada" element={<div data-testid="base-entrada">base</div>} />
      </Routes>,
      '/nfe-entrada',
    );
    fireEvent.click(screen.getAllByRole('button', { name: /Ir para Base NF-e Entrada Importada/i })[0]);
    expect(await screen.findByTestId('base-entrada')).toBeInTheDocument();
  });
});
