import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AlocarEntradaParaVendaBlock } from '@/components/fiscal/AlocarEntradaParaVendaBlock';

const resumoBase = {
  item_conferencia_id: 10,
  nf_entrada_historica_item_id: 20,
  produto_id: 1,
  produto_codigo: 'PE-1',
  produto_nome: 'Produto',
  unidade_estoque_calculada: 'PC',
  quantidade_disponivel: '10.000',
  total_alocado: '0.000',
  saldo_entrada: '10.000',
  estado_operacional: 'SEM_ALOCACAO' as const,
  estoque_aplicado: false,
  aviso_estoque: 'Estoque físico ainda não foi aplicado nesta linha.',
  aviso_operacional: 'Alocação operacional e informativa.',
  alocacoes: [] as {
    id: number;
    pedido_venda_item_id: number;
    pedido_venda_id: number;
    pedido_venda_numero: string;
    cliente_nome: string;
    produto_id: number;
    produto_codigo: string;
    produto_nome: string;
    quantidade_alocada: string;
    necessidade_destino: string;
    total_alocado_destino: string;
    saldo_destino: string;
    faturamento_id: number | null;
    faturamento_numero: string | null;
    nfe_saida_id: number | null;
    nfe_saida_numero: string | null;
    criado_em: string | null;
    atualizado_em: string | null;
  }[],
};

vi.mock('@/services/api/alocacaoAtendimento', () => ({
  alocacaoAtendimentoService: {
    resumoEntradaVenda: vi.fn(),
    opcoesPedidosVendaItens: vi.fn().mockResolvedValue([
      {
        id: 99,
        pedido_venda_id: 1,
        pedido_venda_numero: 'PV-1',
        cliente_nome: 'Cliente',
        produto_id: 1,
        produto_codigo: 'PE-1',
        produto_nome: 'Produto',
        quantidade_necessaria: '10.000',
        quantidade_ja_alocada: '0.000',
        saldo_destino: '10.000',
        faturamento_id: null,
        faturamento_numero: null,
        nfe_saida_id: null,
        nfe_saida_numero: null,
        label: 'PV-1 — Cliente — PE-1 (saldo 10.000)',
      },
    ]),
    alocarEntradaVenda: vi.fn(),
    atualizarQuantidadeEntradaVenda: vi.fn(),
    desvincularEntradaVenda: vi.fn(),
  },
}));

import { alocacaoAtendimentoService } from '@/services/api/alocacaoAtendimento';

describe('AlocarEntradaParaVendaBlock', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue(resumoBase);
  });

  it('mostra aviso de estoque não aplicado e ação Alocar para venda', async () => {
    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Alocar para venda')).toBeInTheDocument();
    });
    expect(screen.getByText(/não movimenta estoque/i)).toBeInTheDocument();
    expect(screen.getByText(/ainda não foi aplicado/i)).toBeInTheDocument();
    expect(screen.getByText('Sem alocação')).toBeInTheDocument();
  });

  it('abre formulário de busca de PV ao clicar Abrir', async () => {
    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    await waitFor(() => expect(screen.getByText('Abrir')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Abrir'));
    expect(screen.getByPlaceholderText(/Pedido de Venda/i)).toBeInTheDocument();
    expect(screen.getByText('Salvar alocação')).toBeInTheDocument();
  });

  it('atualiza resumo após alocar', async () => {
    vi.mocked(alocacaoAtendimentoService.alocarEntradaVenda).mockResolvedValue({
      alocacao: { id: 1 } as never,
      resumo: {
        ...resumoBase,
        total_alocado: '4.000',
        saldo_entrada: '6.000',
        estado_operacional: 'PARCIAL',
        alocacoes: [
          {
            id: 1,
            pedido_venda_item_id: 99,
            pedido_venda_id: 1,
            pedido_venda_numero: 'PV-1',
            cliente_nome: 'Cliente',
            produto_id: 1,
            produto_codigo: 'PE-1',
            produto_nome: 'Produto',
            quantidade_alocada: '4.000',
            necessidade_destino: '10.000',
            total_alocado_destino: '4.000',
            saldo_destino: '6.000',
            faturamento_id: null,
            faturamento_numero: null,
            nfe_saida_id: null,
            nfe_saida_numero: null,
            criado_em: null,
            atualizado_em: null,
          },
        ],
      },
      acao: 'criado',
    });

    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    await waitFor(() => expect(screen.getByText('Abrir')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Abrir'));

    // Sem seleção de PV o botão não aloca — apenas confirma UI de saldo origem
    expect(screen.getByText(/Disponível: 10.000/)).toBeInTheDocument();
  });

  it('pede confirmação antes de desvincular e atualiza resumo', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue({
      ...resumoBase,
      total_alocado: '4.000',
      saldo_entrada: '6.000',
      estado_operacional: 'PARCIAL',
      alocacoes: [
        {
          id: 7,
          pedido_venda_item_id: 99,
          pedido_venda_id: 1,
          pedido_venda_numero: 'PV-1',
          cliente_nome: 'Cliente',
          produto_id: 1,
          produto_codigo: 'PE-1',
          produto_nome: 'Produto',
          quantidade_alocada: '4.000',
          necessidade_destino: '10.000',
          total_alocado_destino: '4.000',
          saldo_destino: '6.000',
          faturamento_id: null,
          faturamento_numero: null,
          nfe_saida_id: null,
          nfe_saida_numero: null,
          criado_em: null,
          atualizado_em: null,
        },
      ],
    });
    vi.mocked(alocacaoAtendimentoService.desvincularEntradaVenda).mockResolvedValue({
      detail: 'ok',
      resumo: { ...resumoBase, estado_operacional: 'SEM_ALOCACAO' },
    });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    await waitFor(() => expect(screen.getByText('Desvincular')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Desvincular'));
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(alocacaoAtendimentoService.desvincularEntradaVenda).toHaveBeenCalledWith(7);
    });
    confirmSpy.mockRestore();
  });

  it('edita quantidade e chama endpoint dedicado', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue({
      ...resumoBase,
      total_alocado: '4.000',
      saldo_entrada: '6.000',
      estado_operacional: 'PARCIAL',
      alocacoes: [
        {
          id: 7,
          pedido_venda_item_id: 99,
          pedido_venda_id: 1,
          pedido_venda_numero: 'PV-1',
          cliente_nome: 'Cliente',
          produto_id: 1,
          produto_codigo: 'PE-1',
          produto_nome: 'Produto',
          quantidade_alocada: '4.000',
          necessidade_destino: '10.000',
          total_alocado_destino: '4.000',
          saldo_destino: '6.000',
          faturamento_id: null,
          faturamento_numero: null,
          nfe_saida_id: null,
          nfe_saida_numero: null,
          criado_em: null,
          atualizado_em: null,
        },
      ],
    });
    vi.mocked(alocacaoAtendimentoService.atualizarQuantidadeEntradaVenda).mockResolvedValue({
      alocacao: { id: 7 } as never,
      resumo: {
        ...resumoBase,
        total_alocado: '5.000',
        saldo_entrada: '5.000',
        estado_operacional: 'PARCIAL',
        alocacoes: [],
      },
    });

    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    await waitFor(() => expect(screen.getByText('Editar qty')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Editar qty'));
    const input = screen.getByDisplayValue('4.000');
    fireEvent.change(input, { target: { value: '5.000' } });
    fireEvent.click(screen.getByText('Salvar'));
    await waitFor(() => {
      expect(alocacaoAtendimentoService.atualizarQuantidadeEntradaVenda).toHaveBeenCalledWith(7, '5.000');
    });
  });
});
