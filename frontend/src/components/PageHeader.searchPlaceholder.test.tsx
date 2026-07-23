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
        />
      </MemoryRouter>,
    );
    expect(
      screen.getByPlaceholderText('Digite parte do número do pedido, como 0006 ou 20260714.'),
    ).toBeInTheDocument();
  });
});
