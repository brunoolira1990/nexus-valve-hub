/** ERP 4.0.14.x — DF-e recebidos (UI). */
import { type ReactElement } from 'react';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import CentralDfe from '@/pages/CentralDfe';
import { usePaginatedList } from '@/hooks/usePaginatedList';

const { docPendente, paginatedWithData, manifestacaoStub } = vi.hoisted(() => {
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
    estado_consolidado: 'XML_DISPONIVEL',
    estado_consolidado_label: 'XML disponível',
    nf_entrada_historica_id: 99,
    xml_armazenado: true,
  };

  const paginated = {
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
  };

  return {
    docPendente: doc,
    paginatedWithData: paginated,
    manifestacaoStub: {
      manifestacaoMap: new Map(),
      manifestacaoSomenteResumo: [] as unknown[],
      documentosCentralPorChave: new Map(),
      fechamento: null,
      detalhe: null,
      setDetalhe: vi.fn(),
      manifestRow: null,
      setManifestRow: vi.fn(),
      manifestModalKey: 0,
      abrirModalManifestacao: vi.fn(),
      confirmBaixar: null,
      setConfirmBaixar: vi.fn(),
      confirmArmazenar: null,
      setConfirmArmazenar: vi.fn(),
      confirmArmazenarCte: null,
      setConfirmArmazenarCte: vi.fn(),
      dfeDetalheRow: null,
      setDfeDetalheRow: vi.fn(),
      loadingAcaoManual: false,
      carregarManifestacao: vi.fn().mockResolvedValue(undefined),
      abrirDetalheManifestacao: vi.fn(),
      abrirDetalheDfeNfe: vi.fn(),
      iniciarManifestacaoManual: vi.fn(),
      iniciarArmazenarXmlManual: vi.fn(),
      sincronizarResumosDestinados: vi.fn().mockResolvedValue(undefined),
      executarManifestacao: vi.fn(),
      executarArmazenarXmlNfe: vi.fn(),
      executarArmazenarXmlCte: vi.fn(),
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

vi.mock('@/hooks/useManifestacaoDestinatario', () => ({
  useManifestacaoDestinatario: vi.fn(() => manifestacaoStub),
}));

vi.mock('@/components/fiscal/CTeHistoricoDetalheModal', () => ({
  CTeHistoricoDetalheModal: () => null,
}));

vi.mock('@/components/fiscal/ManifestacaoDestinatarioModals', () => ({
  ManifestacaoDestinatarioModals: () => null,
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
    capturarSefaz: vi.fn().mockResolvedValue({ ok: true }),
  },
}));

describe('CentralDfe', () => {
  beforeEach(() => {
    vi.mocked(usePaginatedList).mockReturnValue(paginatedWithData);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renderiza Inbox Fiscal com badge de estado consolidado', async () => {
    renderWithRouter(<CentralDfe />);
    expect(screen.getByRole('heading', { name: /Inbox Fiscal/i })).toBeInTheDocument();
    await waitFor(() => {
      const tabela = screen.getByRole('table');
      expect(within(tabela).getByText('10 / 1')).toBeInTheDocument();
      expect(within(tabela).getByText('Fornecedor Teste')).toBeInTheDocument();
      expect(within(tabela).getByText('XML disponível')).toBeInTheDocument();
      expect(within(tabela).getByText(/Entrada: Pendente de entrada/i)).toBeInTheDocument();
    });
  });

  it('exibe alerta fiscal visível quando motivo presente', async () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedWithData,
      items: [
        {
          ...docPendente,
          estado_consolidado: 'DIVERGENTE',
          estado_consolidado_label: 'Divergente',
          estado_consolidado_motivo: '1 item(ns) divergente(s) na conferência.',
        },
      ],
    });
    renderWithRouter(<CentralDfe />);
    await waitFor(() => {
      expect(screen.getByText(/1 item\(ns\) divergente\(s\)/i)).toBeInTheDocument();
    });
    const tabela = screen.getByRole('table');
    expect(within(tabela).getByText('Divergente')).toBeInTheDocument();
  });

  it('exibe badge de estado consolidado para CT-e na mesma listagem', async () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedWithData,
      items: [
        {
          ...docPendente,
          id: 2,
          tipo_documento: 'CTE' as const,
          tipo_label: 'CT-e Transportadora',
          estado_consolidado: 'CONFERIDO',
          estado_consolidado_label: 'Conferido',
        },
      ],
    });
    renderWithRouter(<CentralDfe />);
    await waitFor(() => {
      const tabela = screen.getByRole('table');
      expect(within(tabela).getByText('CT-e Transportadora')).toBeInTheDocument();
      expect(within(tabela).getByText('Conferido')).toBeInTheDocument();
    });
  });

  it('estado vazio quando lista sem itens', async () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedWithData,
      items: [],
      count: 0,
      totalPages: 0,
    });
    renderWithRouter(<CentralDfe />);
    expect(screen.getByText(/Nenhum DF-e encontrado no filtro atual/i)).toBeInTheDocument();
  });

  it('abre workspace ao clicar na linha', async () => {
    renderWithRouter(<CentralDfe />);
    await waitFor(() => {
      expect(screen.getByText('Fornecedor Teste')).toBeInTheDocument();
    });
    const linha = screen.getByText('Fornecedor Teste').closest('tr');
    expect(linha).toBeTruthy();
    linha?.click();
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Iniciar conferência')).toBeInTheDocument();
    });
  });
});
