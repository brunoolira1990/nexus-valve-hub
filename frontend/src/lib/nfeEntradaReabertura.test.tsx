import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NFeEntradaReabrirModal } from '@/components/fiscal/NFeEntradaReabrirModal';
import type {
  NFeEntradaConferencia,
  PreviewReaberturaEntradaFornecedor,
  ResultadoReaberturaEntradaFornecedor,
} from '@/types';

const api = vi.hoisted(() => ({
  previewReabertura: vi.fn(),
  reabrir: vi.fn(),
}));

vi.mock('@/services/api/nfeEntradaConferencia', () => ({
  nfeEntradaConferenciaService: api,
}));

const previewElegivel: PreviewReaberturaEntradaFornecedor = {
  pode_reabrir: true,
  estado_atual: 'PREPARADA',
  entrada_ja_aberta: false,
  impedimentos: [],
  resumo_vinculos: {
    pedido_compra_selecionado: true,
    estoque_aplicado: false,
    contas_pagar_vinculadas: 0,
    alocacoes_entrada_venda: 0,
    itens_com_produto: 2,
    splits_corrida: 1,
  },
  orientacao: 'Informe o motivo.',
  numero_nfe: '123',
  serie_nfe: '1',
  fornecedor: 'Fornecedor teste',
  nfe_entrada_historica_id: 10,
  conferencia_id: 20,
};

const conferencia = {
  id: 20,
  nf_entrada_historica: 10,
  numero: '123',
  serie: '1',
  data_emissao: '2026-07-01',
  valor_total: 100,
  fornecedor_nome: 'Fornecedor teste',
  fornecedor_cnpj: '00000000000191',
  status: 'PENDENTE',
  divergencias_aceitas: false,
  itens: [],
} satisfies NFeEntradaConferencia;

function resultado(overrides?: Partial<ResultadoReaberturaEntradaFornecedor>) {
  return {
    acao_realizada: true,
    entrada_ja_aberta: false,
    estado_anterior: 'PREPARADA',
    estado_atual: 'PENDENTE',
    evento_id: 1,
    mensagem: 'Entrada reaberta.',
    preview: previewElegivel,
    conferencia,
    ...overrides,
  } satisfies ResultadoReaberturaEntradaFornecedor;
}

describe('NFeEntradaReabrirModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.previewReabertura.mockResolvedValue(previewElegivel);
    api.reabrir.mockResolvedValue(resultado());
  });

  afterEach(cleanup);

  it('mostra escopo não fiscal, exige motivo e confirma reabertura elegível', async () => {
    const onSuccess = vi.fn();
    render(
      <NFeEntradaReabrirModal
        open
        nfeHistoricaId={10}
        onOpenChange={vi.fn()}
        onSuccess={onSuccess}
      />,
    );

    expect(
      await screen.findByText(/não cancela, não altera e não transmite eventos/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Contas a Pagar e alocações não serão revertidos/i)).toBeInTheDocument();
    expect(screen.getByText('Fornecedor teste')).toBeInTheDocument();

    const confirmar = screen.getByRole('button', { name: /Reabrir entrada para correção/i });
    expect(confirmar).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Motivo da reabertura/i), { target: { value: 'curto' } });
    expect(confirmar).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Motivo da reabertura/i), {
      target: { value: 'Corrigir vínculo operacional' },
    });
    expect(confirmar).toBeEnabled();
    fireEvent.click(confirmar);

    await waitFor(() => {
      expect(api.reabrir).toHaveBeenCalledWith(10, 'Corrigir vínculo operacional');
      expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({ acao_realizada: true }));
    });
  });

  it('exibe todos os impedimentos e mantém confirmação desabilitada', async () => {
    api.previewReabertura.mockResolvedValue({
      ...previewElegivel,
      pode_reabrir: false,
      impedimentos: [
        { codigo: 'ESTOQUE_APLICADO', mensagem: 'Esta entrada já possui estoque aplicado.' },
        { codigo: 'CONTA_PAGAR_VINCULADA', mensagem: 'Existe Conta a Pagar vinculada.' },
        { codigo: 'ALOCACAO_ENTRADA_VENDA', mensagem: 'Existem alocações para Pedidos de Venda.' },
      ],
    });

    render(
      <NFeEntradaReabrirModal open nfeHistoricaId={10} onOpenChange={vi.fn()} onSuccess={vi.fn()} />,
    );

    expect(await screen.findByText(/já possui estoque aplicado/i)).toBeInTheDocument();
    expect(screen.getByText(/Existe Conta a Pagar vinculada/i)).toBeInTheDocument();
    expect(screen.getByText(/Existem alocações para Pedidos de Venda/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Motivo da reabertura/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /Reabrir entrada para correção/i })).toBeDisabled();
  });

  it('mostra loading enquanto calcula o preview', () => {
    api.previewReabertura.mockReturnValue(new Promise(() => undefined));
    render(
      <NFeEntradaReabrirModal open nfeHistoricaId={10} onOpenChange={vi.fn()} onSuccess={vi.fn()} />,
    );
    expect(screen.getByText(/Verificando efeitos operacionais/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reabrir entrada para correção/i })).toBeDisabled();
  });

  it('mantém erro da API visível', async () => {
    api.previewReabertura.mockRejectedValue(new Error('Falha ao verificar reabertura'));
    render(
      <NFeEntradaReabrirModal open nfeHistoricaId={10} onOpenChange={vi.fn()} onSuccess={vi.fn()} />,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Falha ao verificar reabertura');
  });

  it('trata resposta idempotente como sucesso sem exigir novo evento', async () => {
    api.previewReabertura.mockResolvedValue({
      ...previewElegivel,
      estado_atual: 'PENDENTE',
      entrada_ja_aberta: true,
    });
    api.reabrir.mockResolvedValue(
      resultado({
        acao_realizada: false,
        entrada_ja_aberta: true,
        estado_anterior: 'PENDENTE',
        evento_id: null,
        mensagem: 'A entrada já está aberta para correção.',
      }),
    );
    const onSuccess = vi.fn();
    render(
      <NFeEntradaReabrirModal open nfeHistoricaId={10} onOpenChange={vi.fn()} onSuccess={onSuccess} />,
    );
    fireEvent.change(await screen.findByLabelText(/Motivo da reabertura/i), {
      target: { value: 'Conferir resposta idempotente' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Reabrir entrada para correção/i }));
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(
        expect.objectContaining({ acao_realizada: false, evento_id: null }),
      );
    });
  });
});
