/** ERP 4.0.10.2 — importação/recebimento DF-e (UI). */
import { type ReactElement } from 'react';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import ApuracaoFiscal from '@/pages/ApuracaoFiscal';
import NFeHistoricaEntradaImportada from '@/pages/NFeHistoricaEntradaImportada';
import NFeHistoricaImportada from '@/pages/NFeHistoricaImportada';
import CTeHistoricoImportado from '@/pages/CTeHistoricoImportado';
import CTeEntrada from '@/pages/CTeEntrada';
import NFeEntrada from '@/pages/NFeEntrada';
import { MainLayout } from '@/components/MainLayout';
import { DfeClassificacaoBadges } from '@/components/fiscal/DfeClassificacaoBadges';
import { StatusBadge } from '@/components/nexus/StatusBadge';

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

vi.mock('@/services/api/outros', () => ({
  apuracaoService: {
    get: vi.fn(async () => ({
      cards: {
        notas_entrada: 0,
        notas_saida: 0,
        valor_entradas: 0,
        valor_saidas: 0,
        icms_entrada: 0,
        icms_saida: 0,
        ipi_entrada: 0,
        ipi_saida: 0,
        pis_entrada: 0,
        pis_saida: 0,
        cofins_entrada: 0,
        cofins_saida: 0,
        alertas: 0,
      },
      filtros: { data_inicio: '', data_fim: '', tipo: 'AMBOS', fonte: 'TODOS' },
      resumo: {
        entrada: { quantidade_notas: 0, valor_documentos: 0 },
        saida: { quantidade_notas: 0, valor_documentos: 0 },
        saldo_gerencial_saida_menos_entrada: {},
      },
      icms_ipi: { entrada: {}, saida: {}, comparativo_documento: {} },
      pis_cofins: { entrada: {}, saida: {} },
      reforma_tributaria: { por_documento: { entrada: {}, saida: {}, cte: {} } },
      agrupamentos: {},
      alertas: [],
      fontes: {
        saidas_historicas_candidatas: 0,
        entradas_historicas_candidatas: 0,
      },
    })),
    exportCsvApuracao: vi.fn(),
    exportCsvAlertas: vi.fn(),
  },
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

vi.mock('@/services/api/transportadoras', () => ({
  transportadorasService: { getAll: vi.fn().mockResolvedValue([]) },
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

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: { listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }) },
  cteEntradasService: { listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }) },
}));

vi.mock('@/components/Sidebar', () => ({
  Sidebar: () => <nav data-testid="sidebar" />,
}));

afterEach(() => {
  cleanup();
});

describe('dfeOrganizacao40102', () => {
  it('base NF-e entrada importada — título correto', async () => {
    renderWithRouter(<NFeHistoricaEntradaImportada />);
    expect(await screen.findByText(/Base de NF-e Entrada Importada/i)).toBeInTheDocument();
    expect(screen.getByText(/apuração, contábil, BI e precificação/i)).toBeInTheDocument();
    expect(screen.getByText(/Sem efeito operacional automático/i)).toBeInTheDocument();
  });

  it('base NF-e saída importada — título correto', async () => {
    renderWithRouter(<NFeHistoricaImportada />);
    await waitFor(() => {
      expect(screen.getByText(/Base de NF-e Saída Importada/i)).toBeInTheDocument();
    });
  });

  it('base CT-e importada — título e texto frete', async () => {
    renderWithRouter(<CTeHistoricoImportado />);
    await waitFor(() => {
      expect(screen.getByText(/Base de CT-e Importada/i)).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(
        screen.getByText(/Alimenta apuração, custo logístico, frete médio e precificação/i),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Faturamento base para comparação/i)).toBeInTheDocument();
  });

  it('breadcrumbs não usam Histórica/XML', () => {
    renderWithRouter(
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/nfe-entrada-historica-importada" element={<div>página</div>} />
        </Route>
      </Routes>,
      '/nfe-entrada-historica-importada',
    );
    expect(screen.getByText('NF-e Entrada (base)')).toBeInTheDocument();
    expect(screen.queryByText(/Histórica\/XML/i)).not.toBeInTheDocument();
  });

  it('apuração — aviso homologação', async () => {
    await act(async () => {
      render(<ApuracaoFiscal />);
    });
    expect(screen.getByText(/homologação são sempre excluídos/i)).toBeInTheDocument();
  });

  it('NF-e entrada — emitir entrada própria (sem importador duplicado)', () => {
    renderWithRouter(<NFeEntrada />);
    expect(screen.getAllByRole('button', { name: /Emitir entrada própria/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: /Ir para Base NF-e Entrada Importada/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole('button', { name: /Importar XML de fornecedor/i })).not.toBeInTheDocument();
  });

  it('DfeClassificacaoBadges — homologação fora apuração', () => {
    render(
      <DfeClassificacaoBadges
        classificacao={{
          categoria: 'HOMOLOGACAO',
          homologacao: true,
          badges: ['homologacao', 'fora_apuracao', 'sem_valor_fiscal'],
        }}
      />,
    );
    expect(screen.getByText('Homologação')).toBeInTheDocument();
    expect(screen.getByText('Fora da apuração')).toBeInTheDocument();
  });

  it('StatusBadge — conferida e preparada', () => {
    render(
      <>
        <StatusBadge status="conferida" />
        <StatusBadge status="preparada" />
      </>,
    );
    expect(screen.getByText('Conferida')).toBeInTheDocument();
    expect(screen.getByText('Preparada')).toBeInTheDocument();
  });
});
