import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ColaboradorAcessoSection } from '@/components/cadastros/ColaboradorAcessoSection';
import { badgeAcessoListagem, labelAcessoComPerfil } from '@/lib/colaboradorAcesso';
import type { Colaborador } from '@/types';

vi.mock('@/components/cadastros/EditarAcessoModal', () => ({
  EditarAcessoModal: ({ onClose }: { onClose: () => void }) => (
    <div>
      Modal Editar acesso<button onClick={onClose}>fechar</button>
    </div>
  ),
}));
vi.mock('@/components/cadastros/CriarUsuarioColaboradorModal', () => ({
  CriarUsuarioColaboradorModal: () => null,
}));
vi.mock('@/components/cadastros/VincularUsuarioExistenteModal', () => ({
  VincularUsuarioExistenteModal: () => null,
}));
vi.mock('@/components/cadastros/DefinirPerfilAcessoModal', () => ({
  DefinirPerfilAcessoModal: () => null,
}));
vi.mock('@/components/cadastros/DesativarAcessoModal', () => ({
  DesativarAcessoModal: () => null,
}));
vi.mock('@/components/cadastros/RedefinirSenhaColaboradorModal', () => ({
  RedefinirSenhaColaboradorModal: () => null,
}));

const base: Colaborador = {
  id: 1,
  nome: 'Bruno',
  codigo: 'B001',
  ativo: true,
  eh_vendedor: false,
  eh_comprador: false,
  eh_responsavel_fiscal: false,
  eh_responsavel_financeiro: false,
  eh_responsavel_estoque: false,
  eh_responsavel_qualidade: false,
  eh_administrador: false,
};

describe('colaboradorAcesso 4014102', () => {
  it('listagem mostra Superusuário', () => {
    expect(
      badgeAcessoListagem({
        acesso_status: 'SUPERUSUARIO',
        usuario_is_superuser: true,
        perfil_acesso_label: 'Superusuário',
      }),
    ).toBe('Superusuário');
  });

  it('listagem mostra nome do perfil', () => {
    expect(
      badgeAcessoListagem({
        acesso_status: 'USUARIO_ATIVO',
        perfil_acesso_label: 'Financeiro',
      }),
    ).toBe('Financeiro');
  });

  it('listagem mostra Sem perfil', () => {
    expect(
      labelAcessoComPerfil({
        acesso_status: 'SEM_PERFIL',
        sem_perfil: true,
      }),
    ).toBe('Sem perfil');
  });
});

describe('ColaboradorAcessoSection 4014102', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('mostra login, e-mail, status e perfil', () => {
    render(
      <ColaboradorAcessoSection
        colaborador={{
          ...base,
          usuario_id: 10,
          usuario_login: 'admin',
          usuario_email: 'fiscal01@nexusvalvulas.com.br',
          usuario_ativo: true,
          usuario_is_superuser: true,
          perfil_acesso_label: 'Superusuário',
          acesso_status: 'SUPERUSUARIO',
          pode_editar_acesso: true,
        }}
        onRefresh={() => undefined}
      />,
    );
    expect(screen.getByText('Login')).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('fiscal01@nexusvalvulas.com.br')).toBeInTheDocument();
    expect(screen.getByText('Perfil de acesso')).toBeInTheDocument();
    expect(screen.getAllByText('Superusuário').length).toBeGreaterThan(0);
  });

  it('botão Editar acesso aparece para admin', () => {
    render(
      <ColaboradorAcessoSection
        colaborador={{
          ...base,
          usuario_id: 10,
          usuario_login: 'user1',
          usuario_ativo: true,
          sem_perfil: true,
          acesso_status: 'SEM_PERFIL',
          pode_editar_acesso: true,
        }}
        onRefresh={() => undefined}
      />,
    );
    expect(screen.getByRole('button', { name: /Editar acesso/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Editar acesso/i }));
    expect(screen.getByText(/Modal Editar acesso/i)).toBeInTheDocument();
  });

  it('Redefinir senha continua acessível', () => {
    render(
      <ColaboradorAcessoSection
        colaborador={{
          ...base,
          usuario_id: 10,
          usuario_login: 'user1',
          usuario_ativo: true,
          pode_redefinir_senha: true,
          pode_editar_acesso: true,
        }}
        onRefresh={() => undefined}
      />,
    );
    expect(screen.getByRole('button', { name: /Redefinir senha/i })).toBeInTheDocument();
  });
});
