import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CreditosPage } from '@/pages/financeiro/Creditos';
import { CreditoDetalheDrawer } from '@/components/financeiro/CreditoDetalheDrawer';
import { CreditoTipoEscolhaModal } from '@/components/financeiro/CreditoTipoEscolhaModal';
import { TituloFinanceiroDetalheDrawer } from '@/components/financeiro/TituloFinanceiroDetalheDrawer';
import { FinanceiroEventoHistorico } from '@/components/financeiro/FinanceiroEventoHistorico';
import {
  FINANCEIRO_ACTION_LABELS,
  creditosTemFiltroAtivo,
  getCreditoFinanceiroAcoes,
  getTituloFinanceiroAcoes,
  humanizarDescricaoFinanceira,
  linhasDetalheHistoricoFinanceiro,
} from '@/lib/financeiroUi';

vi.mock('@/services/api/clientes', () => ({
  clientesService: { search: vi.fn().mockResolvedValue([]), getAll: vi.fn() },
}));
vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: { search: vi.fn().mockResolvedValue([]), getAll: vi.fn() },
}));

const listCreditos = vi.fn();
const getCredito = vi.fn();
const getContaReceber = vi.fn();
const cancelarCredito = vi.fn();
const excluirCredito = vi.fn();

vi.mock('@/services/api/financeiro', () => ({
  financeiroService: {
    listCreditos: (...args: unknown[]) => listCreditos(...args),
    getCredito: (...args: unknown[]) => getCredito(...args),
    getContaReceber: (...args: unknown[]) => getContaReceber(...args),
    getContaPagar: vi.fn(),
    cancelarCredito: (...args: unknown[]) => cancelarCredito(...args),
    excluirCredito: (...args: unknown[]) => excluirCredito(...args),
    patchCredito: vi.fn(),
    estornarBaixa: vi.fn(),
    excluirTitulo: vi.fn(),
    cancelarTitulo: vi.fn(),
  },
}));

const creditoDisponivel = {
  id: 1,
  tipo: 'CLIENTE' as const,
  status: 'DISPONIVEL',
  valor_original: '1500.00',
  valor_utilizado: '0.00',
  saldo: '1500.00',
  pode_aplicar: true,
  pode_cancelar: true,
  pode_editar: true,
  pode_editar_completo: true,
  pode_excluir: true,
  possui_movimento: false,
  motivo: 'Ajuste manual',
  data_credito: '2026-06-02',
  origem_tipo: 'MANUAL',
  eventos: [
    {
      id: 1,
      acao: 'CRIACAO',
      descricao: 'Crédito de cliente criado no valor de R$ 1500.00.',
      valor: '1500.00',
      criado_em: '2026-06-02T16:07:00Z',
      usuario_nome: 'admin',
    },
  ],
};

const tituloManual = {
  id: 10,
  tipo: 'RECEBER' as const,
  numero: 'CR-2026-000010',
  cliente: 7,
  cliente_nome: 'Cliente Teste',
  valor_original: '500.00',
  valor_aberto: '500.00',
  valor_baixado: '0.00',
  status: 'EM_ABERTO',
  origem_tipo: 'MANUAL',
  data_emissao: '2026-06-01',
  data_vencimento: '2026-06-15',
  pode_aplicar_credito: true,
  pode_abater: true,
  pode_excluir: true,
  pode_editar: true,
  pode_cancelar: true,
};

