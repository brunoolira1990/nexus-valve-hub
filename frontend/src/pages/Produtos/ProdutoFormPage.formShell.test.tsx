/**
 * Ficha de edição do Produto (Sprint 3.16): PageHeader → FormShell com rail de Chatter.
 * O "Salvar" já vivia nesta página, então o teste garante o shell e o rail.
 */
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen, within } from '@testing-library/react';
import ProdutoFormPage from '@/pages/Produtos/ProdutoFormPage';
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

function renderComRota(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/produtos/novo" element={<ProdutoFormPage />} />
        <Route path="/produtos/:id/editar" element={<ProdutoFormPage />} />
        <Route path="/produtos" element={<div>Lista de produtos</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProdutoFormPage — FormShell + rail do Chatter', () => {
  it('edição: shell com código no título, Salvar/Descartar e rail do Chatter', async () => {
    renderComRota('/produtos/77/editar');

    const header = await screen.findByTestId('form-shell-header');
    expect(header).toHaveTextContent('VAL-ESF-INOX-2');
    // 'Salvar' existe no cabeçalho e no rodapé mobile: a checagem é a do cabeçalho.
    expect(within(header).getByRole('button', { name: 'Salvar' })).toBeInTheDocument();
    expect(within(header).getByRole('button', { name: 'Descartar' })).toBeInTheDocument();
    const rail = await screen.findByTestId('form-shell-rail');
    expect(rail).toHaveTextContent('Chatter');
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
  });

  it('novo produto: o rail avisa que ainda não há registro', async () => {
    renderComRota('/produtos/novo');

    const rail = await screen.findByTestId('form-shell-rail');
    expect(rail).toHaveTextContent('Chatter');
    expect(screen.getByText(/Salve o registro primeiro/i)).toBeInTheDocument();
  });
});
