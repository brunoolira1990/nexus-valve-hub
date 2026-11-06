import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { createRef } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  EstoqueEntradaBloco,
  type EstoqueEntradaBlocoHandle,
} from '@/components/fiscal/EstoqueEntradaBloco';
import { NFeEntradaConferenciaPanel } from '@/components/fiscal/NFeEntradaConferenciaPanel';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import { auditoriaService } from '@/services/api/auditoria';
import type { NFeEntradaConferencia, ResultadoAplicacaoEstoque } from '@/types';

/**
 * PR 9 da Fase 2 — extração do bloco de ESTOQUE do NFeEntradaConferenciaPanel.
 *
 * Diferente dos PRs 6/7/8b, aqui NÃO havia modal autocontido para enrolar: o "Aplicar estoque
 * físico" era JSX inline do painel e os dois fetches viviam nos handlers do painel. O wrapper
 * é dono dos 5 estados locais e dos fetches (são chamadas de service, não de store); tudo que
 * muta estado compartilhado sai por callback. Estes casos cobrem exatamente essa fronteira:
 *
 *  - o wrapper nunca chama `acoes.*`: nos casos de wrapper os callbacks são `vi.fn()` e a
 *    única rede permitida é preview/aplicar;
 *  - `setDados` / `hydrateProdutoCache` / `load` / `notifyUpdated` rodam no PAINEL (últimos
 *    dois casos, renderizando o painel real).
 */

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }));
vi.mock('sonner', () => ({ toast }));

const api = vi.hoisted(() => ({
  get: vi.fn(),
  salvar: vi.fn(),
  prepararEstoque: vi.fn(),
  previewAplicarEstoque: vi.fn(),
  aplicarEstoque: vi.fn(),
  getAllPedidos: vi.fn(),
}));

vi.mock('@/services/api/nfeEntradaConferencia', () => ({
  nfeEntradaConferenciaService: {
    get: api.get,
    salvar: api.salvar,
    prepararEstoque: api.prepararEstoque,
    previewAplicarEstoque: api.previewAplicarEstoque,
    aplicarEstoque: api.aplicarEstoque,
    vincularFornecedor: vi.fn(),
    cadastrarVincularFornecedor: vi.fn(),
    confirmarEquivalencia: vi.fn(),
    rejeitarEquivalencia: vi.fn(),
    previewReabertura: vi.fn().mockResolvedValue(null),
    reabrir: vi.fn(),
  },
}));

vi.mock('@/services/api/comercial', () => ({ pedidosCompraService: { getAll: api.getAllPedidos } }));
vi.mock('@/services/api/produtos', () => ({
  produtosService: { search: vi.fn().mockResolvedValue([]), getById: vi.fn() },
}));
vi.mock('@/services/api/auditoria', () => ({
  auditoriaService: { historicoObjeto: vi.fn(), capacidade: vi.fn().mockResolvedValue({ pode_visualizar: true }) },
}));

const preview = (patch: Partial<ResultadoAplicacaoEstoque> = {}): ResultadoAplicacaoEstoque =>
  ({
    aplicado: false,
    conferencia_id: 20,
    itens_aplicados: [{ item_conferencia_id: 5, produto_id: 3, corrida: 'C1', quantidade: '4' }],
    itens_ignorados: [],
    pendencias: [],
    alertas: [],
    ...patch,
  }) as unknown as ResultadoAplicacaoEstoque;

const wrapperProps = (patch: Partial<React.ComponentProps<typeof EstoqueEntradaBloco>> = {}) => ({
  nfId: 10,
  busy: false,
  dataEntrada: '2026-07-02',
  onBusyChange: vi.fn(),
  onValidarAbrir: vi.fn(() => true),
  onSalvarSilencioso: vi.fn(async () => undefined),
  onAplicado: vi.fn(async () => undefined),
  onConcluido: vi.fn(),
  ...patch,
});

function renderWrapper(p: ReturnType<typeof wrapperProps>) {
  const ref = createRef<EstoqueEntradaBlocoHandle>();
  render(<EstoqueEntradaBloco ref={ref} {...p} />);
  return ref;
}

async function abrirEResperarOverlay(ref: React.RefObject<EstoqueEntradaBlocoHandle>) {
  ref.current?.abrir();
  await screen.findByText('Aplicar estoque físico');
}

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
    fornecedor_id: 99,
    status: 'CONFERIDA',
    divergencias_aceitas: false,
    estoque_aplicado_em: null,
    itens: [],
    ...patch,
  }) as unknown as NFeEntradaConferencia;

