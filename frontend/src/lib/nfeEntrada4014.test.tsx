import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NFeEntrada from '@/pages/NFeEntrada';
import { nfeEntradasService } from '@/services/api/fiscal';
import { labelStatusOperacionalNfeEntrada } from '@/lib/nfeEntradaOperacionalLabels';

const mockReload = vi.fn();

const paginatedListBase = {
  page: 1,
  pageSize: 25,
  totalPages: 0,
  search: '',
  setSearch: vi.fn(),
  setPage: vi.fn(),
  setPageSize: vi.fn(),
  ordering: '',
  setOrdering: vi.fn(),
  filters: {} as Record<string, string>,
  setFilter: vi.fn(),
  setFilters: vi.fn(),
  reload: mockReload,
};

const entradaPropria: import('@/types').NFeEntrada = {
  id: 42,
  numero: '1001',
  serie: '1',
  chave_acesso: '35250612345678901234567890123456789012345678',
  fornecedor_nome: 'Empresa Nexus Ltda',
  destinatario_nome: 'Cliente ABC',
  data: '2025-06-01',
  valor_total: 1234.56,
  tipo_origem: 'ENTRADA_PROPRIA_IMPORTADA',
  tipo_origem_label: 'Entrada própria',
  status_operacional: 'IMPORTADA_PENDENTE_CONFERENCIA',
  status_operacional_label: 'Importada — pendente conferência',
  importado_em: '2025-06-02T10:30:00',
  itens: [],
};

const entradaManual: import('@/types').NFeEntrada = {
  id: 7,
  numero: '200',
  fornecedor_nome: 'Fornecedor Manual',
  data: '2025-05-15',
  valor_total: 500,
  tipo_origem: 'MANUAL',
  status_operacional: 'RASCUNHO',
  status_operacional_label: 'Rascunho',
  itens: [],
};

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: vi.fn(() => ({
    ...paginatedListBase,
    items: [],
    count: 0,
    loading: false,
    error: null,
  })),
}));

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: {
    listPaginated: vi.fn(),
    getById: vi.fn(),
    importarEntradaPropriaEmitida: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('@/components/fiscal/NFeEntradaDetalheDrawer', () => ({
  NFeEntradaDetalheDrawer: ({ open, nfeId }: { open: boolean; nfeId: number | null }) =>
    open ? (
      <div data-testid="nfe-entrada-detalhe-drawer" data-nfe-id={nfeId}>
        Detalhes da NF-e de entrada
      </div>
    ) : null,
}));

vi.mock('@/components/fiscal/NFeEntradaRevisaoDrawer', () => ({
  NFeEntradaRevisaoDrawer: ({ open, nfeId }: { open: boolean; nfeId: number | null }) =>
    open ? (
      <div data-testid="nfe-entrada-revisao-drawer" data-nfe-id={nfeId}>
        Revisão da NF-e de entrada
      </div>
    ) : null,
}));

import { usePaginatedList } from '@/hooks/usePaginatedList';
import { toast } from 'sonner';

describe('NFeEntrada 4014', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [],
      count: 0,
      loading: false,
      error: null,
    });
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

  it('exibe valor em formato BRL na listagem', () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [entradaPropria],
      count: 1,
      totalPages: 1,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    expect(screen.getByText(/R\$\s*1\.234,56/)).toBeInTheDocument();
  });

  it('exibe status amigável sem enum cru', () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [entradaPropria],
      count: 1,
      totalPages: 1,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    expect(screen.getByText('Pendente conferência')).toBeInTheDocument();
    expect(screen.queryByText('IMPORTADA_PENDENTE_CONFERENCIA')).not.toBeInTheDocument();
    expect(labelStatusOperacionalNfeEntrada('IMPORTADA_PENDENTE_CONFERENCIA')).toBe('Pendente conferência');
  });

  it('renderiza Revisar dados, Copiar chave e Ver detalhes para entrada própria importada', () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [entradaPropria],
      count: 1,
      totalPages: 1,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Revisar dados da NF-e/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Copiar chave NF-e/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ver detalhes da NF-e/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Conferir NF-e/i })).not.toBeInTheDocument();
  });

  it('não exibe Revisar dados para entrada manual', () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [entradaManual],
      count: 1,
      totalPages: 1,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: /Revisar dados da NF-e/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ver detalhes da NF-e/i })).toBeInTheDocument();
  });

  it('copia chave NF-e e exibe toast de sucesso', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [entradaPropria],
      count: 1,
      totalPages: 1,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Copiar chave NF-e/i }));
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(entradaPropria.chave_acesso);
      expect(toast.success).toHaveBeenCalledWith('Chave NF-e copiada para a área de transferência.');
    });
  });

  it('abre drawer de revisão ao clicar em Revisar dados', () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [entradaPropria],
      count: 1,
      totalPages: 1,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Revisar dados da NF-e/i }));
    const drawer = screen.getByTestId('nfe-entrada-revisao-drawer');
    expect(drawer).toHaveAttribute('data-nfe-id', '42');
    expect(screen.queryByTestId('nfe-entrada-detalhe-drawer')).not.toBeInTheDocument();
  });

  it('abre drawer de detalhes ao clicar em Ver detalhes', () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [entradaPropria],
      count: 1,
      totalPages: 1,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Ver detalhes da NF-e/i }));
    const drawer = screen.getByTestId('nfe-entrada-detalhe-drawer');
    expect(drawer).toHaveAttribute('data-nfe-id', '42');
    expect(screen.queryByTestId('nfe-entrada-revisao-drawer')).not.toBeInTheDocument();
  });

  it('exibe skeleton durante loading', () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedListBase,
      items: [],
      count: 0,
      loading: true,
      error: null,
    });
    const { container } = render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    expect(container.querySelector('.nexus-skeleton')).toBeTruthy();
  });

  it('exibe estado vazio quando não há registros', () => {
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Nenhuma NF-e de entrada operacional encontrada/i)).toBeInTheDocument();
  });
});