describe('financeiroUi 4.0.14.2.1 — acabamento operacional', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listCreditos.mockResolvedValue({ count: 0, page: 1, page_size: 20, total_pages: 0, results: [] });
  });

  it('tela Créditos vazia não mostra filtros/tabela/paginação', async () => {
    render(
      <MemoryRouter>
        <CreditosPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listCreditos).toHaveBeenCalled());
    expect(screen.queryByLabelText('Filtrar por tipo')).not.toBeInTheDocument();
    expect(screen.queryByText('Todos os tipos')).not.toBeInTheDocument();
    expect(screen.getByText('Nenhum crédito registrado ainda.')).toBeInTheDocument();
  });

  it('tela Créditos vazia mostra botão único Novo crédito', async () => {
    render(
      <MemoryRouter>
        <CreditosPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listCreditos).toHaveBeenCalled());
    expect(screen.getAllByRole('button', { name: FINANCEIRO_ACTION_LABELS.novoCredito }).length).toBeGreaterThan(0);
    expect(screen.queryByText(FINANCEIRO_ACTION_LABELS.novoCreditoCliente)).not.toBeInTheDocument();
  });

  it('botão Novo crédito permite escolher Cliente ou Fornecedor', () => {
    const onEscolher = vi.fn();
    render(
      <CreditoTipoEscolhaModal open onClose={vi.fn()} onEscolher={onEscolher} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Cliente' }));
    expect(onEscolher).toHaveBeenCalledWith('CLIENTE');
  });

  it('drawer crédito disponível sem movimento mostra Editar, Excluir, Cancelar e Aplicar', () => {
    const acoes = getCreditoFinanceiroAcoes(creditoDisponivel);
    const ids = acoes.map((a) => a.id);
    expect(ids).toContain('aplicar');
    expect(ids).toContain('editar');
    expect(ids).toContain('excluir');
    expect(ids).toContain('cancelar');
  });

  it('drawer crédito com movimento não mostra Excluir', () => {
    const acoes = getCreditoFinanceiroAcoes({
      ...creditoDisponivel,
      possui_movimento: true,
      pode_excluir: false,
      pode_editar_completo: false,
      status: 'PARCIALMENTE_UTILIZADO',
      valor_utilizado: '100.00',
      possui_aplicacao: true,
      movimentos: [{ id: 9, estornada: false, pode_estornar: true, tipo_movimento: 'USO_CREDITO' }],
    });
    expect(acoes.some((a) => a.id === 'excluir')).toBe(false);
  });

  it('cancelar e excluir crédito abrem fluxo com motivo via drawer', async () => {
    getCredito.mockResolvedValue(creditoDisponivel);
    render(
      <CreditoDetalheDrawer
        creditoId={1}
        open
        onClose={vi.fn()}
        onUpdated={vi.fn()}
        onAplicar={vi.fn()}
      />,
    );
    await waitFor(() => expect(getCredito).toHaveBeenCalled());
    expect(await screen.findByRole('button', { name: FINANCEIRO_ACTION_LABELS.cancelarCredito })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: FINANCEIRO_ACTION_LABELS.excluirCredito })).toBeInTheDocument();
  });

  it('histórico formata valores em pt-BR', () => {
    const descricao = humanizarDescricaoFinanceira(
      'Crédito de cliente criado no valor de R$ 1500.00.',
      '1500.00',
    );
    expect(descricao).toContain('R$');
    expect(descricao).not.toContain('1500.00');
    const linhas = linhasDetalheHistoricoFinanceiro({
      descricao: 'Crédito aplicado.',
      valor: '1500.00',
      criado_em: '2026-06-02T16:08:00Z',
    });
    expect(linhas[0]).toMatch(/R\$\s*1\.500,00/);
    render(
      <FinanceiroEventoHistorico
        eventos={[
          {
            descricao: 'Crédito de cliente criado.',
            valor: '15000.00',
            criado_em: '2026-06-02T16:07:00Z',
            usuario_nome: 'admin',
          },
        ]}
      />,
    );
    expect(screen.getByText(/Valor: R\$\s*15\.000,00/)).toBeInTheDocument();
  });

  it('título manual sem movimento mostra Excluir título', () => {
    const acoes = getTituloFinanceiroAcoes(tituloManual, 'RECEBER');
    expect(acoes.some((a) => a.id === 'excluir')).toBe(true);
  });

  it('título com baixa não mostra Excluir título', () => {
    const acoes = getTituloFinanceiroAcoes(
      {
        ...tituloManual,
        valor_baixado: '100.00',
        valor_aberto: '400.00',
        pode_excluir: false,
        possui_baixa_ativa: true,
      },
      'RECEBER',
    );
    expect(acoes.some((a) => a.id === 'excluir')).toBe(false);
  });

  it('filtro ativo sem resultado usa helper de filtro', () => {
    expect(creditosTemFiltroAtivo({ search: '', tipo: '', status: '' })).toBe(false);
    expect(creditosTemFiltroAtivo({ search: 'abc', tipo: '', status: '' })).toBe(true);
  });

  it('drawer título manual exibe ação Excluir título quando permitido', async () => {
    getContaReceber.mockResolvedValue(tituloManual);
    render(
      <TituloFinanceiroDetalheDrawer
        tituloId={10}
        modo="RECEBER"
        open
        onClose={vi.fn()}
        onBaixar={vi.fn()}
        onUpdated={vi.fn()}
      />,
    );
    await waitFor(() => expect(getContaReceber).toHaveBeenCalled());
    expect(await screen.findByRole('button', { name: FINANCEIRO_ACTION_LABELS.excluirTitulo })).toBeInTheDocument();
  });
});
