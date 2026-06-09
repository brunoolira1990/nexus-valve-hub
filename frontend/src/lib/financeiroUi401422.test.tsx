import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { CreditoDetalheDrawer } from '@/components/financeiro/CreditoDetalheDrawer';
import { FinanceiroDrawerHistoricoSection } from '@/components/financeiro/FinanceiroDrawerHistoricoSection';
import { TituloFinanceiroDetalheDrawer } from '@/components/financeiro/TituloFinanceiroDetalheDrawer';
import {
  FINANCEIRO_ACTION_LABELS,
  agruparFinanceiroDrawerAcoes,
  creditoOperacionalDrawerTitulo,
  getCreditoFinanceiroAcoes,
  getTituloFinanceiroAcoes,
  tituloOperacionalDrawerTitulo,
} from '@/lib/financeiroUi';

const getCredito = vi.fn();
const getContaReceber = vi.fn();

vi.mock('@/services/api/financeiro', () => ({
  financeiroService: {
    getCredito: (...args: unknown[]) => getCredito(...args),
    getContaReceber: (...args: unknown[]) => getContaReceber(...args),
    getContaPagar: vi.fn(),
    cancelarCredito: vi.fn(),
    excluirCredito: vi.fn(),
    patchCredito: vi.fn(),
    estornarBaixa: vi.fn(),
    cancelarTitulo: vi.fn(),
    excluirTitulo: vi.fn(),
  },
}));

