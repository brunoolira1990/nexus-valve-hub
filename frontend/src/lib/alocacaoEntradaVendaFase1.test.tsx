import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AlocarEntradaParaVendaBlock } from '@/components/fiscal/AlocarEntradaParaVendaBlock';
import {
  deveExibirBlocoAlocarEntradaVenda,
  deveOrientarVincularProdutoParaAlocacao,
} from '@/lib/alocarEntradaVendaVisibilidade';
import { resolverConteudoWorkspace } from '@/lib/centralDfeWorkspaceUi';
import type { CentralDfeDocumento } from '@/services/api/centralDfe';

describe('alocarEntradaVendaVisibilidade', () => {
  it('aparece com produto interno vinculado (qualquer status de conferência, exceto IGNORADO)', () => {
    expect(deveExibirBlocoAlocarEntradaVenda({ produto_id: 1, status: 'CONFERIDO' })).toBe(true);
    expect(deveExibirBlocoAlocarEntradaVenda({ produto_id: 1, status: 'PRODUTO_VINCULADO' })).toBe(true);
    expect(deveExibirBlocoAlocarEntradaVenda({ produto_id: 1, status: 'PENDENTE_PRODUTO' })).toBe(true);
  });

  it('não depende de Pedido de Compra, estoque aplicado ou quantidade (truthiness)', () => {
    expect(deveExibirBlocoAlocarEntradaVenda({ produto_id: 1, status: 'CONFERIDO' })).toBe(true);
    expect(deveExibirBlocoAlocarEntradaVenda({ produto_id: null, status: 'CONFERIDO' })).toBe(false);
    expect(deveExibirBlocoAlocarEntradaVenda({ produto_id: undefined, status: 'CONFERIDO' })).toBe(false);
  });

  it('não aparece quando item IGNORADO; orienta vincular produto quando ausente', () => {
    expect(deveExibirBlocoAlocarEntradaVenda({ produto_id: 1, status: 'IGNORADO' })).toBe(false);
    expect(deveOrientarVincularProdutoParaAlocacao({ produto_id: null, status: 'CONFERIDO' })).toBe(true);
    expect(deveOrientarVincularProdutoParaAlocacao({ produto_id: 1, status: 'CONFERIDO' })).toBe(false);
  });
});

describe('Central DFe — notas finalizadas', () => {
  const baseNfe: CentralDfeDocumento = {
    id: 10,
    tipo_documento: 'NFE_ENTRADA',
    chave_resumida: '1111…1111',
    chave_acesso: '1'.repeat(44),
    numero: '10',
    serie: '1',
    data_emissao: '2026-05-01',
    data_importacao: null,
    emitente_nome: 'Forn',
    emitente_cnpj: '11111111000111',
    uf: 'SP',
    valor_total: '100',
    status_entrada: 'PENDENTE_ENTRADA',
    status_entrada_label: 'Pendente',
    tipo_label: 'NF-e Fornecedor',
    detalhe_rota: '',
    empresa_id: 1,
    nf_entrada_historica_id: 99,
  };

  it('ESTOQUE_APLICADO/CONCLUIDO abrem resumo_final por padrão, mas forçar abre conferência', () => {
    expect(resolverConteudoWorkspace(baseNfe, 'ESTOQUE_APLICADO')).toBe('resumo_final');
    expect(resolverConteudoWorkspace(baseNfe, 'CONCLUIDO')).toBe('resumo_final');
    expect(resolverConteudoWorkspace(baseNfe, 'ESTOQUE_APLICADO', true)).toBe('conferencia_nfe');
    expect(resolverConteudoWorkspace(baseNfe, 'CONCLUIDO', true)).toBe('conferencia_nfe');
  });
});

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
  alocacoes: [],
};

vi.mock('@/services/api/alocacaoAtendimento', () => ({
  alocacaoAtendimentoService: {
    resumoEntradaVenda: vi.fn(),
    opcoesPedidosVendaItens: vi.fn().mockResolvedValue([]),
    alocarEntradaVenda: vi.fn(),
    atualizarQuantidadeEntradaVenda: vi.fn(),
    desvincularEntradaVenda: vi.fn(),
  },
}));

import { alocacaoAtendimentoService } from '@/services/api/alocacaoAtendimento';

function abrirBloco() {
  fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
}

const alocacaoItem = (over: Partial<Record<string, unknown>> = {}) => ({
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
  ...over,
});

const opcaoPv = {
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
};

const resumoComAlocacao = {
  ...resumoBase,
  total_alocado: '4.000',
  saldo_entrada: '6.000',
  estado_operacional: 'PARCIAL' as const,
  alocacoes: [alocacaoItem()],
};