beforeEach(() => {
  vi.clearAllMocks();
  api.previewAplicarEstoque.mockResolvedValue(preview());
  api.aplicarEstoque.mockResolvedValue(preview({ aplicado: true }));
  api.get.mockResolvedValue(conf());
  api.salvar.mockResolvedValue(conf());
  api.getAllPedidos.mockResolvedValue([]);
  vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
});

afterEach(cleanup);

describe('EstoqueEntradaBloco (wrapper dono do modal de aplicar estoque)', () => {
  it('não monta o overlay até abrir(); ao abrir busca o preview e ponteia o busy', async () => {
    const p = wrapperProps();
    const ref = renderWrapper(p);

    expect(screen.queryByText('Aplicar estoque físico')).toBeNull();
    expect(api.previewAplicarEstoque).not.toHaveBeenCalled();

    await abrirEResperarOverlay(ref);

    expect(p.onValidarAbrir).toHaveBeenCalledTimes(1);
    expect(api.previewAplicarEstoque).toHaveBeenCalledWith(10, false);
    expect(p.onSalvarSilencioso).toHaveBeenCalledTimes(1);
    expect(p.onBusyChange).toHaveBeenNthCalledWith(1, true);
    expect(p.onBusyChange).toHaveBeenNthCalledWith(2, false);
  });

  it('guard de data de entrada: onValidarAbrir false não abre o overlay nem chama o preview', async () => {
    const p = wrapperProps({ onValidarAbrir: vi.fn(() => false) });
    const ref = renderWrapper(p);

    ref.current?.abrir();
    await new Promise((r) => setTimeout(r, 0));

    expect(screen.queryByText('Aplicar estoque físico')).toBeNull();
    expect(api.previewAplicarEstoque).not.toHaveBeenCalled();
    expect(p.onSalvarSilencioso).not.toHaveBeenCalled();
    expect(p.onBusyChange).not.toHaveBeenCalled();
  });

  it('confirmar delega onAplicado com o resultado inteiro e depois onConcluido, com o payload exato do disco', async () => {
    const res = preview({
      aplicado: true,
      conferencia: conf({ estoque_aplicado_em: '2026-07-03T10:00:00Z' }),
      pedido_compra_baixa: { aplicado: true, mensagem: 'Pedido 4 baixado.' },
    });
    api.aplicarEstoque.mockResolvedValue(res);
    const onAplicado = vi.fn(async () => undefined);
    const onConcluido = vi.fn();
    const p = wrapperProps({ onAplicado, onConcluido });
    const ref = renderWrapper(p);

    await abrirEResperarOverlay(ref);
    fireEvent.change(screen.getByLabelText(/Observação \(opcional\)/), {
      target: { value: 'conferido no cais' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar aplicação' }));

    await waitFor(() => expect(onAplicado).toHaveBeenCalledWith(res));
    // O disco mandava aplicarEstoque com observação e data_entrada lidos de `dados`.
    expect(api.aplicarEstoque).toHaveBeenCalledWith(10, {
      confirmar_alertas: false,
      observacao: 'conferido no cais',
      data_entrada: '2026-07-02',
    });
    // A obs é estado DO WRAPPER: nunca subiu para o painel.
    expect(p.onSalvarSilencioso).toHaveBeenCalledTimes(1);
    // Toast da baixa fica no wrapper (usa só o res), na ordem do disco.
    expect(toast.success).toHaveBeenCalledWith('Pedido 4 baixado.');
    expect(onConcluido).toHaveBeenCalledTimes(1);
    expect(onConcluido.mock.invocationCallOrder[0]).toBeGreaterThan(
      onAplicado.mock.invocationCallOrder[0],
    );
    expect(screen.queryByText('Aplicar estoque físico')).toBeNull();
    expect(p.onBusyChange).toHaveBeenNthCalledWith(3, true);
    expect(p.onBusyChange).toHaveBeenNthCalledWith(4, false);
  });

  it('pendências bloqueantes desabilitam o confirmar; alertas exigem o checkbox local', async () => {
    api.previewAplicarEstoque.mockResolvedValue(
      preview({
        alertas: ['divergência de quantidade'],
        pendencias: [{ item_conferencia_id: 7, motivo: 'sem produto' }],
      }),
    );
    const p = wrapperProps();
    const ref = renderWrapper(p);
    await abrirEResperarOverlay(ref);

    const confirmar = screen.getByRole('button', { name: 'Confirmar aplicação' });
    expect(confirmar).toBeDisabled();
    // O bloco de pendências é renderizado a partir do preview, sem estado compartilhado.
    expect(screen.getByText(/Pendências bloqueantes/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByRole('checkbox')).toBeChecked();
    expect(api.aplicarEstoque).not.toHaveBeenCalled();
    expect(p.onAplicado).not.toHaveBeenCalled();
  });

  it('erro do aplicar com pendências devolve o preview pelo payload de erro, sem delegar nada', async () => {
    const corpo = preview({ pendencias: [{ item_conferencia_id: 9, motivo: 'sem lote' }], detail: '422' });
    api.aplicarEstoque.mockRejectedValue({ response: { data: corpo } });
    const p = wrapperProps();
    const ref = renderWrapper(p);
    await abrirEResperarOverlay(ref);

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar aplicação' }));

    await waitFor(() => expect(screen.getByText('422')).toBeInTheDocument());
    expect(screen.getByText(/sem lote/)).toBeInTheDocument();
    expect(p.onAplicado).not.toHaveBeenCalled();
    expect(p.onConcluido).not.toHaveBeenCalled();
    expect(p.onBusyChange).toHaveBeenNthCalledWith(2, false);
  });

  it('cancelar fecha e limpa sem aplicar nem delegar', async () => {
    const p = wrapperProps();
    const ref = renderWrapper(p);
    await abrirEResperarOverlay(ref);

    fireEvent.change(screen.getByLabelText(/Observação \(opcional\)/), { target: { value: 'rascunho' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(screen.queryByText('Aplicar estoque físico')).toBeNull();
    expect(api.aplicarEstoque).not.toHaveBeenCalled();
    expect(p.onAplicado).not.toHaveBeenCalled();
    expect(p.onConcluido).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });
});

describe('painel — as mutações de store do confirmar continuam no painel', () => {
  function renderPainel(onUpdated?: () => void) {
    render(
      <MemoryRouter initialEntries={['/nfe-entrada/10/conferencia']}>
        <Routes>
          <Route
            path="/nfe-entrada/10/conferencia"
            element={<NFeEntradaConferenciaPanel nfeHistoricaId={10} onUpdated={onUpdated} />}
          />
          <Route path="*" element={<div />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  async function abrirOverlayDoPainel() {
    await screen.findByTestId('barra-acoes-conferencia');
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar estoque' }));
    await screen.findByText('Aplicar estoque físico');
  }

  it('com conferencia no resultado: o painel aplica setDados (o rodapé passa a ler estoque_aplicado_em)', async () => {
    const onUpdated = vi.fn();
    api.aplicarEstoque.mockResolvedValue(
      preview({
        aplicado: true,
        conferencia: conf({ estoque_aplicado_em: '2026-07-03T10:00:00Z' }),
      }),
    );
    renderPainel(onUpdated);
    await abrirOverlayDoPainel();
    // O salvar silencioso do painel roda antes do preview (gatilho → onSalvarSilencioso).
    expect(api.salvar).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar aplicação' }));

    // setDados veio do resultado: o texto "Estoque aplicado em …" é lido de estado.dados.
    await waitFor(() => expect(screen.getByText(/Estoque aplicado em/)).toBeInTheDocument());
    expect(onUpdated).toHaveBeenCalledTimes(1);
    // Sem `conferencia` ausente, o caminho é setDados — não load: o get não foi re-chamado.
    expect(api.get.mock.calls.length).toBe(1);
  });

  it('sem conferencia no resultado: o painel cai em acoes.load e o wrapper não muta nada', async () => {
    const onUpdated = vi.fn();
    api.aplicarEstoque.mockResolvedValue(preview({ aplicado: true }));
    renderPainel(onUpdated);
    await abrirOverlayDoPainel();
    const antes = api.get.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar aplicação' }));

    await waitFor(() => expect(api.get.mock.calls.length).toBeGreaterThan(antes));
    expect(onUpdated).toHaveBeenCalledTimes(1);
  });
});
