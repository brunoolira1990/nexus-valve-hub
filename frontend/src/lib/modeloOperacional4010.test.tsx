import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StatusBadge } from '@/components/nexus/StatusBadge';

describe('ERP 4.0.10 — tokens operacionais Nexus', () => {
  it('StatusBadge renderiza Entrada pendente', () => {
    render(<StatusBadge status="entrada_pendente" />);
    expect(screen.getByText('Entrada pendente')).toBeInTheDocument();
  });

  it('StatusBadge renderiza Entrada conciliada', () => {
    render(<StatusBadge status="entrada_conciliada" />);
    expect(screen.getByText('Entrada conciliada')).toBeInTheDocument();
  });

  it('StatusBadge renderiza Retirada fornecedor', () => {
    render(<StatusBadge status="retirada_fornecedor" />);
    expect(screen.getByText('Retirada fornecedor')).toBeInTheDocument();
  });

  it('StatusBadge renderiza Entrega direta', () => {
    render(<StatusBadge status="entrega_direta" />);
    expect(screen.getByText('Entrega direta')).toBeInTheDocument();
  });
});
