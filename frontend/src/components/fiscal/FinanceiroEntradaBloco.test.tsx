import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createRef } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  FinanceiroEntradaBloco,
  type FinanceiroEntradaBlocoHandle,
} from '@/components/fiscal/FinanceiroEntradaBloco';
import { NFeEntradaConferenciaPanel } from '@/components/fiscal/NFeEntradaConferenciaPanel';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import { auditoriaService } from '@/services/api/auditoria';
import type { NFeEntradaConferencia } from '@/types';

/**
 * PR 8b da Fase 2 — extração do bloco FINANCEIRO do NFeEntradaConferenciaPanel.
 *
 * O `GerarContasPagarNfeEntradaModal` (435 l.) é um wizard de 4 passos que já existia e este
 * PR não o reescreve; ele é mockado aqui exatamente como o contrato do painel o usa:
 * `open` controla a montagem, `onGenerated(payload)` é o sucesso e o próprio modal dispara
 * `onClose()` em seguida (GerarContasPagarNfeEntradaModal.tsx:127-128). Mockar o modal — e
 * não atravessar os 4 passos — é o que mantém o teste sobre o wrapper e sobre a delegação.
 */

const modal = vi.hoisted(() => ({
  /** Payload que o botão "confirmar gerado" devolve ao onSuccess; trocado caso a caso. */
  proximoTitulo: { id: 777 } as { id: number } | null,
}));

type ModalPropsStub = {
  open: boolean;
  nfeEntradaId: number | null;
  onClose: () => void;
  onGenerated: (payload: { titulo: unknown; financeiro_gerado: boolean }) => void;
};

vi.mock('@/components/fiscal/GerarContasPagarNfeEntradaModal', () => ({
  GerarContasPagarNfeEntradaModal: (props: ModalPropsStub) => {
    if (!props.open) return null;
    return (
      <div data-testid="modal-gerar-contas-pagar">
        <button
          type="button"
          onClick={() => {
            props.onGenerated({ titulo: modal.proximoTitulo, financeiro_gerado: true });
            // O wizard real fecha sozinho depois do onSuccess; o stub preserva a ordem.
            props.onClose();
          }}
        >
          confirmar gerado
        </button>
        <button type="button" onClick={props.onClose}>
          cancelar
        </button>
      </div>
    );
  },
}));

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }));
vi.mock('sonner', () => ({ toast }));

const api = vi.hoisted(() => ({
  get: vi.fn(),
  getAllPedidos: vi.fn(),
}));

vi.mock('@/services/api/nfeEntradaConferencia', () => ({
  nfeEntradaConferenciaService: {
    get: api.get,
    salvar: vi.fn(),
    prepararEstoque: vi.fn(),
    previewAplicarEstoque: vi.fn(),
    aplicarEstoque: vi.fn(),
    vincularFornecedor: vi.fn(),
    cadastrarVincularFornecedor: vi.fn(),
    confirmarEquivalencia: vi.fn(),
    rejeitarEquivalencia: vi.fn(),
    previewReabertura: vi.fn().mockResolvedValue(null),
    reabrir: vi.fn(),
  },
}));

vi.mock('@/services/api/comercial', () => ({
  pedidosCompraService: { getAll: api.getAllPedidos },
}));

vi.mock('@/services/api/produtos', () => ({
  produtosService: { search: vi.fn().mockResolvedValue([]), getById: vi.fn() },
}));

vi.mock('@/services/api/auditoria', () => ({
  auditoriaService: {
    historicoObjeto: vi.fn(),
    capacidade: vi.fn().mockResolvedValue({ pode_visualizar: true }),
  },
}));

const conf = (patch: Partial<NFeEntradaConferencia> = {}): NFeEntradaConferencia =>
  ({
    id: 20,
    nf_entrada_historica: 10,
    numero: '123',
    serie: '1',
    data_emissao: '2026-07-01',
    data_entrada: '2026-07-02',
    valor_total: 100,
    fornecedor_nome: 'Fornecedor teste',
    fornecedor_cnpj: '00000000000191',
    fornecedor_id: 99,
    status: 'CONFERIDA',
    divergencias_aceitas: false,
    estoque_aplicado_em: null,
    // `pode_gerar_contas_pagar` é o que faz o NFeEntradaFinanceiroAcoes renderizar o botão
    // habilitado (NFeEntradaFinanceiroAcoes.tsx:60-78); sem isto o gatilho some da tela.
    financeiro: { pode_gerar_contas_pagar: true, financeiro_gerado: false },
    itens: [],
    ...patch,
  }) as unknown as NFeEntradaConferencia;

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="location">{`${location.pathname}${location.search}`}</p>;
}

