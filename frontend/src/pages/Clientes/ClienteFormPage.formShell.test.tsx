/**
 * Cliente na tela FormShell (Sprint 3.16): o rail do Chatter e o "Salvar" do cabeçalho
 * — que não está dentro do <form> — precisam disparar o submit do RHF.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import ClienteFormPage from '@/pages/Clientes/ClienteFormPage';

const createMock = vi.fn();
const getByIdMock = vi.fn();
const getAllTransportadoras = vi.fn().mockResolvedValue([]);

vi.mock('@/services/api/clientes', () => ({
  clientesService: {
    create: (...args: unknown[]) => createMock(...args),
    update: vi.fn(),
    getById: (...args: unknown[]) => getByIdMock(...args),
    search: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('@/services/api/transportadoras', () => ({
  transportadorasService: {
    getAll: () => getAllTransportadoras(),
  },
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
const CNPJ_DIGITS = '04252011000110';

/** Agora existem dois botões "Salvar" na tela: o do cabeçalho e o do rodapé mobile. */
function salvarDoCabecalho() {
  return within(screen.getByTestId('form-shell-header')).getByRole('button', { name: 'Salvar' });
}

async function preencherCliente() {
  await screen.findByLabelText(/Razão Social/i);
  fireEvent.change(screen.getByLabelText(/Razão Social/i), { target: { value: 'Cliente Rail LTDA' } });
  fireEvent.change(screen.getByLabelText(/^CNPJ/i), { target: { value: CNPJ_OK } });
}

function renderComRota(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/clientes/novo" element={<ClienteFormPage />} />
        <Route path="/clientes/:id/edit" element={<ClienteFormPage />} />
        <Route path="/clientes" element={<div>Lista de clientes</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ClienteFormPage — FormShell + rail do Chatter', () => {
  beforeEach(() => {
    createMock.mockReset();
    getByIdMock.mockReset();
    createMock.mockResolvedValue({ id: 1 });
  });

  it('novo cliente: rail do Chatter no cabeçalho, Badge de estado e sem histórico ainda', async () => {
    renderComRota('/clientes/novo');

    const rail = await screen.findByTestId('form-shell-rail');
    expect(rail).toHaveTextContent('Chatter');
    expect(screen.getByText('Ativo')).toBeInTheDocument();
    expect(screen.getByText(/Salve o registro primeiro/i)).toBeInTheDocument();
  });

  it('edição: com id gravado o rail deixa de pedir o salvamento primeiro', async () => {
    getByIdMock.mockResolvedValue({
      id: 42,
      razao_social: 'Cliente Rail LTDA',
      cnpj: CNPJ_DIGITS,
      ativo: true,
      bloqueado: false,
    });
    renderComRota('/clientes/42/edit');

    await screen.findByTestId('form-shell-rail');
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
    expect(screen.queryByText(/Salve o registro primeiro/i)).not.toBeInTheDocument();
  });

  it('o "Salvar" do cabeçalho cria o cliente e abre o registro novo (chatter com id)', async () => {
    getByIdMock.mockResolvedValue({
      id: 1,
      razao_social: 'Cliente Rail LTDA',
      cnpj: CNPJ_DIGITS,
      ativo: true,
      bloqueado: false,
    });
    renderComRota('/clientes/novo');

    await preencherCliente();

    fireEvent.click(salvarDoCabecalho());

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(createMock.mock.calls[0][0]).toMatchObject({
      razao_social: 'CLIENTE RAIL LTDA',
      cnpj: CNPJ_DIGITS,
    });
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
  });

  it('o "Salvar" do rodapé mobile submete o mesmo formulário', async () => {
    getByIdMock.mockResolvedValue({
      id: 1,
      razao_social: 'Cliente Rail LTDA',
      cnpj: CNPJ_DIGITS,
      ativo: true,
      bloqueado: false,
    });
    renderComRota('/clientes/novo');

    await preencherCliente();

    fireEvent.click(await screen.findByTestId('form-shell-acao-principal-mobile'));

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
  });
});
