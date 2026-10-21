import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProdutoRastreabilidadeTab } from '@/components/produtos/ProdutoRastreabilidadeTab';
import { produtosService } from '@/services/api/produtos';
import type { ProdutoRastreabilidade } from '@/types';

vi.mock('@/services/api/produtos', () => ({
  produtosService: {
    getPainelRastreabilidade: vi.fn(),
  },
}));

const DADOS: ProdutoRastreabilidade = {
  corridas: [
    {
      id: 281,
      codigo: '7287',
      lote: 'L-9',
      saldo: 12,
      fornecedor_nome: 'Forn Rastreabilidade',
      origem_tecnica: 'NF-e 44445',
      nf_entrada_numero: '44445',
      possui_cf: true,
      cf_numero: 'CF-2026-0001',
    },
    {
      id: 282,
      codigo: '7288',
      lote: null,
      saldo: 0,
      fornecedor_nome: null,
      origem_tecnica: 'Cadastro manual',
      nf_entrada_numero: null,
      possui_cf: true,
      cf_numero: null,
    },
  ],
  certificados_qualidade: [],
  certificados_fornecedor: [],
  nfs_entrada: [],
  nfs_saida: [],
};

function renderTab() {
  return render(
    <MemoryRouter>
      <ProdutoRastreabilidadeTab produtoId={77} active />
    </MemoryRouter>,
  );
}

describe('ProdutoRastreabilidadeTab', () => {
  beforeEach(() => {
    vi.mocked(produtosService.getPainelRastreabilidade).mockReset();
    vi.mocked(produtosService.getPainelRastreabilidade).mockResolvedValue(DADOS);
  });

  it('mostra o número do CF na coluna CF em vez de Sim/Não', async () => {
    renderTab();
    const linha = await screen.findByRole('row', { name: /7287/ });
    expect(linha).toHaveTextContent('CF-2026-0001');
    expect(linha).not.toHaveTextContent('Sim');
  });

  it('distingue CF sem número registrado de corrida sem CF', async () => {
    renderTab();
    const linha = await screen.findByRole('row', { name: /7288/ });
    expect(linha).toHaveTextContent('Sem número');
  });

  it('exibe o código da corrida, não o id do banco', async () => {
    renderTab();
    const linha = await screen.findByRole('row', { name: /7287/ });
    expect(linha).not.toHaveTextContent('281');
  });
});
