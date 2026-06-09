/** ERP 4.0.10.1 — organização DF-e e exclusão de homologação (UI). */
import { type ReactElement } from 'react';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import ApuracaoFiscal from '@/pages/ApuracaoFiscal';
import NFeHistoricaEntradaImportada from '@/pages/NFeHistoricaEntradaImportada';
import NFeHistoricaImportada from '@/pages/NFeHistoricaImportada';
import CTeEntrada from '@/pages/CTeEntrada';
import NFeEntrada from '@/pages/NFeEntrada';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { resolveStatusToken } from '@/design-system/tokens';

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

const { acumuloZerado, mockApuracaoGet } = vi.hoisted(() => {
  const acumuloZerado = () => ({
    quantidade_notas: 0,
    quantidade_itens: 0,
    valor_documentos: 0,
    valor_produtos: 0,
    base_icms: 0,
    valor_icms: 0,
    base_ipi: 0,
    valor_ipi: 0,
    base_pis: 0,
    valor_pis: 0,
    base_cofins: 0,
    valor_cofins: 0,
  });
  const mockApuracaoGet = vi.fn(async (params: Record<string, string | number | boolean>) => {
    const a = acumuloZerado();
    return {
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
      filtros: {
        data_inicio: String(params.data_inicio ?? ''),
        data_fim: String(params.data_fim ?? ''),
        tipo: 'AMBOS',
        fonte: 'TODOS',
      },
      resumo: {
        entrada: a,
        saida: a,
        saldo_gerencial_saida_menos_entrada: {},
      },
      icms_ipi: {
        entrada: a,
        saida: a,
        comparativo_documento: { observacao: 'teste' },
      },
      pis_cofins: { entrada: a, saida: a },
      reforma_tributaria: { por_documento: { entrada: {}, saida: {}, cte: {} } },
      agrupamentos: {},
      alertas: [],
    };
  });
  return { acumuloZerado, mockApuracaoGet };
});

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
    get: mockApuracaoGet,
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

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: { listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }) },
  cteEntradasService: { listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }) },
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('dfeOrganizacao40101', () => {
  it('apuração exibe texto de exclusão de homologação', async () => {
    await act(async () => {
      render(<ApuracaoFiscal />);
    });
    expect(screen.getByText(/homologação são sempre excluídos/i)).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Todos válidos: operacionais produção/i })).toBeInTheDocument();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 450));
    });
    expect(mockApuracaoGet).toHaveBeenCalled();
  });

  it('base NF-e saída importada — nova descrição', async () => {
    renderWithRouter(<NFeHistoricaImportada />);
    await waitFor(() => {
      expect(screen.getByText(/Base de NF-e Saída Importada/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/apuração fiscal, base contábil/i)).toBeInTheDocument();
  });

  it('base NF-e entrada importada — empty state sem erro', async () => {
    renderWithRouter(<NFeHistoricaEntradaImportada />);
    expect(await screen.findByText(/Nenhuma NF-e de entrada importada encontrada/i)).toBeInTheDocument();
    expect(screen.queryByText(/Erro ao carregar/i)).not.toBeInTheDocument();
  });

  it('CT-e entrada — botão importar XML', () => {
    render(<CTeEntrada />);
    expect(screen.getAllByRole('button', { name: /Importar XML CT-e/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole('button', { name: /^Novo CT-e$/i })).not.toBeInTheDocument();
  });

  it('NF-e entrada — emitir entrada própria e importar XML', () => {
    renderWithRouter(<NFeEntrada />);
    expect(screen.getByRole('button', { name: /Emitir entrada própria/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Importar XML de fornecedor/i })).toBeInTheDocument();
  });

  it('StatusBadge — base importada e fora da apuração', () => {
    render(
      <>
        <StatusBadge status="base_importada" />
        <StatusBadge status="fora_apuracao" />
      </>,
    );
    expect(screen.getByText('Base importada')).toBeInTheDocument();
    expect(screen.getByText('Fora da apuração')).toBeInTheDocument();
    expect(resolveStatusToken('homologacao').homologacao).toBe(true);
  });
});
