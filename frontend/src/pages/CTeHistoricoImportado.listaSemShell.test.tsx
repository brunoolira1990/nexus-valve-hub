import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CTeHistoricoImportado from '@/pages/CTeHistoricoImportado';
import { usePaginatedList } from '@/hooks/usePaginatedList';

/**
 * Trava da decisão 3.18-4 estendida à base de CT-e Importada (Fase 1 PR 2).
 *
 * `/cte-historico-importado` é a GRADE de CT-e importados; o chatter desta entidade vive no
 * CTeHistoricoDetalheModal (aba 'Histórico', plugado no PR 2 com entityId = cteId), nunca na
 * grade. Mesmos motivos técnicos da 3.18-4: o FormShell não encaminha searchValue/onSearch
 * (a busca desta tela é exatamente o `searchValue`/`onSearch` do PageHeader), o
 * StatusPipeline exige currentKey único, e o Chatter exige entityId.
 */

const mockReload = vi.fn();
const mockSetSearch = vi.fn();
const mockSetFilters = vi.fn();

const paginatedListBase = {
  items: [] as unknown[],
  count: 0,
  page: 1,
  pageSize: 25,
  totalPages: 0,
  search: '',
  setSearch: mockSetSearch,
  setPage: vi.fn(),
  setPageSize: vi.fn(),
  ordering: '',
  setOrdering: vi.fn(),
  filters: {} as Record<string, string>,
  setFilter: vi.fn(),
  setFilters: mockSetFilters,
  loading: false,
  error: null,
  reload: mockReload,
};

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock('@/hooks/usePaginatedList', () => ({ usePaginatedList: vi.fn() }));

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

vi.mock('@/services/api/transportadoras', () => ({
  transportadorasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

// O modal é onde o chatter do CT-e foi plugado (PR 2); mockar aqui prova que a GRADE não o
// monta por cima nem renderiza chatter/linha de histórico fora de uma linha específica.
vi.mock('@/components/fiscal/CTeHistoricoDetalheModal', () => ({
  CTeHistoricoDetalheModal: () => null,
}));

function renderLista() {
  return render(
    <MemoryRouter>
      <CTeHistoricoImportado />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(usePaginatedList).mockReturnValue(paginatedListBase as never);
});

describe('CTeHistoricoImportado (grade) — permanece fora do FormShell (trava 3.18-4, PR 2)', () => {
  it('usa PageHeader com a busca nativa (searchValue/onSearch) e não monta shell, pipeline ou chatter', async () => {
    renderLista();

    expect(
      await screen.findByRole('heading', { name: 'Base de CT-e Importada' }),
    ).toBeInTheDocument();

    // A busca É o PageHeader: SearchInput padrão com placeholder 'Buscar…' ligado ao setSearch.
    const busca = screen.getByPlaceholderText('Buscar…');
    fireEvent.change(busca, { target: { value: '990' } });
    expect(mockSetSearch).toHaveBeenCalledWith('990');

    expect(screen.queryByTestId('form-shell')).toBeNull();
    expect(screen.queryByTestId('form-shell-header')).toBeNull();
    expect(screen.queryByTestId('form-shell-content')).toBeNull();
    expect(screen.queryByTestId('status-pipeline')).toBeNull();
    expect(screen.queryByTestId('chatter')).toBeNull();
  });

  it('mantém o empty state da tabela e as ações da grade (Detalhes), sem banda de status de tela', async () => {
    renderLista();

    expect(
      await screen.findByText('Nenhum XML de CT-e encontrado.'),
    ).toBeInTheDocument();
    expect(screen.queryByTestId('status-pipeline')).toBeNull();
    expect(screen.queryByTestId('chatter')).toBeNull();
  });

  it('o status de cada linha segue sendo badge de tabela quando há linhas', async () => {
    paginatedListBase.items.push({
      id: 77,
      chave_acesso: '2'.repeat(44),
      numero: '10',
      serie: '1',
      dh_emissao: '2026-07-01T10:00:00',
      transportadora_nome: 'Trans teste',
      empresa_tomadora_nome: 'Nexus',
      valor_total_servico: 500,
      status_visual: 'VALIDO',
      status_conferencia: '',
      classificacao_dfe: [],
      tem_xml_conteudo: false,
    });
    renderLista();

    expect(await screen.findByRole('button', { name: 'Detalhes' })).toBeInTheDocument();
    expect(screen.queryByTestId('status-pipeline')).toBeNull();
    expect(screen.queryByTestId('chatter')).toBeNull();
    paginatedListBase.items.length = 0;
  });
});
