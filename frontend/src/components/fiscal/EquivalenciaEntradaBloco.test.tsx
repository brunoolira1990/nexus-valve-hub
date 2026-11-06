import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { EquivalenciaEntradaBloco } from '@/components/fiscal/EquivalenciaEntradaBloco';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import type { EquivalenciasConferenciaPayload } from '@/lib/conferenciaEquivalencia';
import type { NFeEntradaConferencia } from '@/types';

vi.mock('@/services/api/nfeEntradaConferencia', () => ({
  nfeEntradaConferenciaService: {
    confirmarEquivalencia: vi.fn(),
    rejeitarEquivalencia: vi.fn(),
  },
}));

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

const conferencia = { id: 20, nf_entrada_historica: 10, itens: [] } as unknown as NFeEntradaConferencia;

const equivalencias = (patch: Partial<EquivalenciasConferenciaPayload> = {}): EquivalenciasConferenciaPayload => ({
  sugestoes: [{
    tipo: 'equivalencia_composta',
    tipo_composicao: 'KIT_COMERCIAL',
    confianca: 92,
    nivel_confianca: 'alta',
    produto_interno_id: 31,
    produto_interno_codigo: 'PV-31',
    produto_interno_descricao: 'Produto interno',
    item_pedido_compra_id: 44,
    quantidade_equivalente: '2',
    valor_total_agrupado: '120.50',
    valor_pedido_referencia: '119.00',
    diferenca_valor: '1.50',
    dentro_tolerancia: true,
    itens_nfe_conferencia_ids: [501, 502],
    itens_nfe: [{ codigo_fornecedor: 'F-1', descricao: 'Componente A', quantidade: '2', valor_total: '120.50' }],
  }],
  agrupamentos: [],
  comparacao_pedido_nf: {
    valor_produtos_pedido: '119.00',
    valor_produtos_nf: '120.50',
    diferenca_produtos: '1.50',
  },
  aviso_estoque: '',
  ...patch,
});

const props = () => ({
  nfId: 10,
  equivalencias: equivalencias(),
  onResultado: vi.fn(),
  onErro: vi.fn(),
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(nfeEntradaConferenciaService.confirmarEquivalencia).mockResolvedValue({ conferencia, mensagem: 'ok' });
  vi.mocked(nfeEntradaConferenciaService.rejeitarEquivalencia).mockResolvedValue({ conferencia });
});

afterEach(cleanup);

describe('EquivalenciaEntradaBloco', () => {
  it('renderiza badge e comparação; sem sugestões usa a mensagem vazia adequada', () => {
    render(<EquivalenciaEntradaBloco {...props()} />);
    expect(screen.getByText('Equivalências e Composições')).toBeInTheDocument();
    expect(screen.getByText('1 sugestão(ões)')).toBeInTheDocument();
    expect(screen.getByText('Comparação Pedido × NF (informativa)')).toBeInTheDocument();

    cleanup();
    render(<EquivalenciaEntradaBloco {...props()} equivalencias={equivalencias({ sugestoes: [] })} />);
    expect(screen.getByText('Sem sugestões automáticas')).toBeInTheDocument();
  });

  it('confirmar usa o payload da sugestão, delega o resultado e mantém payload completo', async () => {
    const p = props();
    render(<EquivalenciaEntradaBloco {...p} />);

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar vínculo' }));

    await waitFor(() => expect(p.onResultado).toHaveBeenCalledWith(conferencia));
    expect(nfeEntradaConferenciaService.confirmarEquivalencia).toHaveBeenCalledWith(10, {
      produto_interno_id: 31,
      item_pedido_compra_id: 44,
      itens_nfe_conferencia_ids: [501, 502],
      tipo_agrupamento: 'equivalencia_composta',
      quantidade_equivalente: '2',
      confianca: 92,
      salvar_regra_fornecedor: true,
    });
  });

  it('rejeitar delega rejeitarEquivalencia e depois onResultado', async () => {
    const p = props();
    render(<EquivalenciaEntradaBloco {...p} />);

    fireEvent.click(screen.getByRole('button', { name: 'Rejeitar sugestão' }));

    await waitFor(() => expect(p.onResultado).toHaveBeenCalledWith(conferencia));
    expect(nfeEntradaConferenciaService.rejeitarEquivalencia).toHaveBeenCalledWith(10, {
      produto_interno_id: 31,
      itens_nfe_conferencia_ids: [501, 502],
    });
  });

  it('erro de confirmar chama onErro e não chama onResultado', async () => {
    vi.mocked(nfeEntradaConferenciaService.confirmarEquivalencia).mockRejectedValue(new Error('Falha de equivalência'));
    const p = props();
    render(<EquivalenciaEntradaBloco {...p} />);

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar vínculo' }));

    await waitFor(() => expect(p.onErro).toHaveBeenCalled());
    expect(p.onResultado).not.toHaveBeenCalled();
  });

  it('eqBusy desabilita ações e reseta após sucesso', async () => {
    let resolve!: (value: { conferencia: NFeEntradaConferencia; mensagem: string }) => void;
    vi.mocked(nfeEntradaConferenciaService.confirmarEquivalencia).mockReturnValue(new Promise((r) => { resolve = r; }));
    const p = props();
    render(<EquivalenciaEntradaBloco {...p} />);

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar vínculo' }));
    expect(screen.getByRole('button', { name: 'Confirmar vínculo' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Rejeitar sugestão' })).toBeDisabled();

    resolve({ conferencia, mensagem: 'ok' });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmar vínculo' })).not.toBeDisabled());
  });

  it('eqBusy reseta após erro', async () => {
    vi.mocked(nfeEntradaConferenciaService.rejeitarEquivalencia).mockRejectedValue(new Error('Falha ao rejeitar'));
    const p = props();
    render(<EquivalenciaEntradaBloco {...p} />);

    fireEvent.click(screen.getByRole('button', { name: 'Rejeitar sugestão' }));

    await waitFor(() => expect(p.onErro).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole('button', { name: 'Rejeitar sugestão' })).not.toBeDisabled());
  });

  it('renderiza agrupamentos confirmados e itens da NF', () => {
    const p = props();
    p.equivalencias = equivalencias({ agrupamentos: [{ id: 7, produto_interno_codigo: 'PV-31', status: 'CONFIRMADO' }] as never[] });
    render(<EquivalenciaEntradaBloco {...p} />);

    expect(screen.getByText('Agrupamentos confirmados')).toBeInTheDocument();
    expect(screen.getByText(/#7 · PV-31 · CONFIRMADO/)).toBeInTheDocument();
    expect(screen.getByText(/F-1 · Componente A · qtd 2/)).toBeInTheDocument();
  });
});
