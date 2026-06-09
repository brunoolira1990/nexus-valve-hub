import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FinanceiroCadastros from '@/pages/financeiro/FinanceiroCadastros';
import { Sidebar } from '@/components/Sidebar';
import {
  contaFinanceiraTipoBanco,
  labelBancoContaListagem,
  validarContaFinanceiraForm,
} from '@/lib/financeiroUi';
import { isSidebarPathActive } from '@/lib/sidebarNav';

vi.mock('@/hooks/useDashboardPermissoes', () => ({
  useDashboardPermissoes: () => ({ permissoes: [] }),
}));

const listContas = vi.fn();
const createConta = vi.fn();
const listCategorias = vi.fn();
const listCentrosCusto = vi.fn();

vi.mock('@/services/api/financeiro', () => ({
  financeiroService: {
    listContas: (...args: unknown[]) => listContas(...args),
    createConta: (...args: unknown[]) => createConta(...args),
    updateConta: vi.fn(),
    deleteConta: vi.fn(),
    listCategorias: (...args: unknown[]) => listCategorias(...args),
    listCentrosCusto: (...args: unknown[]) => listCentrosCusto(...args),
  },
}));

describe('financeiroUi 4.0.14.1.1 — conta tipo Banco', () => {
  it('listagem exibe banco quando tipo Banco tem banco preenchido', () => {
    expect(labelBancoContaListagem({ tipo: 'BANCO', banco: 'Itaú' })).toBe('Itaú');
  });

  it('listagem exibe Não informado para Banco sem banco', () => {
    expect(labelBancoContaListagem({ tipo: 'BANCO', banco: '' })).toBe('Não informado');
  });

  it('listagem exibe — para Caixa/Carteira sem banco', () => {
    expect(labelBancoContaListagem({ tipo: 'CAIXA' })).toBe('—');
    expect(labelBancoContaListagem({ tipo: 'CARTEIRA', banco: 'X' })).toBe('—');
  });

  it('validação exige banco para tipo Banco', () => {
    expect(
      validarContaFinanceiraForm({
        nome: 'Conta',
        tipo: 'BANCO',
        banco: '',
        agencia: '',
        conta: '',
        ativo: true,
        observacoes: '',
      }),
    ).toMatch(/banco/i);
    expect(contaFinanceiraTipoBanco('BANCO')).toBe(true);
    expect(contaFinanceiraTipoBanco('CAIXA')).toBe(false);
  });

  it('validação não exige banco para Caixa', () => {
    expect(
      validarContaFinanceiraForm({
        nome: 'Caixa loja',
        tipo: 'CAIXA',
        banco: '',
        agencia: '',
        conta: '',
        ativo: true,
        observacoes: '',
      }),
    ).toBeNull();
  });
});

describe('FinanceiroCadastros 4.0.14.1.1 — modal conta', () => {
  beforeEach(() => {
    listContas.mockResolvedValue({ results: [] });
    listCategorias.mockResolvedValue({ results: [] });
    listCentrosCusto.mockResolvedValue({ results: [] });
    createConta.mockResolvedValue({ id: 1 });
  });

  it('modal mostra campos bancários quando Tipo = Banco', async () => {
    render(
      <MemoryRouter>
        <FinanceiroCadastros />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listContas).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /nova conta/i }));
    fireEvent.change(screen.getByLabelText(/^tipo$/i), { target: { value: 'BANCO' } });
    expect(document.getElementById('conta-banco')).toBeInTheDocument();
    expect(document.getElementById('conta-agencia')).toBeInTheDocument();
    expect(document.getElementById('conta-conta')).toBeInTheDocument();
  });

  it('modal esconde campos bancários quando Tipo = Caixa', async () => {
    render(
      <MemoryRouter>
        <FinanceiroCadastros />
      </MemoryRouter>,
    );
    await waitFor(() => expect(listContas).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /nova conta/i }));
    fireEvent.change(screen.getByLabelText(/^tipo$/i), { target: { value: 'BANCO' } });
    fireEvent.change(screen.getByLabelText(/^tipo$/i), { target: { value: 'CAIXA' } });
    expect(document.getElementById('conta-banco')).not.toBeInTheDocument();
  });

  it('listagem exibe banco cadastrado para conta tipo Banco', async () => {
    listContas.mockResolvedValue({
      results: [{ id: 1, nome: 'Conta Itaú', tipo: 'BANCO', tipo_label: 'Banco', banco: 'Itaú', ativo: true }],
    });
    render(
      <MemoryRouter>
        <FinanceiroCadastros />
      </MemoryRouter>,
    );
    expect(await screen.findByText('Itaú')).toBeInTheDocument();
  });
});

describe('sidebarNav 4.0.14.1.1 — active state Financeiro', () => {
  it('rota /financeiro/cadastros ativa apenas Cadastros', () => {
    expect(isSidebarPathActive('/financeiro/cadastros', '/financeiro')).toBe(false);
    expect(isSidebarPathActive('/financeiro/cadastros', '/financeiro/cadastros')).toBe(true);
  });

  it('rota /financeiro ativa apenas Visão geral', () => {
    expect(isSidebarPathActive('/financeiro', '/financeiro')).toBe(true);
    expect(isSidebarPathActive('/financeiro', '/financeiro/cadastros')).toBe(false);
  });

  it('Sidebar destaca só Cadastros em /financeiro/cadastros', () => {
    render(
      <MemoryRouter initialEntries={['/financeiro/cadastros']}>
        <Sidebar isOpen onClose={vi.fn()} />
      </MemoryRouter>,
    );
    const visaoGeral = document.querySelector('a[href="/financeiro"]') as HTMLElement;
    const cadastros = document.querySelector('a[href="/financeiro/cadastros"]') as HTMLElement;
    expect(visaoGeral.className).not.toMatch(/bg-sidebar-active/);
    expect(cadastros.className).toMatch(/bg-sidebar-active/);
  });

  it('Sidebar destaca só Visão geral em /financeiro', () => {
    render(
      <MemoryRouter initialEntries={['/financeiro']}>
        <Sidebar isOpen onClose={vi.fn()} />
      </MemoryRouter>,
    );
    const visaoGeral = document.querySelector('a[href="/financeiro"]') as HTMLElement;
    const cadastros = document.querySelector('a[href="/financeiro/cadastros"]') as HTMLElement;
    expect(visaoGeral.className).toMatch(/bg-sidebar-active/);
    expect(cadastros.className).not.toMatch(/bg-sidebar-active/);
  });
});