describe('financeiroUi 4.0.14.2.2 — exclusão após estorno', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('título manual sem movimento mostra Excluir título', () => {
    const acoes = getTituloFinanceiroAcoes(
      {
        status: 'EM_ABERTO',
        valor_aberto: '500.00',
        valor_baixado: '0.00',
        pode_excluir: true,
        pode_editar: true,
        pode_cancelar: true,
        pode_baixar: true,
        pode_aplicar_credito: true,
      },
      'RECEBER',
    );
    expect(acoes.some((a) => a.id === 'excluir')).toBe(true);
  });

  it('título com movimento ativo não mostra Excluir e expõe motivo', async () => {
    getContaReceber.mockResolvedValue({
      id: 10,
      tipo: 'RECEBER',
      numero: 'CR-001',
      cliente_nome: 'Cliente',
      valor_original: '500.00',
      valor_aberto: '400.00',
      valor_baixado: '100.00',
      status: 'PARCIALMENTE_RECEBIDO',
      origem_tipo: 'MANUAL',
      pode_excluir: false,
      motivo_bloqueio_exclusao:
        'Este título possui movimentações financeiras ativas. Estorne os movimentos antes de excluir.',
      possui_movimento_financeiro_ativo: true,
      data_emissao: '2026-06-01',
      data_vencimento: '2026-06-15',
    });
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
    expect(screen.queryByRole('button', { name: FINANCEIRO_ACTION_LABELS.excluirTitulo })).not.toBeInTheDocument();
    expect(
      await screen.findByText(/Exclusão indisponível: Este título possui movimentações financeiras ativas/i),
    ).toBeInTheDocument();
  });

  it('título com movimento estornado e saldo reaberto mostra Excluir título', () => {
    const acoes = getTituloFinanceiroAcoes(
      {
        status: 'EM_ABERTO',
        valor_aberto: '500.00',
        valor_baixado: '0.00',
        pode_excluir: true,
        possui_apenas_movimentos_estornados: true,
        possui_movimento_financeiro_ativo: false,
        pode_baixar: true,
      },
      'RECEBER',
    );
    expect(acoes.some((a) => a.id === 'excluir')).toBe(true);
  });

  it('crédito manual sem movimento mostra Excluir crédito', () => {
    const acoes = getCreditoFinanceiroAcoes({
      status: 'DISPONIVEL',
      pode_excluir: true,
      pode_aplicar: true,
      pode_editar: true,
      pode_editar_completo: true,
      pode_cancelar: true,
    });
    expect(acoes.some((a) => a.id === 'excluir')).toBe(true);
  });

  it('crédito com aplicação ativa não mostra Excluir e mostra motivo', async () => {
    getCredito.mockResolvedValue({
      id: 1,
      tipo: 'CLIENTE',
      status: 'PARCIALMENTE_UTILIZADO',
      contraparte_nome: 'Cliente Teste',
      valor_original: '500.00',
      valor_utilizado: '100.00',
      saldo: '400.00',
      motivo: 'Teste',
      data_credito: '2026-06-02',
      origem_tipo: 'MANUAL',
      pode_excluir: false,
      possui_movimento_ativo: true,
      motivo_bloqueio_exclusao:
        'Este crédito possui movimentações financeiras ativas. Estorne os movimentos antes de excluir.',
      eventos: [],
    });
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
    expect(screen.queryByRole('button', { name: FINANCEIRO_ACTION_LABELS.excluirCredito })).not.toBeInTheDocument();
    expect(await screen.findByText(/Exclusão indisponível:/i)).toBeInTheDocument();
  });

  it('crédito com aplicação estornada e saldo reaberto mostra Excluir crédito', async () => {
    getCredito.mockResolvedValue({
      id: 2,
      tipo: 'CLIENTE',
      status: 'DISPONIVEL',
      contraparte_nome: 'Cliente Teste',
      valor_original: '500.00',
      valor_utilizado: '0.00',
      saldo: '500.00',
      motivo: 'Teste',
      data_credito: '2026-06-02',
      origem_tipo: 'MANUAL',
      pode_excluir: true,
      possui_apenas_movimentos_estornados: true,
      possui_movimento_ativo: false,
      eventos: [{ id: 1, descricao: 'Uso estornado', criado_em: '2026-06-02T16:08:00Z' }],
    });
    render(
      <CreditoDetalheDrawer
        creditoId={2}
        open
        onClose={vi.fn()}
        onUpdated={vi.fn()}
        onAplicar={vi.fn()}
      />,
    );
    await waitFor(() => expect(getCredito).toHaveBeenCalled());
    expect(await screen.findByRole('button', { name: FINANCEIRO_ACTION_LABELS.excluirCredito })).toBeInTheDocument();
  });

  it('histórico começa recolhido por padrão', () => {
    render(
      <FinanceiroDrawerHistoricoSection
        eventos={[
          {
            id: 1,
            descricao: 'Crédito criado.',
            valor: '1500.00',
            criado_em: '2026-06-02T16:07:00Z',
            usuario_nome: 'admin',
          },
        ]}
      />,
    );
    expect(screen.getByText('Movimentos e histórico')).toBeInTheDocument();
    expect(screen.queryByText(/Valor: R\$/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: FINANCEIRO_ACTION_LABELS.verHistorico }));
    expect(screen.getByText(/Valor: R\$/)).toBeInTheDocument();
  });

  it('drawer de crédito mostra título operacional', () => {
    expect(
      creditoOperacionalDrawerTitulo({ tipo: 'CLIENTE', contraparte_nome: 'ACME Ltda' }),
    ).toBe('Crédito de cliente — ACME Ltda');
  });

  it('drawer de título mostra título operacional', () => {
    expect(
      tituloOperacionalDrawerTitulo({ numero: 'CR-001', cliente_nome: 'ACME Ltda' }, 'RECEBER'),
    ).toBe('Conta a receber — ACME Ltda');
  });

  it('agrupa ações em principal, secundárias e perigosas', () => {
    const acoes = [
      { id: 'aplicar', label: 'Aplicar', variant: 'primary' as const },
      { id: 'editar', label: 'Editar', variant: 'outline' as const },
      { id: 'excluir', label: 'Excluir', variant: 'destructive' as const },
    ];
    const grupos = agruparFinanceiroDrawerAcoes(acoes, vi.fn());
    expect(grupos.principal).toHaveLength(1);
    expect(grupos.secundarias).toHaveLength(1);
    expect(grupos.perigosas).toHaveLength(1);
  });
});
