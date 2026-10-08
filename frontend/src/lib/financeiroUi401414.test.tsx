import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TituloFinanceiroNovoModal } from '@/components/financeiro/TituloFinanceiroNovoModal';
import { ClienteSearchSelect } from '@/components/financeiro/ClienteSearchSelect';
import {
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_CLIENTE_MESSAGES,
  PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO,
  tituloModoConfig,
  validarContaReceberForm,
} from '@/lib/financeiroUi';
import { clientesService } from '@/services/api/clientes';

vi.mock('@/services/api/clientes', () => ({
  clientesService: {
    search: vi.fn(),
    getAll: vi.fn(),
  },
}));

const createContaReceber = vi.fn();
const listCategorias = vi.fn();
const listCentrosCusto = vi.fn();
const listContasAtivas = vi.fn();
const listFormasAtivas = vi.fn();

vi.mock('@/services/api/financeiro', () => ({
  financeiroService: {
    createContaReceber: (...args: unknown[]) => createContaReceber(...args),
    listCategorias: (...args: unknown[]) => listCategorias(...args),
    listCentrosCusto: (...args: unknown[]) => listCentrosCusto(...args),
    listContasAtivas: (...args: unknown[]) => listContasAtivas(...args),
    listFormasAtivas: (...args: unknown[]) => listFormasAtivas(...args),
  },
}));

const clienteMock = {
  id: 7,
  razao_social: 'PETROBRAS TRANSPORTE S.A - TRANSPETRO',
  nome_fantasia: 'Transpetro',
  cnpj: '02709449006866',
  ie: '',
  logradouro: '',
  numero: '',
  complemento: '',
  bairro: '',
  cidade: '',
  uf: '',
  cep: '',
  telefone: '',
  email: '',
  contato_responsavel: '',
  observacoes: '',
  condicao_pagamento_texto: '',
  dias_parcelas: [],
  quantidade_parcelas: 0,
  ativo: true,
} as const;

describe('financeiroUi 4.0.14.1.4 — nomenclatura CR', () => {
  it('botão e modal usam Nova conta a receber', () => {
    expect(FINANCEIRO_ACTION_LABELS.novaContaReceber).toBe('Nova conta a receber');
    expect(tituloModoConfig('RECEBER').novoLabel).toBe('Nova conta a receber');
    expect(FINANCEIRO_ACTION_LABELS.baixarRecebimento).toBe('Baixar recebimento');
  });

  it('validação exige cliente e valor', () => {
    expect(validarContaReceberForm(null, { data_emissao: '2026-06-02', data_vencimento: '2026-06-10', valor_original: '100' })).toBe(
      FINANCEIRO_CLIENTE_MESSAGES.selecioneCliente,
    );
    expect(validarContaReceberForm(1, { data_emissao: '2026-06-02', data_vencimento: '', valor_original: '100' })).toBe(
      FINANCEIRO_CLIENTE_MESSAGES.informeVencimento,
    );
    expect(validarContaReceberForm(1, { data_emissao: '2026-06-02', data_vencimento: '2026-06-10', valor_original: '0' })).toBe(
      FINANCEIRO_CLIENTE_MESSAGES.informeValorMaiorZero,
    );
  });
});

describe('ClienteSearchSelect', () => {
  beforeEach(() => {
    vi.mocked(clientesService.search).mockResolvedValue([clienteMock as never]);
  });

  it('exibe placeholder operacional', () => {
    render(
      <MemoryRouter>
        <ClienteSearchSelect valueId={null} selectedCliente={null} onSelect={vi.fn()} onClear={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText(PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO)).toBeInTheDocument();
  });

  it('busca por nome e CNPJ com máscara', async () => {
    render(
      <MemoryRouter>
        <ClienteSearchSelect valueId={null} selectedCliente={null} onSelect={vi.fn()} onClear={vi.fn()} />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Transpetro' } });
    await waitFor(() => expect(clientesService.search).toHaveBeenCalledWith('Transpetro', 25));
    fireEvent.change(input, { target: { value: '02.709.449/0068-66' } });
    await waitFor(() => expect(clientesService.search).toHaveBeenCalledWith('02.709.449/0068-66', 25));
  });

  it('mensagem quando não encontra cliente', async () => {
    vi.mocked(clientesService.search).mockResolvedValue([]);
    render(
      <MemoryRouter>
        <ClienteSearchSelect valueId={null} selectedCliente={null} onSelect={vi.fn()} onClear={vi.fn()} />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Inexistente' } });
    expect(await screen.findByText('Nenhum cliente encontrado.')).toBeInTheDocument();
  });
});

describe('TituloFinanceiroNovoModal — conta a receber', () => {
  beforeEach(() => {
    listCategorias.mockResolvedValue({ results: [] });
    listCentrosCusto.mockResolvedValue({ results: [] });
    listContasAtivas.mockResolvedValue([]);
    listFormasAtivas.mockResolvedValue([]);
    createContaReceber.mockClear();
    createContaReceber.mockResolvedValue({ id: 1 });
    vi.mocked(clientesService.search).mockResolvedValue([clienteMock as never]);
    vi.mocked(clientesService.getAll).mockClear();
  });

  it('modal abre com título Nova conta a receber', () => {
    render(
      <MemoryRouter>
        <TituloFinanceiroNovoModal open onClose={vi.fn()} modo="RECEBER" onCreated={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Nova conta a receber' })).toBeInTheDocument();
  });

  it('não usa select simples de cliente', () => {
    render(
      <MemoryRouter>
        <TituloFinanceiroNovoModal open onClose={vi.fn()} modo="RECEBER" onCreated={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText(PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO)).toBeInTheDocument();
    expect(screen.queryByText('Selecione…')).not.toBeInTheDocument();
    expect(clientesService.getAll).not.toHaveBeenCalled();
    const clienteField = screen.getByText(/^Cliente$/).closest('div');
    expect(clienteField?.querySelector('select')).toBeNull();
  });

  it('exige cliente ao salvar', async () => {
    render(
      <MemoryRouter>
        <TituloFinanceiroNovoModal open onClose={vi.fn()} modo="RECEBER" onCreated={vi.fn()} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(await screen.findByText(FINANCEIRO_CLIENTE_MESSAGES.selecioneCliente)).toBeInTheDocument();
    expect(createContaReceber).not.toHaveBeenCalled();
  });

  it('grava id do cliente selecionado', async () => {
    render(
      <MemoryRouter>
        <TituloFinanceiroNovoModal open onClose={vi.fn()} modo="RECEBER" onCreated={vi.fn()} />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'PETROBRAS' } });
    fireEvent.click(await screen.findByText('PETROBRAS TRANSPORTE S.A - TRANSPETRO'));
    fireEvent.change(screen.getByLabelText(/^valor$/i), { target: { value: '5000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(createContaReceber).toHaveBeenCalled());
    expect(createContaReceber.mock.calls.at(-1)?.[0].cliente).toBe(7);
  });

  it('mostra Parcelar este título', () => {
    render(
      <MemoryRouter>
        <TituloFinanceiroNovoModal open onClose={vi.fn()} modo="RECEBER" onCreated={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText(FINANCEIRO_ACTION_LABELS.parcelarTitulo)).toBeInTheDocument();
    expect(screen.queryByText('Gerar parcelas automaticamente')).not.toBeInTheDocument();
  });
});
