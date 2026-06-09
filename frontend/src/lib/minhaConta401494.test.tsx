import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MinhaConta from '@/pages/MinhaConta';
import { appContextoService } from '@/services/api/appContexto';

vi.mock('@/hooks/useAppContexto', () => ({
  setAppContextoCache: vi.fn(),
  clearAppContextoCache: vi.fn(),
}));

const minhaContaMock = {
  empresa: {
    id: 1,
    nome_exibicao: 'NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA',
    razao_social: 'NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA',
    cnpj: '12345678000199',
    ambiente: 'homologacao',
  },
  usuario: {
    id: 1,
    nome: 'BRUNO PRADO DE LIRA',
    nome_exibicao: 'BRUNO PRADO DE LIRA',
    email: 'admin@localhost',
    email_tecnico: true,
    username: 'admin',
    perfil: 'Superusuário',
    perfil_label: 'Superusuário',
    is_admin: true,
    is_staff: true,
    is_superuser: true,
    is_active: true,
  },
  colaborador: {
    id: 1,
    nome: 'BRUNO PRADO DE LIRA',
    codigo: 'B001',
    email: 'admin@localhost',
    telefone: '11999998888',
    cargo: 'Diretor',
    departamento: 'TI',
    ativo: true,
    funcoes_internas: ['Admin'],
  },
  ambiente: 'homologacao',
  ambiente_label: 'Homologação',
  avisos: ['Este e-mail parece ser técnico ou local. Para produção, informe um e-mail real.'],
};

describe('MinhaConta 401494', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(appContextoService, 'getMinhaConta').mockResolvedValue(minhaContaMock);
    vi.spyOn(appContextoService, 'patchMinhaConta').mockResolvedValue({
      ...minhaContaMock,
      usuario: { ...minhaContaMock.usuario, email: 'bruno@test.com' },
      mensagem: 'Seus dados foram atualizados.',
    });
  });

  it('mostra Nome e Login separados', async () => {
    render(
      <MemoryRouter>
        <MinhaConta />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Dados pessoais/i })).toBeInTheDocument();
    });
    const blocoPessoais = screen.getByRole('heading', { name: /Dados pessoais/i }).closest('section');
    expect(blocoPessoais).toHaveTextContent('BRUNO PRADO DE LIRA');
    const blocoAcesso = screen.getByRole('heading', { name: /Dados de acesso/i }).closest('section');
    expect(blocoAcesso).toHaveTextContent('admin');
  });

  it('mostra aviso para e-mail técnico', async () => {
    render(
      <MemoryRouter>
        <MinhaConta />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/técnico ou local/i)).toBeInTheDocument();
    });
  });

  it('tem ação Editar meus dados', async () => {
    render(
      <MemoryRouter>
        <MinhaConta />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Editar meus dados/i })).toBeInTheDocument();
    });
  });

  it('Alterar senha continua acessível', async () => {
    render(
      <MemoryRouter>
        <MinhaConta />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /Alterar senha/i })).toHaveAttribute(
        'href',
        '/minha-conta/alterar-senha',
      );
    });
  });

  it('Editar meus dados salva e atualiza', async () => {
    render(
      <MemoryRouter>
        <MinhaConta />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByRole('button', { name: /Editar meus dados/i }));
    fireEvent.click(screen.getByRole('button', { name: /Editar meus dados/i }));
    const emailInput = await screen.findByLabelText(/E-mail/i);
    fireEvent.change(emailInput, { target: { value: 'bruno@test.com' } });
    fireEvent.click(screen.getByRole('button', { name: /^Salvar$/i }));
    await waitFor(() => {
      expect(appContextoService.patchMinhaConta).toHaveBeenCalledWith(
        expect.objectContaining({ email: 'bruno@test.com' }),
      );
    });
  });
});
