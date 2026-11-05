import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NFeHistoricaEntradaImportada from '@/pages/NFeHistoricaEntradaImportada';
import { usePaginatedList } from '@/hooks/usePaginatedList';

/**
 * Trava da decisão 3.18-4 estendida à base de NF-e Entrada Importada (Fase 1 PR 2).
 *
 * `/nfe-entrada-historica-importada` é a GRADE de XMLs importados. Ela permanece fora do
 * FormShell pelos mesmos três motivos técnicos já travados para `/nfe-entrada`
 * (NFeEntrada.listaSemShell.test.tsx): o FormShell não encaminha searchValue/onSearch, o
 * StatusPipeline exige um currentKey único (cada linha tem o próprio status_conferencia),
 * e o Chatter exige entityId (não há objeto único nesta tela). O PR 2 plugou <Chatter> na
 * CONFERÊNCIA e no MODAL de CT-e — nunca numa grade — e este teste é a cerca que impede a
 * Fase 4 de "aplicar o padrão" aqui sem reabrir a decisão.
 */

const mockReload = vi.fn();
const mockSetSearch = vi.fn();
const mockSetFilter = vi.fn();
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
  setFilter: mockSetFilter,
  setFilters: mockSetFilters,
  loading: false,
  error: null,
  reload: mockReload,
};

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock('@/hooks/usePaginatedList', () => ({ usePaginatedList: vi.fn() }));

vi.mock('@/services/api/nfeHistoricaEntradaImportada', () => ({
  nfeHistoricaEntradaImportadaService: {
    listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }),
    importarXmls: vi.fn(),
    getById: vi.fn(),
    reabrir: vi.fn(),
  },
}));

vi.mock('@/services/api/empresas', () => ({
  empresasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: { getAll: vi.fn().mockResolvedValue([]) },
}));

// O drawer de reabertura é chamado pela grade; mockar evita calls de contexto no teste-trava.
vi.mock('@/components/fiscal/NFeEntradaReabrirModal', () => ({
  NFeEntradaReabrirModal: () => null,
}));

function renderLista() {
  return render(
    <MemoryRouter>
      <NFeHistoricaEntradaImportada />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(usePaginatedList).mockReturnValue(paginatedListBase as never);
});

describe('NFeHistoricaEntradaImportada (grade) — permanece fora do FormShell (trava 3.18-4, PR 2)', () => {
  it('usa PageHeader próprio e não monta shell, pipeline ou chatter', () => {
    renderLista();

    expect(screen.getByRole('heading', { name: 'Base de NF-e Entrada Importada' })).toBeInTheDocument();
    expect(screen.queryByTestId('form-shell')).toBeNull();
    expect(screen.queryByTestId('form-shell-header')).toBeNull();
    expect(screen.queryByTestId('form-shell-content')).toBeNull();
    expect(screen.queryByTestId('status-pipeline')).toBeNull();
    expect(screen.queryByTestId('chatter')).toBeNull();
  });

  it('a busca continua sendo input da própria página, ligada ao setSearch do hook', async () => {
    renderLista();

    const busca = await screen.findByPlaceholderText('Número, fornecedor, chave…');
    fireEvent.change(busca, { target: { value: '123' } });
    expect(mockSetSearch).toHaveBeenCalledWith('123');
  });

  it('o status de cada linha segue sendo badge de tabela, não banda de status da tela', async () => {
    paginatedListBase.items.push({
      id: 10,
      chave_acesso: '1'.repeat(44),
      numero: '123',
      serie: '1',
      fornecedor_nome: 'Fornecedor teste',
      dh_emissao: '2026-07-01T10:00:00',
      importado_em: '2026-07-01T11:00:00',
      status_conferencia: 'PREPARADA',
      tem_xml_conteudo: true,
      classificacao_dfe: [],
    });
    renderLista();

    expect(await screen.findByRole('button', { name: /Reabrir entrada para correção/i })).toBeInTheDocument();
    expect(screen.queryByTestId('status-pipeline')).toBeNull();
    expect(screen.queryByTestId('chatter')).toBeNull();
    paginatedListBase.items.length = 0;
  });
});
