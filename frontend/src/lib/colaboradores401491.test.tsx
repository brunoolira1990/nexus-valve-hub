import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { labelAcessoComPerfil, PERFIS_ACESSO } from '@/lib/colaboradorAcesso';
import { CriarUsuarioColaboradorModal } from '@/components/cadastros/CriarUsuarioColaboradorModal';
import type { Colaborador } from '@/types';

vi.mock('@/services/api/colaboradores', () => ({
  colaboradoresService: {
    criarUsuario: vi.fn(),
  },
}));

const base: Colaborador = {
  id: 1,
  nome: 'Teste Acesso',
  codigo: 'TA1',
  email: 'teste@acesso.com',
  ativo: true,
  eh_vendedor: false,
  eh_comprador: false,
  eh_responsavel_fiscal: false,
  eh_responsavel_financeiro: true,
  eh_responsavel_estoque: false,
  eh_responsavel_qualidade: false,
  eh_administrador: false,
  acesso_status: 'SEM_USUARIO',
  acesso_status_label: 'Sem acesso',
  pode_criar_usuario: true,
  perfil_sugerido: 'financeiro',
  perfil_sugerido_label: 'Financeiro',
};

describe('colaboradorAcesso', () => {
  it('label com perfil ativo', () => {
    expect(
      labelAcessoComPerfil({
        acesso_status: 'USUARIO_ATIVO',
        acesso_status_label: 'Usuário ativo',
        perfil_acesso_label: 'Financeiro',
      }),
    ).toBe('Financeiro');
  });

  it('perfis incluem Financeiro', () => {
    expect(PERFIS_ACESSO.some((p) => p.value === 'financeiro')).toBe(true);
  });
});

describe('CriarUsuarioColaboradorModal', () => {
  it('exige e-mail', async () => {
    render(
      <CriarUsuarioColaboradorModal colaborador={{ ...base, email: '' }} onClose={() => undefined} onSuccess={() => undefined} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Criar usuário/i }));
    expect(await screen.findByText(/Informe o e-mail|Informe um e-mail válido/i)).toBeInTheDocument();
  });

  it('mostra sugestão de perfil', () => {
    render(
      <CriarUsuarioColaboradorModal colaborador={base} onClose={() => undefined} onSuccess={() => undefined} />,
    );
    expect(screen.getByText(/Perfil sugerido com base nas funções internas/i)).toBeInTheDocument();
  });
});
