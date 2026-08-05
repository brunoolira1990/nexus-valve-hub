import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Estoque from '@/pages/Estoque';
import AtendimentosEstoque from '@/pages/AtendimentosEstoque';
import CTeEntrada from '@/pages/CTeEntrada';
import CTeHistoricoImportado from '@/pages/CTeHistoricoImportado';
import RegrasFiscais from '@/pages/RegrasFiscais';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';

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
  setFilters: vi.fn(),
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: () => paginatedEmpty,
}));

vi.mock('@/services/api/outros', () => ({
  estoqueService: {
    listSaldosPaginated: vi.fn(),
    getSaldosConsolidados: vi.fn().mockResolvedValue([]),
  },
  atendimentosEstoqueService: {
    listPaginated: vi.fn(),
    linhasConferenciaElegiveis: vi.fn(),
    vincular: vi.fn(),
  },
}));

vi.mock('@/services/api/atendimentosOperacionais', () => ({
  atendimentosOperacionaisService: { listPaginated: vi.fn(), get: vi.fn(), kpis: vi.fn() },
}));

vi.mock('@/services/api/alocacaoAtendimento', () => ({
  alocacaoAtendimentoService: { get: vi.fn(), update: vi.fn(), opcoesFornecedores: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/components/comercial/ClienteComercialField', () => ({
  ClienteComercialField: () => null,
}));
vi.mock('@/components/comercial/ProdutoComercialField', () => ({
  ProdutoComercialField: () => null,
}));

vi.mock('@/services/api/fiscal', () => ({
  cteEntradasService: {
    listPaginated: vi.fn(),
    delete: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('@/services/api/cteHistoricoImportado', () => ({
  cteHistoricoImportadoService: {
    listPaginated: vi.fn(),
    importarXmls: vi.fn(),
    resumoGerencial: vi.fn().mockResolvedValue({ totais: {}, indicadores_gerenciais: {}, base_comparativa: {} }),
    transportadorasGerencial: vi.fn().mockResolvedValue({ transportadoras: [] }),
    serieMensalGerencial: vi.fn().mockResolvedValue({ meses: [] }),
    serieTrimestralGerencial: vi.fn().mockResolvedValue({ trimestres: [] }),
    getById: vi.fn(),
  },
}));

vi.mock('@/services/api/transportadoras', () => ({
  transportadorasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/empresas', () => ({
  empresasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/regras-fiscais', () => ({
  regrasFiscaisService: { listPaginated: vi.fn(), delete: vi.fn(), create: vi.fn(), update: vi.fn() },
}));

vi.mock('@/services/api/cenarios-fiscais-saida', () => ({
  cenariosFiscaisSaidaService: {
    getAll: vi.fn().mockResolvedValue([]),
    getEscopos: vi.fn().mockResolvedValue([]),
    getMatrizEscopo: vi.fn(),
  },
}));

vi.mock('@/services/api/cenarios-fiscais-entrada', () => ({
  cenariosFiscaisEntradaService: {
    getAll: vi.fn().mockResolvedValue([]),
    getEscopos: vi.fn().mockResolvedValue([]),
    getMatrizEscopo: vi.fn(),
    createEscopo: vi.fn(),
  },
}));

vi.mock('@/services/api/regras-fiscais-entrada', () => ({
  regrasFiscaisEntradaService: {
    getById: vi.fn(),
    delete: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    duplicar: vi.fn(),
  },
}));

vi.mock('@/services/api/regras-fiscais-saida', () => ({
  regrasFiscaisSaidaService: {
    getById: vi.fn(),
    delete: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

const CHAVE_CTE = '35260112345678901234567890123456789012345678';

describe('ERP 4.0.9.3 — migração visual Nexus (Estoque/CT-e/Fiscal)', () => {
  it('Estoque/Saldos renderiza PageHeader e DataTable', () => {
    render(
      <MemoryRouter>
        <Estoque />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Estoque / Saldos' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Produto' })).toBeInTheDocument();
    expect(screen.getByText('Nenhum saldo encontrado para os filtros atuais.')).toBeInTheDocument();
  });

  it('Atendimentos Operacionais renderiza PageHeader e tabela', () => {
    render(
      <MemoryRouter>
        <AtendimentosEstoque />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Atendimentos Operacionais' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Documento' })).toBeInTheDocument();
  });

  it('CT-e Entrada renderiza DataTable', () => {
    render(
      <MemoryRouter>
        <CTeEntrada />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'CT-e Entrada' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Transportadora' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'ICMS' })).toBeInTheDocument();
    expect(screen.getByText('Nenhum CT-e operacional encontrado.')).toBeInTheDocument();
  });

  it('chave resumida não exibe XML/chave completa na listagem', () => {
    const resumida = chaveNfeResumida(CHAVE_CTE);
    expect(resumida).not.toBe(CHAVE_CTE);
    expect(resumida.length).toBeLessThan(CHAVE_CTE.length);
  });

  it('Histórico XML CT-e não renderiza chave completa na listagem vazia', () => {
    render(
      <MemoryRouter>
        <CTeHistoricoImportado />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Histórico XML CT-e' })).toBeInTheDocument();
    expect(screen.getByText('Nenhum XML de CT-e encontrado.')).toBeInTheDocument();
    expect(screen.queryByText(CHAVE_CTE)).not.toBeInTheDocument();
  });

  it('Regras Fiscais renderiza DataTable na aba legada', () => {
    render(
      <MemoryRouter>
        <RegrasFiscais />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Regras Fiscais' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'NCM' })).toBeInTheDocument();
    expect(screen.getByText('Nenhuma regra fiscal encontrada.')).toBeInTheDocument();
  });

  it('StatusBadge renderiza tokens de estoque e CT-e', () => {
    render(
      <div>
        <StatusBadge status="baixo_estoque" />
        <StatusBadge status="processado" />
        <StatusBadge status="incompleto" />
      </div>,
    );
    expect(screen.getByText('Baixo estoque')).toBeInTheDocument();
    expect(screen.getByText('Processado')).toBeInTheDocument();
    expect(screen.getByText('Incompleto')).toBeInTheDocument();
  });
});
