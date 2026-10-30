/**
 * Fornecedor na tela FormShell (Sprint 3.16): rail do Chatter + "Salvar" do cabeçalho
 * disparando o submit que pertence ao <form> de RHF.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import FornecedorFormPage from '@/pages/Fornecedores/FornecedorFormPage';

const createMock = vi.fn();
const getByIdMock = vi.fn();

vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: {
    create: (...args: unknown[]) => createMock(...args),
    update: vi.fn(),
    getById: (...args: unknown[]) => getByIdMock(...args),
  },
}));

vi.mock('@/services/api/transportadoras', () => ({
  transportadorasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/consulta', () => ({
  consultaCnpj: vi.fn(),
  consultaCep: vi.fn(),
}));

vi.mock('@/hooks/useConsultaIeSefaz', () => ({
  useConsultaIeSefaz: () => ({
    tryAutoConsultaIe: vi.fn(),
    loading: false,
    message: null,
    error: null,
  }),
}));

const CNPJ_OK = '04.252.011/0001-10';

/** Agora existem dois botões "Salvar" na tela: o do cabeçalho e o do rodapé mobile. */
function salvarDoCabecalho() {
  return within(screen.getByTestId('form-shell-header')).getByRole('button', { name: 'Salvar' });
}

async function preencherFornecedor() {
  await screen.findByLabelText(/Razão Social/i);
  fireEvent.change(screen.getByLabelText(/Razão Social/i), { target: { value: 'Fornecedor Rail LTDA' } });
  fireEvent.change(screen.getByLabelText(/^CNPJ/i), { target: { value: CNPJ_OK } });
}

function renderComRota(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/fornecedores/novo" element={<FornecedorFormPage />} />
        <Route path="/fornecedores/:id/edit" element={<FornecedorFormPage />} />
        <Route path="/fornecedores" element={<div>Lista de fornecedores</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('FornecedorFormPage — FormShell + rail do Chatter', () => {
  beforeEach(() => {
    createMock.mockReset();
    getByIdMock.mockReset();
    createMock.mockResolvedValue({ id: 1 });
  });

  it('novo fornecedor: rail do Chatter, Badge "Ativo" e sem histórico ainda', async () => {
    renderComRota('/fornecedores/novo');

    const rail = await screen.findByTestId('form-shell-rail');
    expect(rail).toHaveTextContent('Chatter');
    expect(screen.getByText('Ativo')).toBeInTheDocument();
    expect(screen.getByText(/Salve o registro primeiro/i)).toBeInTheDocument();
  });

  it('inativo: o Badge do cabeçalho reflete o cadastro carregado', async () => {
    getByIdMock.mockResolvedValue({
      id: 9,
      razao_social: 'Fornecedor Inativo LTDA',
      cnpj: '04252011000110',
      ativo: false,
    });
    renderComRota('/fornecedores/9/edit');

    const header = await screen.findByTestId('form-shell-header');
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
    expect(header).toHaveTextContent('Inativo');
  });

  it('o "Salvar" do cabeçalho cria o fornecedor e abre o registro novo (chatter com id)', async () => {
    getByIdMock.mockResolvedValue({ id: 1, razao_social: 'Fornecedor Rail LTDA', cnpj: '04252011000110', ativo: true });
    renderComRota('/fornecedores/novo');

    await preencherFornecedor();

    fireEvent.click(salvarDoCabecalho());

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
  });

  it('o "Salvar" do rodapé mobile submete o mesmo formulário', async () => {
    getByIdMock.mockResolvedValue({ id: 1, razao_social: 'Fornecedor Rail LTDA', cnpj: '04252011000110', ativo: true });
    renderComRota('/fornecedores/novo');

    await preencherFornecedor();

    fireEvent.click(await screen.findByTestId('form-shell-acao-principal-mobile'));

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
  });
});
