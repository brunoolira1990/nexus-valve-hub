import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { UserMenu } from '@/components/header/UserMenu';

describe('UserMenu 4014941', () => {
  const usuario = {
    id: 1,
    nome: 'admin',
    nome_exibicao: 'admin',
    colaborador_nome: 'BRUNO PRADO DE LIRA',
    colaborador_id: 1,
    email: 'admin@localhost',
    username: 'admin',
    perfil: 'Superusuário',
    perfil_label: 'Superusuário',
    is_admin: true,
  };

  it('mostra colaborador_nome quando nome_exibicao ainda é o login', () => {
    render(
      <MemoryRouter>
        <UserMenu usuario={usuario} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Menu do usuário BRUNO PRADO DE LIRA/i })).toBeInTheDocument();
    expect(screen.queryByText(/^admin$/)).not.toBeInTheDocument();
  });

  it('abre dropdown com Minha conta e Alterar senha', async () => {
    render(
      <MemoryRouter>
        <UserMenu usuario={usuario} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Menu do usuário/i }));
    await waitFor(() => {
      expect(screen.getByRole('menuitem', { name: /Minha conta/i })).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /Alterar senha/i })).toBeInTheDocument();
    });
  });
});
