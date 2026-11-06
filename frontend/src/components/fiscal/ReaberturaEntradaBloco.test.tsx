import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ReaberturaEntradaBloco,
  type ReaberturaEntradaBlocoHandle,
} from '@/components/fiscal/ReaberturaEntradaBloco';
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

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }));
vi.mock('sonner', () => ({ toast }));

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

const resultado: ResultadoReaberturaEntradaFornecedor = {
  acao_realizada: true,
  entrada_ja_aberta: false,
  estado_anterior: 'PREPARADA',
  estado_atual: 'PENDENTE',
  evento_id: 1,
  mensagem: 'Entrada reaberta.',
  preview: previewElegivel,
  conferencia,
};

async function abrirEConfirmar(ref: React.RefObject<ReaberturaEntradaBlocoHandle>) {
  ref.current?.abrir();
  const confirmar = await screen.findByRole('button', { name: /Reabrir entrada para correção/i });
  fireEvent.change(await screen.findByLabelText(/Motivo da reabertura/i), {
    target: { value: 'Corrigir vínculo operacional' },
  });
  fireEvent.click(confirmar);
}

describe('ReaberturaEntradaBloco', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.previewReabertura.mockResolvedValue(previewElegivel);
    api.reabrir.mockResolvedValue(resultado);
  });

  afterEach(cleanup);

  it('não renderiza o modal até o handle abrir()', () => {
    const ref = createRef<ReaberturaEntradaBlocoHandle>();
    render(
      <ReaberturaEntradaBloco
        ref={ref}
        nfId={10}
        embedded={false}
        onConferenciaReaberta={vi.fn()}
        onNavigateConferencia={vi.fn()}
      />,
    );
    expect(screen.queryByRole('button', { name: /Reabrir entrada para correção/i })).toBeNull();
  });

  it('abre o modal pelo handle e delega sucesso, atualização e navegação quando não embeddado', async () => {
    const ref = createRef<ReaberturaEntradaBlocoHandle>();
    const onConferenciaReaberta = vi.fn();
    const onUpdated = vi.fn();
    const onNavigateConferencia = vi.fn();
    render(
      <ReaberturaEntradaBloco
        ref={ref}
        nfId={10}
        embedded={false}
        onUpdated={onUpdated}
        onConferenciaReaberta={onConferenciaReaberta}
        onNavigateConferencia={onNavigateConferencia}
      />,
    );

    await abrirEConfirmar(ref);

    await waitFor(() => {
      expect(api.reabrir).toHaveBeenCalledWith(10, 'Corrigir vínculo operacional');
      expect(onConferenciaReaberta).toHaveBeenCalledWith(expect.objectContaining({ acao_realizada: true }));
      expect(onUpdated).toHaveBeenCalledTimes(1);
      expect(onNavigateConferencia).toHaveBeenCalledTimes(1);
      expect(toast.success).toHaveBeenCalledWith('Entrada reaberta.');
    });
  });

  it('não navega quando embeddado, mas ainda delega sucesso e atualização', async () => {
    const ref = createRef<ReaberturaEntradaBlocoHandle>();
    const onConferenciaReaberta = vi.fn();
    const onUpdated = vi.fn();
    const onNavigateConferencia = vi.fn();
    render(
      <ReaberturaEntradaBloco
        ref={ref}
        nfId={10}
        embedded
        onUpdated={onUpdated}
        onConferenciaReaberta={onConferenciaReaberta}
        onNavigateConferencia={onNavigateConferencia}
      />,
    );

    await abrirEConfirmar(ref);

    await waitFor(() => {
      expect(onConferenciaReaberta).toHaveBeenCalledWith(
        expect.objectContaining({ conferencia }),
      );
      expect(onUpdated).toHaveBeenCalledTimes(1);
    });
    expect(onNavigateConferencia).not.toHaveBeenCalled();
  });
});
