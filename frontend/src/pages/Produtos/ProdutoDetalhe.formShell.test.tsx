/**
 * Produto (Sprint 3.16): a ficha de edição e a visualização passam a ser FormShell com
 * rail de Chatter. O "Salvar" já vivia na página, então o que este teste garante é o rail.
 */
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen, fireEvent, within } from '@testing-library/react';
import ProdutoDetalhe from '@/pages/Produtos/ProdutoDetalhe';
import type { Produto } from '@/types';

const PRODUTO = vi.hoisted(() => ({
  id: 77,
  codigo_completo: 'VAL-ESF-INOX-2',
  descricao: 'VÁLVULA DE ESFERA INOX 316 2 POL',
  ativo: true,
  ncm: '',
  familia: null,
  familia_detalhes: null,
}));

vi.mock('@/services/api/produtos', () => ({
  produtosService: {
    getById: vi.fn().mockResolvedValue(PRODUTO as unknown as Produto),
    create: vi.fn(),
    update: vi.fn(),
    search: vi.fn().mockResolvedValue([]),
  },
  familiasProdutoService: {
    getAll: vi.fn().mockResolvedValue([]),
    getById: vi.fn().mockResolvedValue(null),
  },
  ncmApiService: { search: vi.fn().mockResolvedValue([]) },
  roscasConexaoService: { getAll: vi.fn().mockResolvedValue([]) },
  schedulesEspessuraService: { getAll: vi.fn().mockResolvedValue([]) },
  polegadasService: { getAll: vi.fn().mockResolvedValue([]) },
  familiaVariacoesService: {
    listRoscasPermitidas: vi.fn().mockResolvedValue([]),
    listSchedulesPermitidos: vi.fn().mockResolvedValue([]),
    listPolegadasPermitidas: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('@/services/api/materiais', () => ({
  materiaisService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/produtoComposicao', () => ({
  listProdutoComposicoes: vi.fn().mockResolvedValue([]),
  createProdutoComposicao: vi.fn(),
  updateProdutoComposicao: vi.fn(),
  deleteProdutoComposicao: vi.fn(),
}));

function renderDetalhe() {
  render(
    <MemoryRouter initialEntries={['/produtos/77']}>
      <Routes>
        <Route path="/produtos/:id" element={<ProdutoDetalhe />} />
        <Route path="/produtos/:id/editar" element={<div>Ficha de edição</div>} />
        <Route path="/produtos" element={<div>Lista de produtos</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProdutoDetalhe — FormShell + rail do Chatter', () => {
  it('mostra o rail do Chatter na visualização e o código no título', async () => {
    renderDetalhe();

    const header = await screen.findByTestId('form-shell-header');
    expect(header).toHaveTextContent('VAL-ESF-INOX-2');
    const rail = await screen.findByTestId('form-shell-rail');
    expect(rail).toHaveTextContent('Chatter');
    // Com id gravado, o chatter já pergunta o histórico do produto.
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
  });

  it('o "Editar" do cabeçalho leva para a ficha de edição', async () => {
    renderDetalhe();

    // A ação principal também é replicada no rodapé mobile: o clique é o do cabeçalho.
    const header = await screen.findByTestId('form-shell-header');
    fireEvent.click(within(header).getByRole('button', { name: 'Editar' }));
    expect(await screen.findByText('Ficha de edição')).toBeInTheDocument();
  });

  it('a ação principal ganha rodapé fixo no mobile', async () => {
    renderDetalhe();

    const rodape = await screen.findByTestId('form-shell-rodape-mobile');
    expect(within(rodape).getByRole('button', { name: 'Editar' })).toBeInTheDocument();
  });
});
