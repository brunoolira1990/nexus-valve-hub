import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CreditosPage } from '@/pages/financeiro/Creditos';
import { CreditoNovoModal } from '@/components/financeiro/CreditoNovoModal';
import { AplicarCreditoModal } from '@/components/financeiro/AplicarCreditoModal';
import { AbaterDevolucaoModal } from '@/components/financeiro/AbaterDevolucaoModal';
import { TituloFinanceiroDetalheDrawer } from '@/components/financeiro/TituloFinanceiroDetalheDrawer';
import {
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_CREDITO_MESSAGES,
  labelEstornoMovimentoFinanceiro,
  validarAbatimentoForm,
  validarAplicarCreditoForm,
  validarCreditoForm,
} from '@/lib/financeiroUi';

vi.mock('@/services/api/clientes', () => ({
  clientesService: { search: vi.fn().mockResolvedValue([]), getAll: vi.fn() },
}));
vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: { search: vi.fn().mockResolvedValue([]), getAll: vi.fn() },
}));

const listCreditos = vi.fn();
const createCredito = vi.fn();
const getContaReceber = vi.fn();
const getContaPagar = vi.fn();
const aplicarCredito = vi.fn();
const abaterDevolucaoReceber = vi.fn();

vi.mock('@/services/api/financeiro', () => ({
  financeiroService: {
    listCreditos: (...args: unknown[]) => listCreditos(...args),
    createCredito: (...args: unknown[]) => createCredito(...args),
    getContaReceber: (...args: unknown[]) => getContaReceber(...args),
    getContaPagar: (...args: unknown[]) => getContaPagar(...args),
    aplicarCredito: (...args: unknown[]) => aplicarCredito(...args),
    abaterDevolucaoReceber: (...args: unknown[]) => abaterDevolucaoReceber(...args),
    abaterDevolucaoPagar: vi.fn(),
    cancelarTitulo: vi.fn(),
    estornarBaixa: vi.fn(),
  },
}));

const tituloAberto = {
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
};

