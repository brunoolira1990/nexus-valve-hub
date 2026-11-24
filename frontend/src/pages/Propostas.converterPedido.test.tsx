import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Propostas from '@/pages/Propostas';
import { propostasService } from '@/services/api/comercial';
import { toast } from 'sonner';
import type { Proposta } from '@/types';

const listState = vi.hoisted(() => ({
  current: {
    items: [] as unknown[],
    count: 0,
    page: 1,
    pageSize: 20,
    totalPages: 0,
    search: '',
    setSearch: vi.fn(),
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    filters: {},
    setFilter: vi.fn(),
    loading: false,
    error: null as string | null,
    reload: vi.fn(),
  },
}));

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: () => listState.current,
}));

vi.mock('@/services/api/comercial', () => ({
  propostasService: {
    convertToPedido: vi.fn(),
    delete: vi.fn(),
    visualizarPdf: vi.fn(),
    baixarPdf: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const convertToPedido = vi.mocked(propostasService.convertToPedido);

function propostaBase(overrides: Partial<Proposta> = {}): Proposta {
  return {
    id: 7,
    numero: 'PROP-7',
    cliente_nome: 'Cliente Teste',
    data: '2026-11-01',
    validade: '2026-11-30',
    vendedor_nome: 'Vendedor',
    status: 'APROVADA',
    valor_total: 1000,
    pode_gerar_pedido: true,
    requer_recuperacao: false,
    pedidos_gerados_resumo: [],
    ...overrides,
  } as Proposta;
}

function renderPage(items: Proposta[]) {
  listState.current = { ...listState.current, items, count: items.length, reload: vi.fn() };
  return render(
    <MemoryRouter>
      <Propostas />
    </MemoryRouter>,
  );
}

describe('Propostas — converter para pedido pelo carrinho', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('chama POST converter-pedido, mostra toast e recarrega a lista', async () => {
    convertToPedido.mockResolvedValue({
      pedido_id: 99,
      numero: 'PV-99',
      status: 'ABERTO',
      proposta_id: 7,
      proposta_status: 'CONVERTIDA',
      itens_criados: 2,
      mensagens: [],
      ja_existia: false,
    });

    renderPage([propostaBase()]);
    fireEvent.click(screen.getByTitle('Gerar pedido de venda'));

    await waitFor(() => expect(convertToPedido).toHaveBeenCalledWith(7));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('PV-99')));
    expect(listState.current.reload).toHaveBeenCalled();
  });

  it('exibe o detail do 400 em banner sem quebrar a tela', async () => {
    const detail = 'A condição atual da proposta não corresponde à condição aprovada pelo Financeiro.';
    convertToPedido.mockRejectedValue({
      response: { status: 400, data: { code: 'CONDICAO_DIVERGENTE', detail } },
    });

    renderPage([propostaBase()]);
    fireEvent.click(screen.getByTitle('Gerar pedido de venda'));

    const banner = await screen.findByRole('alert');
    expect(banner).toHaveTextContent(detail);
    expect(listState.current.reload).not.toHaveBeenCalled();
  });

  it('não dispara POST quando a proposta exige recuperação', async () => {
    renderPage([propostaBase({ requer_recuperacao: true, pode_gerar_pedido: false })]);
    fireEvent.click(screen.getByTitle('Converter em pedido'));

    await waitFor(() => expect(convertToPedido).not.toHaveBeenCalled());
  });
});
