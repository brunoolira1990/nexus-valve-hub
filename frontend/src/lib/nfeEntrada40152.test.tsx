import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FornecedorEntradaAcoes } from '@/components/fiscal/FornecedorEntradaAcoes';

vi.mock('@/components/financeiro/FornecedorSearchSelect', () => ({
  FornecedorSearchSelect: () => <div data-testid="fornecedor-search" />,
}));

describe('FornecedorEntradaAcoes', () => {
  it('mostra cadastrar e vincular quando fornecedor não identificado', () => {
    render(
      <FornecedorEntradaAcoes
        status={{
          status: 'nao_encontrado',
          identificado: false,
          pode_cadastrar: true,
          pode_vincular_manual: true,
          mensagem: 'Fornecedor não identificado.',
          cnpj_documento: '62070693000146',
        }}
        onVincular={vi.fn()}
        onCadastrar={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /Cadastrar fornecedor/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Vincular fornecedor/i })).toBeInTheDocument();
  });

  it('não mostra ações quando fornecedor identificado', () => {
    render(
      <FornecedorEntradaAcoes
        status={{
          status: 'vinculado',
          identificado: true,
          fornecedor_nome: 'CONEFER',
        }}
        onVincular={vi.fn()}
        onCadastrar={vi.fn()}
      />,
    );
    expect(screen.queryByRole('button', { name: /Cadastrar fornecedor/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Fornecedor identificado/i)).toBeInTheDocument();
  });
});
