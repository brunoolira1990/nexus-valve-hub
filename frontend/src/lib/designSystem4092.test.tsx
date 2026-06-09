import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Colaboradores from '@/pages/Colaboradores';
import Corridas from '@/pages/Corridas';
import Certificados from '@/pages/Certificados';
import CertificadosFornecedor from '@/pages/CertificadosFornecedor';
import { StatusBadge } from '@/components/nexus/StatusBadge';

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

vi.mock('@/services/api/colaboradores', () => ({
  colaboradoresService: {
    listPaginated: vi.fn(),
    delete: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('@/services/api/corridas', () => ({
  corridasService: { listPaginated: vi.fn(), delete: vi.fn(), create: vi.fn(), update: vi.fn() },
}));

vi.mock('@/services/api/qualidade', () => ({
  certificadosQualidadeService: { listPaginated: vi.fn().mockResolvedValue({ results: [], count: 0 }) },
}));

vi.mock('@/services/api/certificadosFornecedor', () => ({
  certificadosFornecedorService: {
    listPaginated: vi.fn().mockResolvedValue({ results: [], count: 0 }),
  },
  corridaLoteEfetivosResultadoFornecedor: vi.fn(),
  mensagemPrincipalBuscaDadosTecnicosFornecedor: vi.fn(),
}));

vi.mock('@/services/api/fiscal', () => ({
  nfeSaidasService: { getAll: vi.fn().mockResolvedValue([]) },
  nfeEntradasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/nfeHistoricaImportada', () => ({
  nfeHistoricaImportadaService: { list: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/nfeEntradaHistoricaImportada', () => ({
  nfeEntradaHistoricaImportadaService: { list: vi.fn().mockResolvedValue([]) },
}));

describe('ERP 4.0.9.2 — migração visual Nexus (Qualidade/Cadastros)', () => {
  it('Colaboradores renderiza PageHeader e DataTable', () => {
    render(
      <MemoryRouter>
        <Colaboradores />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Colaboradores' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Nome' })).toBeInTheDocument();
    expect(screen.getByText('Nenhum colaborador encontrado.')).toBeInTheDocument();
  });

  it('Corridas renderiza PageHeader', () => {
    render(<Corridas />);
    expect(screen.getByRole('heading', { name: 'Corridas / Lotes Técnicos' })).toBeInTheDocument();
    expect(screen.getByText(/lote técnico encontrado/i)).toBeInTheDocument();
  });

  it('StatusBadge renderiza status de qualidade', () => {
    render(
      <div>
        <StatusBadge status="emitido" />
        <StatusBadge status="validado" />
        <StatusBadge status="divergente" />
      </div>,
    );
    expect(screen.getByText('Emitido')).toBeInTheDocument();
    expect(screen.getByText('Validado')).toBeInTheDocument();
    expect(screen.getByText('Divergente')).toBeInTheDocument();
  });

  it('Certificados de Qualidade renderiza DataTable e EmptyState', () => {
    render(<Certificados />);
    expect(screen.getByRole('heading', { name: 'Certificados de Qualidade' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Número' })).toBeInTheDocument();
    expect(screen.getByText('Nenhum certificado de qualidade encontrado.')).toBeInTheDocument();
  });

  it('Certificados de Fornecedor renderiza DataTable e StatusBadge na listagem', () => {
    render(<CertificadosFornecedor />);
    expect(screen.getByRole('heading', { name: 'Certificados de Fornecedor' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Status' })).toBeInTheDocument();
    expect(screen.getByText('Nenhum certificado de fornecedor encontrado.')).toBeInTheDocument();
  });
});
