import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
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

  it('abre modal de cadastro ao clicar em Cadastrar fornecedor', () => {
    render(
      <FornecedorEntradaAcoes
        status={{
          status: 'nao_encontrado',
          identificado: false,
          pode_cadastrar: true,
          pode_vincular_manual: true,
          mensagem: 'Fornecedor não identificado.',
          cnpj_documento: '52512837000113',
          sugestao_cadastro: {
            razao_social: 'ORANIO DOMINGUES',
            cnpj: '52512837000113',
          },
        }}
        onVincular={vi.fn()}
        onCadastrar={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Cadastrar fornecedor/i }));
    expect(screen.getByRole('dialog', { name: /Cadastrar fornecedor/i })).toBeInTheDocument();
    expect(screen.getByDisplayValue('ORANIO DOMINGUES')).toBeInTheDocument();
    expect(screen.getByDisplayValue('52512837000113')).toBeInTheDocument();
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
