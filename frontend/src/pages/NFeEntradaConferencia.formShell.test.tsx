/**
 * Sprint 3.18-3 — Conferência de NF-e de entrada no padrão Odoo.
 *
 * Este arquivo cobre só o shell e só o modo standalone (a rota
 * /nfe-entrada/:id/conferencia): FormShell no lugar do PageHeader, pipeline de
 * leitura da máquina PENDENTE → CONFERIDA → PREPARADA e as ações do cabeçalho
 * apontando para os mesmos handlers da barra de baixo. O modo embedded (Central
 * DF-e) é coberto aqui porque a decisão do PO é justamente não ter shell nele.
 *
 * O workbench de equivalência/vínculo continua intocado — ele pertence aos
 * testes próprios da conferência (nfeEntradaReaberturaAcoes.test.tsx e afins).
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NFeEntradaConferenciaPanel } from '@/components/fiscal/NFeEntradaConferenciaPanel';
import NFeEntradaConferenciaPage from '@/pages/NFeEntradaConferencia';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import type { NFeEntradaConferencia, ResultadoAplicacaoEstoque } from '@/types';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  salvar: vi.fn(),
  prepararEstoque: vi.fn(),
  previewAplicarEstoque: vi.fn(),
  aplicarEstoque: vi.fn(),
  getAllPedidos: vi.fn(),
}));

vi.mock('@/services/api/nfeEntradaConferencia', () => ({
  nfeEntradaConferenciaService: {
    get: mocks.get,
    salvar: mocks.salvar,
    prepararEstoque: mocks.prepararEstoque,
    previewAplicarEstoque: mocks.previewAplicarEstoque,
    aplicarEstoque: mocks.aplicarEstoque,
    vincularFornecedor: vi.fn(),
    cadastrarVincularFornecedor: vi.fn(),
    confirmarEquivalencia: vi.fn(),
    rejeitarEquivalencia: vi.fn(),
    previewReabertura: vi.fn().mockResolvedValue(null),
    reabrir: vi.fn(),
  },
}));

vi.mock('@/services/api/comercial', () => ({
  pedidosCompraService: { getAll: mocks.getAllPedidos },
}));

vi.mock('@/services/api/produtos', () => ({
  produtosService: {
    search: vi.fn().mockResolvedValue([]),
    getById: vi.fn(),
  },
}));

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="location">{location.pathname}</p>;
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
    fornecedor_cnpj: '00000000000191',
    status: 'PENDENTE',
    divergencias_aceitas: false,
    estoque_aplicado_em: null,
    itens: [],
    ...patch,
  }) as unknown as NFeEntradaConferencia;

/** Preview vazio: 'Aplicar estoque' abre o modal, e o modal lê esses arrays no render. */
const previewAplicar = (): ResultadoAplicacaoEstoque =>
  ({
    aplicado: false,
    conferencia_id: 20,
    itens_aplicados: [],
    itens_ignorados: [],
    pendencias: [],
    alertas: [],
  }) as unknown as ResultadoAplicacaoEstoque;

/** Rota real da página: é por ela que o modo standalone existe em produção. */
function renderStandalone(inicialEntries = ['/nfe-entrada/10/conferencia']) {
  render(
    <MemoryRouter initialEntries={inicialEntries}>
      <Routes>
        <Route path="/nfe-entrada/:id/conferencia" element={<NFeEntradaConferenciaPage />} />
        <Route path="/nfe-entrada-historica-importada" element={<LocationProbe />} />
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
  return screen.findByTestId('form-shell');
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.get.mockResolvedValue(conf());
  mocks.getAllPedidos.mockResolvedValue([]);
  mocks.salvar.mockResolvedValue(conf());
  mocks.prepararEstoque.mockResolvedValue(conf({ status: 'PREPARADA' }));
  mocks.previewAplicarEstoque.mockResolvedValue(previewAplicar());
  mocks.aplicarEstoque.mockResolvedValue({ ...previewAplicar(), conferencia: conf({ status: 'PREPARADA' }) });
});

afterEach(() => {
  cleanup();
});

