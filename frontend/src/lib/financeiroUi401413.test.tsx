import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ContaPagarDespesaModal } from '@/components/financeiro/ContaPagarDespesaModal';
import { FornecedorSearchSelect } from '@/components/financeiro/FornecedorSearchSelect';
import {
  FINANCEIRO_FORNECEDOR_MESSAGES,
  PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO,
} from '@/lib/financeiroUi';
import { fornecedoresService } from '@/services/api/fornecedores';

vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: {
    search: vi.fn(),
    getAll: vi.fn(),
  },
}));

const createContaPagar = vi.fn();
const listCategorias = vi.fn();
const listContasAtivas = vi.fn();
const listFormasAtivas = vi.fn();

vi.mock('@/services/api/financeiro', () => ({
  financeiroService: {
    createContaPagar: (...args: unknown[]) => createContaPagar(...args),
    listCategorias: (...args: unknown[]) => listCategorias(...args),
    listContasAtivas: (...args: unknown[]) => listContasAtivas(...args),
    listFormasAtivas: (...args: unknown[]) => listFormasAtivas(...args),
  },
}));

const fornecedorMock = {
  id: 42,
  razao_social: 'WINNER EXPRESS TRANSPORTES LTDA',
  nome_fantasia: 'Winner Express',
  cnpj: '32241095000121',
  ie: '',
  logradouro: '',
  numero: '',
  complemento: '',
  bairro: '',
  cidade: 'São Paulo',
  uf: 'SP',
  cep: '',
  telefone: '',
  email: '',
  contato_responsavel: '',
  observacoes: '',
  inscricao_municipal: '',
  suframa: '',
  email_nf: '',
  telefone_alternativo: '',
  celular: '',
  condicao_pagamento_texto: '',
  dias_parcelas: [],
  quantidade_parcelas: 0,
  transportadora_padrao_id: null,
  prazo_entrega: 0,
  ativo: true,
  ddd: '',
  banco: '',
  agencia: '',
  conta: '',
  tipo_conta: '',
  cnae: '',
  regime_tributario: '',
  integracao_texto: '',
};

describe('FornecedorSearchSelect', () => {
  beforeEach(() => {
    vi.mocked(fornecedoresService.search).mockResolvedValue([fornecedorMock]);
  });

  it('exibe placeholder operacional de busca', () => {
    render(
      <MemoryRouter>
        <FornecedorSearchSelect
          valueId={null}
          selectedFornecedor={null}
          onSelect={vi.fn()}
          onClear={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText(PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO)).toBeInTheDocument();
  });

  it('busca fornecedor por nome e seleciona', async () => {
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <FornecedorSearchSelect
          valueId={null}
          selectedFornecedor={null}
          onSelect={onSelect}
          onClear={vi.fn()}
        />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Winner' } });
    await waitFor(() => expect(fornecedoresService.search).toHaveBeenCalledWith('Winner', 25));
    const option = await screen.findByText('WINNER EXPRESS TRANSPORTES LTDA');
    fireEvent.click(option);
    expect(onSelect).toHaveBeenCalledWith(fornecedorMock);
  });

  it('busca fornecedor por CNPJ', async () => {
    render(
      <MemoryRouter>
        <FornecedorSearchSelect
          valueId={null}
          selectedFornecedor={null}
          onSelect={vi.fn()}
          onClear={vi.fn()}
        />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: '32.241.095/0001-21' } });
    await waitFor(() =>
      expect(fornecedoresService.search).toHaveBeenCalledWith('32.241.095/0001-21', 25),
    );
  });

  it('exibe mensagem quando não encontra fornecedor', async () => {
    vi.mocked(fornecedoresService.search).mockResolvedValue([]);
    render(
      <MemoryRouter>
        <FornecedorSearchSelect
          valueId={null}
          selectedFornecedor={null}
          onSelect={vi.fn()}
          onClear={vi.fn()}
        />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Inexistente XYZ' } });
    expect(await screen.findByText('Nenhum fornecedor encontrado.')).toBeInTheDocument();
  });

  it('permite limpar fornecedor selecionado', () => {
    const onClear = vi.fn();
    render(
      <MemoryRouter>
        <FornecedorSearchSelect
          valueId={42}
          selectedFornecedor={fornecedorMock}
          onSelect={vi.fn()}
          onClear={onClear}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Limpar' }));
    expect(onClear).toHaveBeenCalled();
  });
});

describe('ContaPagarDespesaModal — busca fornecedor', () => {
  beforeEach(() => {
    listCategorias.mockResolvedValue({ results: [] });
    listContasAtivas.mockResolvedValue([]);
    listFormasAtivas.mockResolvedValue([]);
    createContaPagar.mockClear();
    createContaPagar.mockResolvedValue({ id: 1 });
    vi.mocked(fornecedoresService.search).mockResolvedValue([fornecedorMock]);
    vi.mocked(fornecedoresService.getAll).mockClear();
  });

  it('Nova conta a pagar não usa select simples de fornecedor', () => {
    render(
      <MemoryRouter>
        <ContaPagarDespesaModal
          open
          onClose={vi.fn()}
          onCreated={vi.fn()}
          tipoLancamento="FORNECEDOR"
          tituloModal="Nova conta a pagar"
        />
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText(PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO)).toBeInTheDocument();
    expect(fornecedoresService.getAll).not.toHaveBeenCalled();
    const fornecedorField = screen.getByText(/^Fornecedor$/).closest('.sm\\:col-span-2');
    expect(fornecedorField?.querySelector('select')).toBeNull();
  });

  it('exige fornecedor na nova conta a pagar', async () => {
    render(
      <MemoryRouter>
        <ContaPagarDespesaModal
          open
          onClose={vi.fn()}
          onCreated={vi.fn()}
          tipoLancamento="FORNECEDOR"
          tituloModal="Nova conta a pagar"
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(await screen.findByText(FINANCEIRO_FORNECEDOR_MESSAGES.selecioneFornecedor)).toBeInTheDocument();
    expect(createContaPagar).not.toHaveBeenCalled();
  });

  it('grava id do fornecedor selecionado no payload', async () => {
    render(
      <MemoryRouter>
        <ContaPagarDespesaModal
          open
          onClose={vi.fn()}
          onCreated={vi.fn()}
          tipoLancamento="FORNECEDOR"
          tituloModal="Nova conta a pagar"
        />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Winner' } });
    fireEvent.click(await screen.findByText('WINNER EXPRESS TRANSPORTES LTDA'));
    fireEvent.change(screen.getByLabelText(/^descrição$/i), { target: { value: 'Serviço transporte' } });
    fireEvent.change(screen.getByLabelText(/^valor$/i), { target: { value: '1500' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(createContaPagar).toHaveBeenCalled());
    expect(createContaPagar.mock.calls.at(-1)?.[0].fornecedor).toBe(42);
  });

  it('Nova despesa permite fornecedor vazio', async () => {
    render(
      <MemoryRouter>
        <ContaPagarDespesaModal
          open
          onClose={vi.fn()}
          onCreated={vi.fn()}
          tipoLancamento="DESPESA_OPERACIONAL"
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(FINANCEIRO_FORNECEDOR_MESSAGES.despesaFornecedorOpcional)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/^descrição$/i), { target: { value: 'Aluguel' } });
    fireEvent.change(screen.getByLabelText(/^valor$/i), { target: { value: '2000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(createContaPagar).toHaveBeenCalled());
    expect(createContaPagar.mock.calls.at(-1)?.[0].fornecedor).toBeNull();
  });
});
