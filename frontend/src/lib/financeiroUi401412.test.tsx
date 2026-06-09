import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FinanceiroCadastros from '@/pages/financeiro/FinanceiroCadastros';
import {
  labelNomeContaFinanceira,
  PLACEHOLDER_BANCO_CONTA_FINANCEIRA,
  placeholderNomeContaFinanceira,
  validarContaFinanceiraForm,
} from '@/lib/financeiroUi';

vi.mock('@/hooks/useDashboardPermissoes', () => ({
  useDashboardPermissoes: () => ({ permissoes: [] }),
}));

const listContas = vi.fn();
const listCategorias = vi.fn();
const listCentrosCusto = vi.fn();

vi.mock('@/services/api/financeiro', () => ({
  financeiroService: {
    listContas: (...args: unknown[]) => listContas(...args),
    createConta: vi.fn(),
    updateConta: vi.fn(),
    deleteConta: vi.fn(),
    listCategorias: (...args: unknown[]) => listCategorias(...args),
    listCentrosCusto: (...args: unknown[]) => listCentrosCusto(...args),
  },
}));

describe('financeiroUi 4.0.14.1.2 — labels conta tipo Banco', () => {
  it('label nome para Banco é Descrição / Apelido da conta', () => {
    expect(labelNomeContaFinanceira('BANCO')).toBe('Descrição / Apelido da conta');
  });

  it('label nome para Caixa é Nome da conta/caixa', () => {
    expect(labelNomeContaFinanceira('CAIXA')).toBe('Nome da conta/caixa');
  });

  it('placeholder banco sugere instituições bancárias', () => {
    expect(PLACEHOLDER_BANCO_CONTA_FINANCEIRA).toMatch(/Itaú/);
    expect(PLACEHOLDER_BANCO_CONTA_FINANCEIRA).toMatch(/Bradesco/);
  });

  it('placeholder apelido para Banco sugere descrição operacional', () => {
    expect(placeholderNomeContaFinanceira('BANCO')).toMatch(/Conta principal/);
  });

  it('placeholder nome para Caixa sugere caixa/carteira', () => {
    expect(placeholderNomeContaFinanceira('CAIXA')).toMatch(/Caixa interno/);
  });

  it('validação Banco obrigatório continua para tipo Banco', () => {
    expect(
      validarContaFinanceiraForm({
        nome: 'Conta principal',
        tipo: 'BANCO',
        banco: '',
        agencia: '',
        conta: '',
        ativo: true,
        observacoes: '',
      }),
    ).toMatch(/banco/i);
  });

  it('validação nome vazio para Banco pede descrição amigável', () => {
    expect(
      validarContaFinanceiraForm({
        nome: '',
        tipo: 'BANCO',
        banco: 'Itaú',
        agencia: '',
        conta: '',
        ativo: true,
        observacoes: '',
      }),
    ).toBe('Informe uma descrição para identificar esta conta.');
  });
});

describe('FinanceiroCadastros 4.0.14.1.2 — modal labels', () => {
  beforeEach(() => {
    listContas.mockResolvedValue({ results: [] });
    listCategorias.mockResolvedValue({ results: [] });
    listCentrosCusto.mockResolvedValue({ results: [] });
  });

  it('Tipo Banco mostra Descrição / Apelido e placeholder de instituição', async () => {
    render(
      <MemoryRouter>
        <FinanceiroCadastros />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listContas).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /nova conta/i }));
    fireEvent.change(screen.getByLabelText(/^tipo$/i), { target: { value: 'BANCO' } });

    expect(screen.getByLabelText(/descrição \/ apelido da conta/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/conta principal, conta movimento/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/itaú, bradesco, banco do brasil/i)).toBeInTheDocument();
  });

  it('Tipo Caixa mostra Nome da conta/caixa e oculta campos bancários', async () => {
    render(
      <MemoryRouter>
        <FinanceiroCadastros />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listContas).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /nova conta/i }));

    expect(screen.getByLabelText(/nome da conta\/caixa/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/caixa interno, carteira pix/i)).toBeInTheDocument();
    expect(document.getElementById('conta-banco')).not.toBeInTheDocument();
  });

  it('listagem separa apelido e instituição bancária', async () => {
    listContas.mockResolvedValue({
      results: [
        {
          id: 1,
          nome: 'Conta principal',
          tipo: 'BANCO',
          tipo_label: 'Banco',
          banco: 'Itaú',
          ativo: true,
        },
      ],
    });
    render(
      <MemoryRouter>
        <FinanceiroCadastros />
      </MemoryRouter>,
    );
    expect(await screen.findByText('Conta principal')).toBeInTheDocument();
    expect(screen.getByText('Itaú')).toBeInTheDocument();
  });
});