describe('AlocarEntradaParaVendaBlock — lazy load e erro', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('no mount: bloco visível, sem chamada de resumo nem opções de PV', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue(resumoBase);
    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    expect(screen.getByText('Alocar para venda')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Abrir' })).toBeInTheDocument();
    expect(alocacaoAtendimentoService.resumoEntradaVenda).not.toHaveBeenCalled();
    expect(alocacaoAtendimentoService.opcoesPedidosVendaItens).not.toHaveBeenCalled();
    expect(screen.queryByPlaceholderText(/Pedido de Venda/i)).not.toBeInTheDocument();
  });

  it('ao Abrir: carrega resumo e lista PVs do mesmo produto (sem digitar código)', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue(resumoBase);
    vi.mocked(alocacaoAtendimentoService.opcoesPedidosVendaItens).mockResolvedValue([opcaoPv]);
    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    abrirBloco();
    await waitFor(() => expect(alocacaoAtendimentoService.resumoEntradaVenda).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText('Sem alocação')).toBeInTheDocument());
    expect(screen.getByPlaceholderText(/Filtrar por nº do PV ou cliente/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(alocacaoAtendimentoService.opcoesPedidosVendaItens).toHaveBeenCalledWith(
        '',
        expect.objectContaining({ produto_id: 1 }),
      ),
    );
    expect(await screen.findByText(opcaoPv.label)).toBeInTheDocument();
  });

  it('erro na API de resumo → bloco mostra erro e permanece visível', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockRejectedValue(new Error('falha resumo'));
    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    abrirBloco();
    await waitFor(() => expect(screen.getByText(/falha resumo/i)).toBeInTheDocument());
    expect(screen.getByText('Alocar para venda')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fechar' })).toBeInTheDocument();
  });

  it('criar alocação: busca PV ao digitar, salva e atualiza saldos', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue(resumoBase);
    vi.mocked(alocacaoAtendimentoService.opcoesPedidosVendaItens).mockResolvedValue([opcaoPv]);
    vi.mocked(alocacaoAtendimentoService.alocarEntradaVenda).mockResolvedValue({
      alocacao: alocacaoItem() as never,
      resumo: resumoComAlocacao,
    });

    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    abrirBloco();
    const input = await screen.findByPlaceholderText(/Filtrar por nº do PV ou cliente/i);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'PV' } });
    // Debounce de 300ms do AsyncAutocomplete
    await waitFor(() =>
      expect(alocacaoAtendimentoService.opcoesPedidosVendaItens).toHaveBeenCalled(),
    );
    fireEvent.click(await screen.findByText(opcaoPv.label));
    fireEvent.click(screen.getByText('Salvar alocação'));

    await waitFor(() => expect(alocacaoAtendimentoService.alocarEntradaVenda).toHaveBeenCalledTimes(1));
    expect(alocacaoAtendimentoService.alocarEntradaVenda).toHaveBeenCalledWith(
      expect.objectContaining({ item_conferencia_id: 10, pedido_venda_item_id: 99 }),
    );
    await waitFor(() => expect(screen.getByText('Parcial')).toBeInTheDocument());
    expect(screen.getByText(/Alocado:\s*4\.000/)).toBeInTheDocument();
    expect(screen.getByText(/qty 4\.000/)).toBeInTheDocument();
  });

  it('editar quantidade: salva e atualiza resumo', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue(resumoComAlocacao);
    vi.mocked(alocacaoAtendimentoService.atualizarQuantidadeEntradaVenda).mockResolvedValue({
      resumo: {
        ...resumoComAlocacao,
        total_alocado: '5.000',
        saldo_entrada: '5.000',
        alocacoes: [alocacaoItem({ quantidade_alocada: '5.000' })],
      },
    });

    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    abrirBloco();
    fireEvent.click(await screen.findByText('Editar qty'));
    fireEvent.change(screen.getByDisplayValue('4.000'), { target: { value: '5.000' } });
    fireEvent.click(screen.getByText('Salvar'));

    await waitFor(() =>
      expect(alocacaoAtendimentoService.atualizarQuantidadeEntradaVenda).toHaveBeenCalledWith(1, '5.000'),
    );
    await waitFor(() => expect(screen.getByText(/qty 5\.000/)).toBeInTheDocument());
    expect(screen.getByText(/Alocado:\s*5\.000/)).toBeInTheDocument();
  });

  it('desvincular: confirma, remove alocação e volta a Sem alocação', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue(resumoComAlocacao);
    vi.mocked(alocacaoAtendimentoService.desvincularEntradaVenda).mockResolvedValue({
      resumo: resumoBase,
    } as never);
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    abrirBloco();
    fireEvent.click(await screen.findByText('Desvincular'));

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => expect(alocacaoAtendimentoService.desvincularEntradaVenda).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.getByText('Sem alocação')).toBeInTheDocument());
    expect(screen.queryByText(/qty 4\.000/)).not.toBeInTheDocument();
    confirmSpy.mockRestore();
  });

  it('estoque não aplicado → aviso; estoque aplicado → sem aviso de estoque', async () => {
    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue(resumoBase);
    const { rerender } = render(<AlocarEntradaParaVendaBlock itemConferenciaId={10} produtoId={1} />);
    abrirBloco();
    await waitFor(() => expect(screen.getByText(/ainda não foi aplicado/i)).toBeInTheDocument());

    vi.mocked(alocacaoAtendimentoService.resumoEntradaVenda).mockResolvedValue({
      ...resumoBase,
      estoque_aplicado: true,
      aviso_estoque: null,
    });
    rerender(<AlocarEntradaParaVendaBlock itemConferenciaId={11} produtoId={1} />);
    expect(screen.getByRole('button', { name: 'Abrir' })).toBeInTheDocument();
    expect(screen.queryByText(/ainda não foi aplicado/i)).not.toBeInTheDocument();
    abrirBloco();
    await waitFor(() => expect(alocacaoAtendimentoService.resumoEntradaVenda).toHaveBeenCalled());
    expect(screen.queryByText(/ainda não foi aplicado/i)).not.toBeInTheDocument();
  });
});
