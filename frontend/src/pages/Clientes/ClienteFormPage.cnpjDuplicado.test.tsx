/**
 * Cadastro de cliente — mensagem amigável em CNPJ duplicado (HTTP 400).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ClienteFormPage from '@/pages/Clientes/ClienteFormPage';
import {
  MSG_CNPJ_CLIENTE_DUPLICADO,
  MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM,
} from '@/lib/clienteCadastroErros';
import { PERMISSION_DENIED_MESSAGE, SESSION_EXPIRED_MESSAGE } from '@/services/api/config';

const createMock = vi.fn();
const searchMock = vi.fn();
const getAllTransportadoras = vi.fn().mockResolvedValue([]);

vi.mock('@/services/api/clientes', () => ({
  clientesService: {
    create: (...args: unknown[]) => createMock(...args),
    update: vi.fn(),
    getById: vi.fn(),
    search: (...args: unknown[]) => searchMock(...args),
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

function axiosLike(status: number, data: unknown) {
  const err = new Error(`Request failed with status code ${status}`) as Error & {
    response?: { status: number; data: unknown };
  };
  err.response = { status, data };
  return err;
}

/** CNPJ válido (dígitos verificadores corretos) para passar no zod do formulário. */
const CNPJ_OK = '04.252.011/0001-10';
const CNPJ_DIGITS = '04252011000110';

async function preencherESalvar() {
  render(
    <MemoryRouter initialEntries={['/clientes/novo']}>
      <Routes>
        <Route path="/clientes/novo" element={<ClienteFormPage />} />
        <Route path="/clientes" element={<div>Lista</div>} />
        <Route path="/clientes/:id/edit" element={<div>Editar</div>} />
      </Routes>
    </MemoryRouter>,
  );

  await screen.findByLabelText(/Razão Social/i);
  fireEvent.change(screen.getByLabelText(/Razão Social/i), { target: { value: 'Cliente Teste LTDA' } });
  fireEvent.change(screen.getByLabelText(/^CNPJ/i), { target: { value: CNPJ_OK } });
  fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
}

describe('ClienteFormPage — CNPJ duplicado', () => {
  beforeEach(() => {
    createMock.mockReset();
    searchMock.mockReset();
  });

  it('exibe mensagem amigável, link com match único e mantém os dados após HTTP 400', async () => {
    createMock.mockRejectedValue(axiosLike(400, { cnpj: ['Cliente com este CNPJ já existe.'] }));
    searchMock.mockResolvedValue([{ id: 77, cnpj: CNPJ_DIGITS, razao_social: 'Já cadastrado' }]);

    await preencherESalvar();

    expect(await screen.findByTestId('cliente-form-save-error-main')).toHaveTextContent(
      MSG_CNPJ_CLIENTE_DUPLICADO,
    );
    expect(screen.queryByText(/Request failed with status code 400/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Razão Social/i)).toHaveValue('CLIENTE TESTE LTDA');
    expect(screen.getByLabelText(/^CNPJ/i)).toHaveValue(CNPJ_OK);
    expect(screen.queryByTestId('cliente-form-save-error-hint')).not.toBeInTheDocument();
    expect(await screen.findByTestId('cliente-form-abrir-existente')).toHaveAttribute(
      'href',
      '/clientes/77/edit',
    );
  });

  it('401 e 403 do save não viram mensagem de duplicidade', async () => {
    createMock.mockRejectedValue(axiosLike(401, { detail: 'Authentication credentials were not provided.' }));
    await preencherESalvar();
    expect(await screen.findByTestId('cliente-form-save-error')).toHaveTextContent(SESSION_EXPIRED_MESSAGE);
    expect(screen.queryByText(MSG_CNPJ_CLIENTE_DUPLICADO)).not.toBeInTheDocument();

    createMock.mockRejectedValue(axiosLike(403, { detail: 'Permission denied.' }));
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(await screen.findByText(PERMISSION_DENIED_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByText(MSG_CNPJ_CLIENTE_DUPLICADO)).not.toBeInTheDocument();
  });

  it('zero matches: mensagem principal permanece, orientação de listagem, sem link', async () => {
    createMock.mockRejectedValue(axiosLike(400, { cnpj: ['Cliente com este CNPJ já existe.'] }));
    searchMock.mockResolvedValue([]);
    await preencherESalvar();
    await waitFor(() => {
      expect(screen.getByTestId('cliente-form-save-error-main')).toHaveTextContent(MSG_CNPJ_CLIENTE_DUPLICADO);
      expect(screen.getByTestId('cliente-form-save-error-hint')).toHaveTextContent(
        MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM,
      );
    });
    expect(screen.queryByTestId('cliente-form-abrir-existente')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Razão Social/i)).toHaveValue('CLIENTE TESTE LTDA');
  });

  it('múltiplos matches: sem escolha automática e sem link', async () => {
    createMock.mockRejectedValue(axiosLike(400, { cnpj: ['Cliente com este CNPJ já existe.'] }));
    searchMock.mockResolvedValue([
      { id: 1, cnpj: CNPJ_DIGITS, razao_social: 'A' },
      { id: 2, cnpj: CNPJ_OK, razao_social: 'B' },
    ]);
    await preencherESalvar();
    await waitFor(() => {
      expect(screen.getByTestId('cliente-form-save-error-main')).toHaveTextContent(MSG_CNPJ_CLIENTE_DUPLICADO);
      expect(screen.getByTestId('cliente-form-save-error-hint')).toHaveTextContent(
        MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM,
      );
    });
    expect(screen.queryByTestId('cliente-form-abrir-existente')).not.toBeInTheDocument();
  });

  it('busca auxiliar falha: mensagem principal permanece, sem link e sem hint', async () => {
    createMock.mockRejectedValue(axiosLike(400, { cnpj: ['Cliente com este CNPJ já existe.'] }));
    searchMock.mockRejectedValue(axiosLike(403, { detail: 'Permission denied.' }));
    await preencherESalvar();
    expect(await screen.findByTestId('cliente-form-save-error-main')).toHaveTextContent(
      MSG_CNPJ_CLIENTE_DUPLICADO,
    );
    expect(screen.queryByTestId('cliente-form-save-error-hint')).not.toBeInTheDocument();
    expect(screen.queryByTestId('cliente-form-abrir-existente')).not.toBeInTheDocument();
    expect(screen.queryByText(PERMISSION_DENIED_MESSAGE)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Razão Social/i)).toHaveValue('CLIENTE TESTE LTDA');
    expect(screen.getByLabelText(/^CNPJ/i)).toHaveValue(CNPJ_OK);
  });
});