function renderPainel(embedded: boolean, onUpdated?: () => void) {
  return render(
    <MemoryRouter initialEntries={['/nfe-entrada/10/conferencia']}>
      <Routes>
        <Route
          path="/nfe-entrada/10/conferencia"
          element={
            <>
              <NFeEntradaConferenciaPanel nfeHistoricaId={10} embedded={embedded} onUpdated={onUpdated} />
              <LocationProbe />
            </>
          }
        />
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  modal.proximoTitulo = { id: 777 };
  vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  api.get.mockResolvedValue(conf());
  api.getAllPedidos.mockResolvedValue([]);
});

afterEach(cleanup);

describe('FinanceiroEntradaBloco (wrapper extraído do painel)', () => {
  it('não monta o modal até o handle abrir()', async () => {
    const ref = createRef<FinanceiroEntradaBlocoHandle>();
    render(<FinanceiroEntradaBloco ref={ref} nfId={10} onGerado={vi.fn()} />);

    expect(screen.queryByTestId('modal-gerar-contas-pagar')).toBeNull();

    ref.current?.abrir();
    await screen.findByTestId('modal-gerar-contas-pagar');
  });

  it('no sucesso tosta o texto exato do painel e sobe só o tituloId para cima', async () => {
    const ref = createRef<FinanceiroEntradaBlocoHandle>();
    const onGerado = vi.fn();
    render(<FinanceiroEntradaBloco ref={ref} nfId={10} onGerado={onGerado} />);

    ref.current?.abrir();
    fireEvent.click(await screen.findByRole('button', { name: 'confirmar gerado' }));

    expect(toast.success).toHaveBeenCalledWith('Contas a pagar geradas com sucesso.');
    expect(onGerado).toHaveBeenCalledTimes(1);
    expect(onGerado).toHaveBeenCalledWith(777);
    // O fechamento vem do onClose que o próprio wizard dispara depois do onSuccess.
    expect(screen.queryByTestId('modal-gerar-contas-pagar')).toBeNull();
  });

  it('sem título gerado delega null (a condição composta do painel é quem decide)', async () => {
    const ref = createRef<FinanceiroEntradaBlocoHandle>();
    const onGerado = vi.fn();
    modal.proximoTitulo = null;
    render(<FinanceiroEntradaBloco ref={ref} nfId={10} onGerado={onGerado} />);

    ref.current?.abrir();
    fireEvent.click(await screen.findByRole('button', { name: 'confirmar gerado' }));

    expect(onGerado).toHaveBeenCalledWith(null);
    expect(toast.success).toHaveBeenCalledTimes(1);
  });

  it('cancelar não tosta nem delega', async () => {
    const ref = createRef<FinanceiroEntradaBlocoHandle>();
    const onGerado = vi.fn();
    render(<FinanceiroEntradaBloco ref={ref} nfId={10} onGerado={onGerado} />);

    ref.current?.abrir();
    fireEvent.click(await screen.findByRole('button', { name: 'cancelar' }));

    expect(onGerado).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
    expect(screen.queryByTestId('modal-gerar-contas-pagar')).toBeNull();
  });
});

describe('painel — onSuccess do financeiro resolvido com o store (condição composta)', () => {
  async function gatilhoCarregado(): Promise<number> {
    await screen.findByTestId('barra-acoes-conferencia');
    const chamadasIniciais = api.get.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: /Gerar contas a pagar/i }));
    await screen.findByTestId('modal-gerar-contas-pagar');
    return chamadasIniciais;
  }

  it('standalone com título recarrega, avisa o contêiner e navega para o título', async () => {
    const onUpdated = vi.fn();
    renderPainel(false, onUpdated);
    const antes = await gatilhoCarregado();

    fireEvent.click(screen.getByRole('button', { name: 'confirmar gerado' }));

    await waitFor(() => expect(api.get.mock.calls.length).toBeGreaterThan(antes));
    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent('/financeiro/contas-pagar?titulo=777'),
    );
    expect(onUpdated).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith('Contas a pagar geradas com sucesso.');
  });

  it('embedded recarrega e avisa, mas NÃO navega (segunda metade da condição)', async () => {
    const onUpdated = vi.fn();
    renderPainel(true, onUpdated);
    const antes = await gatilhoCarregado();

    fireEvent.click(screen.getByRole('button', { name: 'confirmar gerado' }));

    await waitFor(() => expect(api.get.mock.calls.length).toBeGreaterThan(antes));
    expect(onUpdated).toHaveBeenCalled();
    // Continua na rota da conferência: !embedded é falso.
    expect(screen.getByTestId('location')).toHaveTextContent('/nfe-entrada/10/conferencia');
  });

  it('sem título não navega, mas recarrega (primeira metade da condição)', async () => {
    modal.proximoTitulo = null;
    renderPainel(false);
    const antes = await gatilhoCarregado();

    fireEvent.click(screen.getByRole('button', { name: 'confirmar gerado' }));

    await waitFor(() => expect(api.get.mock.calls.length).toBeGreaterThan(antes));
    expect(screen.getByTestId('location')).toHaveTextContent('/nfe-entrada/10/conferencia');
  });
});
