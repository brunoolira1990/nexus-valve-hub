import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Header } from '@/components/Header';
import { TopBar } from '@/components/layout/TopBar';
import { EmpresaAtualBadge } from '@/components/header/EmpresaAtualBadge';
import { UserMenu } from '@/components/header/UserMenu';

vi.mock('@/hooks/useAppContexto', () => ({
  useAppContexto: () => ({
    contexto: {
      empresa: {
        id: 1,
        nome_exibicao: 'NEXUS VÁLVULAS',
        razao_social: 'NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA',
        cnpj: '12345678000199',
        ambiente: 'homologacao',
      },
      usuario: {
        id: 1,
        nome: 'Admin',
        nome_exibicao: 'Admin',
        email: 'admin@test.com',
        username: 'admin',
        perfil: 'Administrador',
        perfil_label: 'Administrador',
        is_admin: true,
      },
      colaborador: null,
      ambiente: 'homologacao',
      ambiente_label: 'Homologação',
    },
    loading: false,
  }),
  clearAppContextoCache: vi.fn(),
}));

vi.mock('@/components/header/GlobalSearch', () => ({
  GlobalSearch: () => <input aria-label="Busca global" placeholder="Buscar…" />,
}));

vi.mock('@/components/layout/NotificacoesSino', () => ({
  NotificacoesSino: () => <button type="button" aria-label="Notificações" />,
}));

describe('Header 401493', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exibe nome da empresa', () => {
    render(
      <MemoryRouter>
        <Header onToggleSidebar={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByText('NEXUS VÁLVULAS')).toBeInTheDocument();
  });

  it('mantém selo Homologação', () => {
    render(
      <MemoryRouter>
        <Header onToggleSidebar={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Homologação')).toBeInTheDocument();
  });

  it('não exibe Minha conta solto', () => {
    render(
      <MemoryRouter>
        <Header onToggleSidebar={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('link', { name: /^Minha conta$/i })).not.toBeInTheDocument();
  });

  it('exibe menu do usuário na TopBar', () => {
    render(
      <MemoryRouter>
        <TopBar onOpenAppSwitcher={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Menu do usuário Admin/i })).toBeInTheDocument();
  });

  it('exibe busca global na TopBar', () => {
    render(
      <MemoryRouter>
        <TopBar onOpenAppSwitcher={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText('Busca global')).toBeInTheDocument();
  });

  it('criar rápido só expõe rotas de criação que existem', () => {
    render(
      <MemoryRouter>
        <TopBar onOpenAppSwitcher={() => undefined} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Criar rapidamente/i }));
    expect(screen.getByRole('menuitem', { name: 'Novo Produto' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Nova Família' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Novo Pedido de Compra' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: /NF-e/i })).not.toBeInTheDocument();
  });
});

describe('UserMenu', () => {
  it('abre menu com Minha conta e Alterar senha', () => {
    render(
      <MemoryRouter>
        <UserMenu
          usuario={{
            id: 1,
            nome: 'Bruno',
            nome_exibicao: 'Bruno',
            email: 'b@test.com',
            username: 'bruno',
            perfil: 'Administrador',
            perfil_label: 'Administrador',
            is_admin: true,
          }}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Menu do usuário Bruno/i }));
    expect(screen.getByRole('menuitem', { name: /Minha conta/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /Alterar senha/i })).toBeInTheDocument();
  });
});

describe('EmpresaAtualBadge', () => {
  it('mostra empresa não configurada', () => {
    render(
      <MemoryRouter>
        <EmpresaAtualBadge empresa={null} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Empresa não configurada/i)).toBeInTheDocument();
  });
});
