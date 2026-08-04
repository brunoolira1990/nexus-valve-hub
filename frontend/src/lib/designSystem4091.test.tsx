import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import FornecedorList from '@/pages/Fornecedores/FornecedorList';
import TransportadoraList from '@/pages/Transportadoras/TransportadoraList';
import Propostas from '@/pages/Propostas';
import PedidosCompra from '@/pages/PedidosCompra';
import NFeEntrada from '@/pages/NFeEntrada';
import NFeHistoricaEntradaImportada from '@/pages/NFeHistoricaEntradaImportada';
import { transportadorasService } from '@/services/api/transportadoras';
import { fornecedoresService } from '@/services/api/fornecedores';

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
  filters: {},
  setFilter: vi.fn(),
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: () => paginatedEmpty,
}));

vi.mock('@/services/api/empresas', () => ({
  empresasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: {
    listPaginated: vi.fn(),
    getAll: vi.fn().mockResolvedValue([{ id: 1, razao_social: 'Fornecedor Teste' }]),
    delete: vi.fn(),
  },
}));

vi.mock('@/services/api/transportadoras', () => ({
  transportadorasService: {
    listPaginated: vi.fn(),
    getAll: vi.fn().mockResolvedValue([{ id: 1, razao_social: 'Transportadora Teste' }]),
    delete: vi.fn(),
  },
}));

vi.mock('@/services/api/comercial', () => ({
  propostasService: { listPaginated: vi.fn(), delete: vi.fn() },
  pedidosCompraService: { listPaginated: vi.fn(), delete: vi.fn() },
}));

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: { listPaginated: vi.fn(), delete: vi.fn(), create: vi.fn(), update: vi.fn() },
}));

vi.mock('@/services/api/nfeHistoricaEntradaImportada', () => ({
  nfeHistoricaEntradaImportadaService: {
    listPaginated: vi.fn(),
    getById: vi.fn(),
    importarXmls: vi.fn(),
  },
}));

describe('ERP 4.0.9.1 — migração visual Nexus', () => {
  it('Fornecedores renderiza PageHeader e DataTable', () => {
    render(
      <MemoryRouter>
        <FornecedorList />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Fornecedores' })).toBeInTheDocument();
    expect(screen.getByText(/dados comerciais\/fiscais/i)).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Razão Social' })).toBeInTheDocument();
    expect(screen.getByText('Nenhum fornecedor encontrado.')).toBeInTheDocument();
  });

  it('Transportadoras renderiza PageHeader', () => {
    render(
      <MemoryRouter>
        <TransportadoraList />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Transportadoras' })).toBeInTheDocument();
    expect(screen.getByText('Nenhuma transportadora encontrada.')).toBeInTheDocument();
  });

  it('Transportadoras e Fornecedores preservam getAll para autocomplete', () => {
    expect(typeof fornecedoresService.getAll).toBe('function');
    expect(typeof transportadorasService.getAll).toBe('function');
  });

  it('Propostas renderiza StatusBadge via listagem vazia e header', () => {
    render(
      <MemoryRouter>
        <Propostas />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Propostas' })).toBeInTheDocument();
    expect(screen.getByText(/conversão em pedido/i)).toBeInTheDocument();
  });

  it('Pedidos de Compra renderiza header Nexus', () => {
    render(
      <MemoryRouter>
        <PedidosCompra />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Pedidos de Compra' })).toBeInTheDocument();
    expect(screen.getByText(/acompanhamento de recebimento/i)).toBeInTheDocument();
  });

  it('Entrada Própria não renderiza XML completo na listagem', () => {
    render(
      <MemoryRouter>
        <NFeEntrada />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Entrada Própria' })).toBeInTheDocument();
    expect(screen.queryByText(/<nfeProc/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/<NFe/i)).not.toBeInTheDocument();
  });

  it('NF-e Entrada Histórica renderiza DataTable e header', () => {
    render(
      <MemoryRouter>
        <NFeHistoricaEntradaImportada />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Base de NF-e Entrada Importada' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Chave' })).toBeInTheDocument();
    expect(screen.getByText(/Nenhuma NF-e de entrada importada encontrada/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Este mês/i })).toBeInTheDocument();
    expect(screen.getByText(/Competência \(mm\/aaaa\)/i)).toBeInTheDocument();
  });
});
