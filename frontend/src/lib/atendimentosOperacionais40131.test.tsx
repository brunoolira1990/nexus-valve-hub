import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AtendimentosEstoque from '@/pages/AtendimentosEstoque';
import type { AtendimentoOperacionalItem } from '@/types/atendimentosOperacionais';

const row: AtendimentoOperacionalItem = {
  id: 1,
  pedido_venda: { id: 10, numero: 'PV-20260521-0002' },
  faturamento: { id: 5, numero_faturamento: 'FAT-20260522-0001' },
  nfe_saida: { id: 2, titulo: 'NF-e Homologação nº 000000002 — Série 0' },
  cliente: { id: 3, nome: 'DYNATECH INDUSTRIAS QUIMICAS LTDA' },
  produto: { id: 20, codigo: 'ABC', descricao: 'Produto ABC' },
  quantidade_necessaria: '10.000',
  quantidade_atendida: '4.000',
  quantidade_pendente: '6.000',
  tipo_atendimento: 'RETIRADA_FORNECEDOR',
  tipo_atendimento_label: 'Retirada no fornecedor',
  status_entrada_fiscal: 'PENDENTE',
  status_entrada_fiscal_label: 'Entrada pendente',
  origem_fisica: 'FORNECEDOR',
  origem_fisica_label: 'Fornecedor',
  destino_fisico: 'CLIENTE',
  destino_fisico_label: 'Cliente',
  fornecedor: { id: 7, nome: 'FORNECEDOR XYZ LTDA' },
  pedido_compra: null,
  nfe_entrada: null,
  cte: null,
  badges: [{ label: 'Retirada fornecedor', status: 'retirada_fornecedor', variant: 'info' }],
  alertas: ['Sem pedido de compra vinculado'],
  observacao_operacional: '',
};

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: () => ({
    items: [row],
    count: 1,
    page: 1,
    pageSize: 20,
    totalPages: 1,
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    filters: { somente_pendentes: 'true' },
    setFilter: vi.fn(),
    setFilters: vi.fn(),
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

vi.mock('@/services/api/atendimentosOperacionais', () => ({
  atendimentosOperacionaisService: {
    listPaginated: vi.fn(),
    get: vi.fn(),
    kpis: vi.fn(),
  },
}));

vi.mock('@/services/api/alocacaoAtendimento', () => ({
  alocacaoAtendimentoService: {
    get: vi.fn().mockResolvedValue({
      id: 1,
      produto_id: 20,
      produto_codigo: 'ABC',
      produto_nome: 'Produto ABC',
      pedido_venda_numero: 'PV-20260521-0002',
      quantidade_necessaria: '10',
      quantidade_atendida: '4',
      quantidade_pendente: '6',
      tipo_atendimento: 'RETIRADA_FORNECEDOR',
      status_entrada_fiscal: 'PENDENTE',
      origem_fisica: 'FORNECEDOR',
      destino_fisico: 'CLIENTE',
      observacao_operacional: '',
      vinculos: {},
    }),
    update: vi.fn(),
    opcoesFornecedores: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('@/components/comercial/ClienteComercialField', () => ({
  ClienteComercialField: () => <div data-testid="filtro-cliente" />,
}));
vi.mock('@/components/comercial/ProdutoComercialField', () => ({
  ProdutoComercialField: () => <div data-testid="filtro-produto" />,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <AtendimentosEstoque />
    </MemoryRouter>,
  );
}

describe('ERP 4.0.13.1 — Atendimentos Operacionais', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renderiza título Atendimentos Operacionais', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: 'Atendimentos Operacionais' })).toBeInTheDocument();
  });

  it('não mostra filtro Produto (ID) nem NF saída (ID)', () => {
    renderPage();
    expect(screen.queryByLabelText(/Produto \(ID\)/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/NF saída \(ID\)/i)).not.toBeInTheDocument();
  });

  it('mostra busca livre e filtros operacionais', () => {
    renderPage();
    expect(
      screen.getByPlaceholderText(/Buscar por PV, cliente, produto, fornecedor/i),
    ).toBeInTheDocument();
    expect(screen.getByText('Tipo de atendimento')).toBeInTheDocument();
    expect(screen.getByText('Entrada fiscal')).toBeInTheDocument();
    expect(screen.getByTestId('filtro-cliente')).toBeInTheDocument();
    expect(screen.getByTestId('filtro-produto')).toBeInTheDocument();
  });

  it('lista alocação com PV, cliente e produto', () => {
    renderPage();
    expect(screen.getByText('PV-20260521-0002')).toBeInTheDocument();
    expect(screen.getByText('DYNATECH INDUSTRIAS QUIMICAS LTDA')).toBeInTheDocument();
    expect(screen.getByText('ABC')).toBeInTheDocument();
  });

  it('mostra badges de atendimento', () => {
    renderPage();
    expect(screen.getByText('Retirada fornecedor')).toBeInTheDocument();
  });

  it('mostra vínculos legíveis', () => {
    renderPage();
    expect(screen.getByText(/Forn.: FORNECEDOR XYZ LTDA/)).toBeInTheDocument();
  });

  it('botão editar abre formulário com aviso de segurança', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /Editar/i }));
    expect(await screen.findByText(/não movimenta estoque/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Editar atendimento operacional/i })).toBeInTheDocument();
  });
  it('mostra controles de paginação quando há registros', () => {
    renderPage();
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeInTheDocument();
  });
});

