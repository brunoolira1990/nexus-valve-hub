import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { PageHeader } from '@/components/PageHeader';

describe('PageHeader searchPlaceholder', () => {
  it('exibe hint de busca parcial por número de pedido', () => {
    render(
      <MemoryRouter>
        <PageHeader
          title="Pedidos de Venda"
          searchValue=""
          onSearch={vi.fn()}
          searchPlaceholder="Digite parte do número do pedido, como 0006 ou 20260714."
          onAdd={vi.fn()}
          addLabel="Novo Pedido"
        />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(
      'Digite parte do número do pedido, como 0006 ou 20260714.',
    );
    expect(input).toBeInTheDocument();
    expect(input).toHaveClass('w-full');
    // Container responsivo: min ~320px no sm+, sem sm:w-56 fixo no input.
    const wrap = input.parentElement;
    expect(wrap).toHaveClass('sm:min-w-[20rem]');
    expect(wrap).toHaveClass('w-full');
    expect(wrap?.className).not.toMatch(/\bsm:w-56\b/);
    expect(screen.getByRole('button', { name: /Novo Pedido/i })).toBeInTheDocument();
  });
});