describe('financeiroUi 4.0.14.2 — créditos e abatimentos', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listCreditos.mockResolvedValue({
      count: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
      results: [
        {
          id: 1,
          tipo: 'CLIENTE',
          tipo_label: 'Cliente',
          contraparte_nome: 'Cliente Teste',
          valor_original: '500.00',
          valor_utilizado: '0.00',
          saldo: '500.00',
          status: 'DISPONIVEL',
          status_label: 'Disponível',
          origem_tipo: 'MANUAL',
          origem_tipo_label: 'Manual',
          origem_numero: '',
          data_credito: '2026-06-01',
          motivo: 'Ajuste',
        },
      ],
    });
    getContaReceber.mockResolvedValue({ ...tituloAberto, baixas: [], eventos: [], parcelas: [] });
    getContaPagar.mockResolvedValue({ ...tituloAberto, tipo: 'PAGAR', baixas: [], eventos: [], parcelas: [] });
  });

  it('tela Créditos lista créditos', async () => {
    render(
      <MemoryRouter>
        <CreditosPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listCreditos).toHaveBeenCalled());
    expect(await screen.findByText('Cliente Teste')).toBeInTheDocument();
    expect(screen.getByText('Créditos')).toBeInTheDocument();
  });

  it('novo crédito de cliente abre modal correto', () => {
    render(
      <MemoryRouter>
        <CreditoNovoModal open tipo="CLIENTE" onClose={() => {}} onCreated={() => {}} />
      </MemoryRouter>,
    );
    expect(screen.getByText(FINANCEIRO_ACTION_LABELS.novoCreditoCliente)).toBeInTheDocument();
  });

  it('novo crédito de fornecedor abre modal correto', () => {
    render(
      <MemoryRouter>
        <CreditoNovoModal open tipo="FORNECEDOR" onClose={() => {}} onCreated={() => {}} />
      </MemoryRouter>,
    );
    expect(screen.getByText(FINANCEIRO_ACTION_LABELS.novoCreditoFornecedor)).toBeInTheDocument();
  });

  it('validação aplicar crédito exige crédito selecionado', () => {
    expect(validarAplicarCreditoForm(null, '100', '500', '500')).toBe(
      FINANCEIRO_CREDITO_MESSAGES.selecioneCredito,
    );
  });

  it('validação aplicar crédito bloqueia valor maior que saldo', () => {
    expect(validarAplicarCreditoForm(1, '600', '500', '500')).toContain('excede');
  });

  it('abatimento exige motivo', () => {
    expect(validarAbatimentoForm('100', '', '500')).toBe(FINANCEIRO_CREDITO_MESSAGES.informeMotivo);
  });

  it('drawer abre modal aplicar crédito via callback', async () => {
    const onAplicar = vi.fn();
    render(
      <TituloFinanceiroDetalheDrawer
        tituloId={10}
        modo="RECEBER"
        open
        onClose={() => {}}
        onBaixar={() => {}}
        onUpdated={() => {}}
        onAplicarCredito={onAplicar}
        onAbaterDevolucao={() => {}}
      />,
    );
    await waitFor(() => expect(getContaReceber).toHaveBeenCalled());
    fireEvent.click(await screen.findByRole('button', { name: FINANCEIRO_ACTION_LABELS.aplicarCredito }));
    expect(onAplicar).toHaveBeenCalled();
  });

  it('drawer abre modal abater via callback', async () => {
    const onAbater = vi.fn();
    render(
      <TituloFinanceiroDetalheDrawer
        tituloId={10}
        modo="RECEBER"
        open
        onClose={() => {}}
        onBaixar={() => {}}
        onUpdated={() => {}}
        onAplicarCredito={() => {}}
        onAbaterDevolucao={onAbater}
      />,
    );
    await waitFor(() => expect(getContaReceber).toHaveBeenCalled());
    fireEvent.click(await screen.findByRole('button', { name: FINANCEIRO_ACTION_LABELS.abaterDevolucao }));
    expect(onAbater).toHaveBeenCalled();
  });

  it('movimentos exibem label de estorno para uso de crédito', () => {
    expect(labelEstornoMovimentoFinanceiro('USO_CREDITO')).toBe(FINANCEIRO_ACTION_LABELS.estornarUsoCredito);
    expect(labelEstornoMovimentoFinanceiro('ABATIMENTO_DEVOLUCAO')).toBe(
      FINANCEIRO_ACTION_LABELS.estornarAbatimento,
    );
  });

  it('modal abater por devolução renderiza campos', () => {
    render(
      <AbaterDevolucaoModal
        open
        onClose={() => {}}
        modo="RECEBER"
        titulo={tituloAberto}
        onSuccess={() => {}}
      />,
    );
    expect(screen.getByText(FINANCEIRO_ACTION_LABELS.abaterDevolucao)).toBeInTheDocument();
    expect(screen.getByText('Motivo')).toBeInTheDocument();
  });

  it('modal aplicar crédito renderiza seleção de crédito', async () => {
    listCreditos.mockResolvedValueOnce({
      count: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
      results: [{ id: 3, saldo: '200.00', motivo: 'Crédito A', pode_aplicar: true }],
    });
    render(
      <AplicarCreditoModal
        open
        onClose={() => {}}
        modo="RECEBER"
        titulo={tituloAberto}
        onSuccess={() => {}}
      />,
    );
    await waitFor(() => expect(getContaReceber).toHaveBeenCalled());
    expect(await screen.findByText('Crédito disponível')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aplicar crédito' })).toBeInTheDocument();
  });

  it('validação crédito exige cliente', () => {
    expect(
      validarCreditoForm(
        null,
        { valor_original: '100', data_credito: '2026-06-01', origem_tipo: 'MANUAL', origem_numero: '', motivo: 'x', observacoes: '' },
        'CLIENTE',
      ),
    ).toBeTruthy();
  });

  it('mensagens amigáveis de sucesso existem', () => {
    expect(FINANCEIRO_CREDITO_MESSAGES.creditoClienteSucesso).toContain('cliente');
    expect(FINANCEIRO_CREDITO_MESSAGES.estornoUsoCreditoSucesso).toContain('crédito');
  });
});
