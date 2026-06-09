import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CriarUsuarioColaboradorModal } from '@/components/cadastros/CriarUsuarioColaboradorModal';
import { RedefinirSenhaColaboradorModal } from '@/components/cadastros/RedefinirSenhaColaboradorModal';
import type { Colaborador } from '@/types';

vi.mock('@/services/api/colaboradores', () => ({
  colaboradoresService: {
    criarUsuario: vi.fn(),
    redefinirSenha: vi.fn(),
  },
}));

const base: Colaborador = {
  id: 1,
  nome: 'Teste Senha',
  codigo: 'TS1',
  email: 'teste@senha.com',
  ativo: true,
  eh_vendedor: false,
  eh_comprador: false,
  eh_responsavel_fiscal: false,
  eh_responsavel_financeiro: false,
  eh_responsavel_estoque: false,
  eh_responsavel_qualidade: false,
  eh_administrador: false,
  acesso_status: 'SEM_USUARIO',
  pode_criar_usuario: true,
};

describe('CriarUsuarioColaboradorModal 401492', () => {
  it('mostra campos Senha e Confirmar senha', () => {
    render(
      <CriarUsuarioColaboradorModal colaborador={base} onClose={() => undefined} onSuccess={() => undefined} />,
    );
    expect(screen.getByText(/^Senha \*$/)).toBeInTheDocument();
    expect(screen.getByText(/^Confirmar senha \*$/)).toBeInTheDocument();
  });

  it('não menciona convite obrigatório', () => {
    render(
      <CriarUsuarioColaboradorModal colaborador={base} onClose={() => undefined} onSuccess={() => undefined} />,
    );
    expect(screen.queryByText(/convite/i)).not.toBeInTheDocument();
    expect(screen.getByText(/não será exibida novamente após salvar/i)).toBeInTheDocument();
  });

  it('e-mail inválido mostra erro', async () => {
    render(
      <CriarUsuarioColaboradorModal
        colaborador={{ ...base, email: 'comercial04@' }}
        onClose={() => undefined}
        onSuccess={() => undefined}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Criar usuário/i }));
    expect(await screen.findByText(/Informe um e-mail válido/i)).toBeInTheDocument();
  });

  it('senhas divergentes mostram erro', async () => {
    render(
      <CriarUsuarioColaboradorModal colaborador={base} onClose={() => undefined} onSuccess={() => undefined} />,
    );
    const inputs = screen.getAllByDisplayValue('');
    const passwordInputs = inputs.filter((el) => (el as HTMLInputElement).type === 'password');
    fireEvent.change(passwordInputs[0], { target: { value: 'Abc12345!' } });
    fireEvent.change(passwordInputs[1], { target: { value: 'Outra123!' } });
    fireEvent.click(screen.getByRole('button', { name: /Criar usuário/i }));
    expect(await screen.findByText(/não conferem/i)).toBeInTheDocument();
  });
});

describe('RedefinirSenhaColaboradorModal', () => {
  it('valida confirmação divergente', async () => {
    render(
      <RedefinirSenhaColaboradorModal
        colaborador={{ ...base, usuario_id: 2, usuario_login: 'user1', pode_redefinir_senha: true }}
        onClose={() => undefined}
        onSuccess={() => undefined}
      />,
    );
    const passwordInputs = screen.getAllByDisplayValue('').filter((el) => (el as HTMLInputElement).type === 'password');
    fireEvent.change(passwordInputs[0], { target: { value: 'Nova123!' } });
    fireEvent.change(passwordInputs[1], { target: { value: 'Diferente123!' } });
    fireEvent.click(screen.getByRole('button', { name: /Redefinir senha/i }));
    expect(await screen.findByText(/não conferem/i)).toBeInTheDocument();
  });
});