describe('NFeEntradaConferencia — FormShell standalone (Sprint 3.18-3)', () => {
  it('troca o PageHeader pelo FormShell com o título da conferência', async () => {
    await renderStandalone();

    const header = await screen.findByTestId('form-shell-header');
    expect(within(header).getByRole('heading', { name: 'Conferência da nota de entrada' })).toBeInTheDocument();
    expect(screen.getByTestId('form-shell-content')).toBeInTheDocument();
    // A barra de ações de baixo não é renderizada em standalone: as mesmas ações vivem
    // no cabeçalho. Provar pelo conteúdo (não pelo `screen`) é o que separa as duas coisas.
    const conteudo = screen.getByTestId('form-shell-content');
    expect(within(conteudo).queryByRole('button', { name: 'Finalizar' })).not.toBeInTheDocument();
    expect(within(conteudo).queryByRole('button', { name: 'Salvar' })).not.toBeInTheDocument();
  });

  it('o pipeline mostra os três estágios da conferência e marca o atual', async () => {
    mocks.get.mockResolvedValue(conf({ status: 'CONFERIDA' }));
    await renderStandalone();

    const banda = await screen.findByTestId('form-shell-pipeline');
    expect(within(banda).getByTestId('status-pipeline-step-pendente')).toBeInTheDocument();
    expect(within(banda).getByTestId('status-pipeline-step-conferida')).toBeInTheDocument();
    expect(within(banda).getByTestId('status-pipeline-step-preparada')).toBeInTheDocument();
    expect(within(banda).getByTestId('status-pipeline-step-conferida')).toHaveAttribute('aria-current', 'step');
    expect(within(banda).getByTestId('status-pipeline-atual')).toBeInTheDocument();
  });

  it('sem onChange o rail é exibição: nenhum estágio é clicável e clicar não recarrega nada', async () => {
    await renderStandalone();

    const banda = await screen.findByTestId('form-shell-pipeline');
    // Decisão do PO: `pipeline={{ steps }}` sem a chave `somenteLeitura` e sem `onChange`.
    // Quem decide a interatividade é o StatusPipeline (`!somenteLeitura && Boolean(onChange)`),
    // então a ausência do onChange já é o rail de leitura — o que importa aqui é que as
    // transições reais continuam passando pelos endpoints do domínio, não pelo clique.
    expect(within(banda).getByTestId('status-pipeline-step-pendente')).toBeDisabled();
    expect(within(banda).getByTestId('status-pipeline-step-conferida')).toBeDisabled();
    expect(within(banda).getByTestId('status-pipeline-step-preparada')).toBeDisabled();

    fireEvent.click(within(banda).getByTestId('status-pipeline-step-preparada'));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1));
    expect(mocks.salvar).not.toHaveBeenCalled();
    expect(mocks.prepararEstoque).not.toHaveBeenCalled();
  });

  it('CANCELADA pinta de perigo o primeiro estágio sem perder os demais', async () => {
    mocks.get.mockResolvedValue(conf({ status: 'CANCELADA' }));
    await renderStandalone();

    const banda = await screen.findByTestId('form-shell-pipeline');
    const pendente = within(banda).getByTestId('status-pipeline-step-pendente');
    expect(pendente).toHaveClass('line-through');
    expect(pendente).toHaveAttribute('title', 'Conferência cancelada/revertida');
    expect(within(banda).getByTestId('status-pipeline-step-conferida')).toBeInTheDocument();
    expect(within(banda).getByTestId('status-pipeline-step-preparada')).toBeInTheDocument();
  });

  it('o Voltar do shell leva à listagem de entradas históricas (rota atual preservada)', async () => {
    await renderStandalone();

    const header = await screen.findByTestId('form-shell-header');
    fireEvent.click(within(header).getByRole('button', { name: 'Voltar' }));
    expect(await screen.findByTestId('location')).toHaveTextContent('/nfe-entrada-historica-importada');
  });

  it('Finalizar no cabeçalho dispara exatamente o preparar() da barra', async () => {
    await renderStandalone();

    const header = await screen.findByTestId('form-shell-header');
    fireEvent.click(within(header).getByRole('button', { name: 'Finalizar' }));

    await waitFor(() => expect(mocks.prepararEstoque).toHaveBeenCalledWith(10, { data_entrada: '2026-07-02' }));
    expect(mocks.salvar).toHaveBeenCalledTimes(1);
  });

  it('as ações condicionalmente ausentes: sem Aplicar estoque nem devolução em PENDENTE', async () => {
    await renderStandalone();

    const header = await screen.findByTestId('form-shell-header');
    expect(within(header).getByRole('button', { name: 'Finalizar' })).toBeInTheDocument();
    expect(within(header).getByRole('button', { name: 'Salvar' })).toBeInTheDocument();
    expect(within(header).queryByRole('button', { name: 'Aplicar estoque' })).not.toBeInTheDocument();
    expect(within(header).queryByRole('button', { name: 'Gerar devolução ao fornecedor' })).not.toBeInTheDocument();
  });

  it('em CONFERIDA entram Aplicar estoque e devolução; Aplicar abre o preview', async () => {
    const conferida = conf({ status: 'CONFERIDA' });
    mocks.get.mockResolvedValue(conferida);
    // O salvar() silencioso do 'Aplicar estoque' devolve a mesma conferência. Sem isso o
    // estado voltaria a PENDENTE no meio do teste e a ação condicional sumiria do cabeçalho.
    mocks.salvar.mockResolvedValue(conferida);
    await renderStandalone();

    const header = await screen.findByTestId('form-shell-header');
    expect(within(header).getByRole('button', { name: 'Gerar devolução ao fornecedor' })).toBeInTheDocument();
    expect(within(header).getByRole('button', { name: 'Aplicar estoque' })).toBeInTheDocument();

    fireEvent.click(within(header).getByRole('button', { name: 'Aplicar estoque' }));
    await waitFor(() => expect(mocks.previewAplicarEstoque).toHaveBeenCalledWith(10, false));
  });

  it('o Salvar herda o rótulo dinâmico de pendências operacionais', async () => {
    mocks.get.mockResolvedValue(
      conf({ financeiro: { possui_pendencias_operacionais: true } } as Partial<NFeEntradaConferencia>),
    );
    await renderStandalone();

    const header = await screen.findByTestId('form-shell-header');
    expect(within(header).getByRole('button', { name: 'Salvar com pendências' })).toBeInTheDocument();
  });

  it('Reabrir para correção está no cabeçalho e abre o modal de reabertura', async () => {
    await renderStandalone();

    const header = await screen.findByTestId('form-shell-header');
    fireEvent.click(within(header).getByRole('button', { name: 'Reabrir para correção' }));
    expect(
      await screen.findByRole('heading', { name: 'Reabrir entrada de fornecedor para correção' }),
    ).toBeInTheDocument();
  });
});

describe('NFeEntradaConferenciaPanel — modo embedded continua sem shell', () => {
  it('sem FormShell e sem pipeline, mas com a barra de ações de sempre', async () => {
    mocks.get.mockResolvedValue(conf({ status: 'PREPARADA' }));
    render(
      <MemoryRouter>
        <NFeEntradaConferenciaPanel nfeHistoricaId={10} embedded onClose={vi.fn()} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: 'Finalizar' })).toBeInTheDocument();
    expect(screen.queryByTestId('form-shell')).toBeNull();
    expect(screen.queryByTestId('form-shell-header')).toBeNull();
    expect(screen.queryByTestId('form-shell-pipeline')).toBeNull();

    // A barra preservada é a única fonte de ações aqui: um botão de cada, incluindo os
    // condicionais que só existem no embedded (Fechar) e os que a decisão do PO manteve.
    expect(screen.getAllByRole('button', { name: 'Finalizar' })).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Fechar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aplicar estoque' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reabrir para correção' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Gerar devolução ao fornecedor' })).toBeInTheDocument();
    expect(nfeEntradaConferenciaService.get).toHaveBeenCalledWith(10);
  });
});
