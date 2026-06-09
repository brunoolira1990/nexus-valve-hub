import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Header } from '@/components/Header';
import { EmpresaAtualBadge } from '@/components/header/EmpresaAtualBadge';
import { UserMenu } from '@/components/header/UserMenu';

const EMPRESA_COMPLETA = 'NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA';

vi.mock('@/hooks/useAppContexto', () => ({
  useAppContexto: () => ({
    contexto: {
      empresa: {
        id: 1,
        nome_exibicao: EMPRESA_COMPLETA,
        razao_social: EMPRESA_COMPLETA,
        cnpj: '12345678000199',
        ambiente: 'homologacao',
      },
      usuario: {
        id: 1,
        nome: 'BRUNO PRADO DE LIRA',
        nome_exibicao: 'BRUNO PRADO DE LIRA',
        nome_curto: 'BRUNO P.',
        email: 'admin@localhost',
        email_tecnico: true,
        username: 'admin',
        perfil: 'Superusuário',
        perfil_label: 'Superusuário',
        is_admin: true,
        colaborador_nome: 'BRUNO PRADO DE LIRA',
      },
      colaborador: {
        id: 1,
        nome: 'BRUNO PRADO DE LIRA',
        codigo: 'B001',
        email: 'admin@localhost',
        funcoes_internas: [],
      },
      ambiente: 'homologacao',
      ambiente_label: 'Homologação',
    },
    loading: false,
    refresh: vi.fn(),
  }),
  clearAppContextoCache: vi.fn(),
}));

vi.mock('@/components/header/GlobalSearch', () => ({
  GlobalSearch: () => <input aria-label="Busca global" placeholder="Buscar…" />,
}));

describe('Header 401494', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exibe nome completo da empresa', () => {
    render(
      <MemoryRouter>
        <Header onToggleSidebar={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByText(EMPRESA_COMPLETA)).toBeInTheDocument();
  });

  it('mantém selo Homologação', () => {
    render(
      <MemoryRouter>
        <Header onToggleSidebar={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Homologação')).toBeInTheDocument();
  });

  it('exibe nome do colaborador, não username', () => {
    render(
      <MemoryRouter>
        <Header onToggleSidebar={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByText('BRUNO PRADO DE LIRA')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^admin$/i })).not.toBeInTheDocument();
  });
});

describe('UserMenu 401494', () => {
  it('mostra nome, e-mail, login e perfil no dropdown', async () => {
    render(
      <MemoryRouter>
        <UserMenu
          usuario={{
            id: 1,
            nome: 'BRUNO PRADO DE LIRA',
            nome_exibicao: 'BRUNO PRADO DE LIRA',
            email: 'admin@localhost',
            username: 'admin',
            perfil: 'Superusuário',
            perfil_label: 'Superusuário',
            is_admin: true,
            colaborador_nome: 'BRUNO PRADO DE LIRA',
          }}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Menu do usuário/i }));
    await waitFor(() => {
      expect(screen.getByText('Login: admin')).toBeInTheDocument();
      expect(screen.getByText('Perfil: Superusuário')).toBeInTheDocument();
      expect(screen.getByText(/admin@localhost/)).toBeInTheDocument();
    });
  });
});

describe('EmpresaAtualBadge 401494', () => {
  it('tooltip com razão social e CNPJ', () => {
    render(
      <MemoryRouter>
        <EmpresaAtualBadge
          empresa={{
            id: 1,
            nome_exibicao: EMPRESA_COMPLETA,
            razao_social: EMPRESA_COMPLETA,
            cnpj: '12345678000199',
            ambiente: 'homologacao',
          }}
        />
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: /Ver empresa atual/i });
    expect(link).toHaveAttribute('title', expect.stringContaining('CNPJ'));
    expect(link).toHaveAttribute('title', expect.stringContaining(EMPRESA_COMPLETA));
  });

  it('trunca apenas com classe truncate no span interno', () => {
    render(
      <MemoryRouter>
        <EmpresaAtualBadge
          empresa={{
            id: 1,
            nome_exibicao: EMPRESA_COMPLETA,
            razao_social: EMPRESA_COMPLETA,
            cnpj: '12345678000199',
            ambiente: 'homologacao',
          }}
        />
      </MemoryRouter>,
    );
    const span = screen.getByText(EMPRESA_COMPLETA);
    expect(span.className).toMatch(/truncate/);
  });
});
