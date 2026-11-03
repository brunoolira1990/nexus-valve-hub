/**
 * Cotação com fornecedor (Sprint 3.18-1): primeira tela de documento no padrão Odoo.
 *
 * Este arquivo cobre só o shell — FormShell no lugar do PageHeader, pipeline de
 * exibição e rail do Chatter — e a preservação das 6 abas. O conteúdo das abas
 * (matriz de respostas, comparativo econômico, seleção de referência) pertence ao
 * CotacoesFornecedoresFlow.test.tsx, que continua intocado nesta fase.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CotacaoFornecedorDetalhe from '@/pages/CotacaoFornecedorDetalhe';
import { chatterNotasService } from '@/services/api/chatterNotas';
import { auditoriaService } from '@/services/api/auditoria';
import { cotacoesFornecedoresService } from '@/services/api/comercial';
import type { CotacaoComparativo, CotacaoFornecedor } from '@/types';

const mocks = vi.hoisted(() => ({
  getById: vi.fn(),
  comparativo: vi.fn(),
  historico: vi.fn(),
  resposta: vi.fn(),
  selecionarReferencia: vi.fn(),
  listarNotas: vi.fn(),
  historicoObjeto: vi.fn(),
}));

vi.mock('@/services/api/comercial', () => ({
  cotacoesFornecedoresService: {
    getById: mocks.getById,
    comparativo: mocks.comparativo,
    historico: mocks.historico,
    resposta: mocks.resposta,
    selecionarReferencia: mocks.selecionarReferencia,
  },
  propostasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/chatterNotas', () => ({
  chatterNotasService: {
    listar: mocks.listarNotas,
    criar: vi.fn(),
    atualizar: vi.fn(),
    excluir: vi.fn(),
    uploadAnexo: vi.fn(),
    excluirAnexo: vi.fn(),
  },
}));

vi.mock('@/services/api/auditoria', () => ({
  auditoriaService: {
    historicoObjeto: mocks.historicoObjeto,
    capacidade: vi.fn(),
  },
}));

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="location">{location.pathname}</p>;
}

const cotacao = (patch: Partial<CotacaoFornecedor> = {}): CotacaoFornecedor => ({
  id: 7,
  numero: 'CF-20260831-0007',
  proposta_id: null,
  data: '2026-08-31',
  responsavel: 1,
  responsavel_nome: 'Bruno',
  prazo_resposta: null,
  observacao: 'Consulta técnica',
  status: 'RASCUNHO',
  criado_em: '2026-08-31T10:00:00-03:00',
  atualizado_em: '2026-08-31T11:00:00-03:00',
  itens: [],
  participantes: [],
  ...patch,
} as CotacaoFornecedor);

const comparativoVazio = (): CotacaoComparativo => ({
  cotacao_id: 7,
  numero: 'CF-20260831-0007',
  proposta_id: null,
  status: 'RASCUNHO',
  itens: [],
});

function renderDetalhe(inicialEntries = ['/cotacoes-fornecedores/7']) {
  render(
    <MemoryRouter initialEntries={inicialEntries}>
      <Routes>
        <Route path="/cotacoes-fornecedores/:id" element={<CotacaoFornecedorDetalhe />} />
        <Route path="/cotacoes-fornecedores" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
  return screen.findByTestId('form-shell');
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getById.mockResolvedValue(cotacao());
  mocks.comparativo.mockResolvedValue(comparativoVazio());
  mocks.historico.mockResolvedValue([]);
  mocks.listarNotas.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.historicoObjeto.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});

describe('CotacaoFornecedorDetalhe — FormShell (Sprint 3.18-1)', () => {
  it('troca o PageHeader pelo FormShell e mantém o número da cotação como título', async () => {
    await renderDetalhe();

    const header = await screen.findByTestId('form-shell-header');
    expect(within(header).getByRole('heading', { name: 'CF-20260831-0007' })).toBeInTheDocument();
    // O badge de status é o único do cabeçalho hoje; ele mora no `meta` do shell.
    // Em RASCUNHO o rótulo também aparece como estágio do pipeline, então a prova do
    // badge isolado está no teste do status CANCELADA abaixo.
    expect(screen.getByTestId('form-shell-content')).toBeInTheDocument();
  });

  it('o badge do meta mostra o status; os badges das abas não saíram de lá', async () => {
    mocks.getById.mockResolvedValue(cotacao({ status: 'CANCELADA' }));
    await renderDetalhe();

    const header = await screen.findByTestId('form-shell-header');
    // 'Cancelada' só existe no badge do meta — o pipeline cancelado mantém os rótulos
    // normais (Rascunho / Em cotação / Concluída) com tom de perigo.
    expect(within(header).getByText('Cancelada')).toBeInTheDocument();
  });

  it('o rail do Chatter pergunta notas e histórico no alias cotacaofornecedor', async () => {
    await renderDetalhe();

    expect(await screen.findByTestId('form-shell-rail')).toBeInTheDocument();
    expect(await screen.findByTestId('chatter-tabs')).toBeInTheDocument();
    await waitFor(() =>
      expect(chatterNotasService.listar).toHaveBeenCalledWith('cotacaofornecedor', 7, { page_size: 50 }),
    );
    // Par comercial/cotacaofornecedor é o que está em MODELOS_AUDITADOS (3.18-0).
    await waitFor(() =>
      expect(auditoriaService.historicoObjeto).toHaveBeenCalledWith('comercial', 'cotacaofornecedor', 7, {
        page_size: 50,
      }),
    );
  });

  it('o pipeline do cabeçalho é os steps de cotacaoStatusToSteps e não responde a clique', async () => {
    await renderDetalhe();

    const banda = await screen.findByTestId('form-shell-pipeline');
    expect(banda).toBeInTheDocument();
    expect(screen.getByTestId('status-pipeline-step-rascunho')).toBeInTheDocument();
    expect(screen.getByTestId('status-pipeline-step-em_cotacao')).toBeInTheDocument();
    expect(screen.getByTestId('status-pipeline-step-concluida')).toBeInTheDocument();

    // RASCUNHO é o estágio atual; os demais ficam desabilitados (somenteLeitura),
    // porque a transição real de cotação passa pelos endpoints do domínio, não pelo rail.
    expect(screen.getByTestId('status-pipeline-step-rascunho')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByTestId('status-pipeline-step-em_cotacao')).toBeDisabled();
    expect(screen.getByTestId('status-pipeline-step-concluida')).toBeDisabled();
    fireEvent.click(screen.getByTestId('status-pipeline-step-concluida'));
    expect(mocks.getById).toHaveBeenCalledTimes(1);
  });

  it('o estágio atual acompanha o status vindo da API', async () => {
    mocks.getById.mockResolvedValue(cotacao({ status: 'CONCLUIDA' }));
    await renderDetalhe();

    expect(await screen.findByTestId('status-pipeline-step-concluida')).toHaveAttribute('aria-current', 'step');
  });

  it('as ações do cabeçalho são as de hoje: Atualizar recarrega e Voltar leva à listagem', async () => {
    await renderDetalhe();

    const header = await screen.findByTestId('form-shell-header');
    expect(within(header).getByRole('button', { name: 'Voltar' })).toBeInTheDocument();

    fireEvent.click(within(header).getByRole('button', { name: 'Atualizar' }));
    await waitFor(() => expect(mocks.getById).toHaveBeenCalledTimes(2));
    expect(mocks.comparativo).toHaveBeenCalledTimes(2);
    expect(mocks.historico).toHaveBeenCalledTimes(2);

    // 'Atualizar' passa pelo `if (loading)` da página, que desmonta o shell e monta de
    // novo: o clique em Voltar reconsulta o cabeçalho atual em vez de usar a referência velha.
    const headerDepois = await screen.findByTestId('form-shell-header');
    fireEvent.click(within(headerDepois).getByRole('button', { name: 'Voltar' }));
    expect(await screen.findByTestId('location')).toHaveTextContent('/cotacoes-fornecedores');
  });

  it('as 6 abas permanecem na mesma ordem', async () => {
    await renderDetalhe();

    const conteudo = await screen.findByTestId('form-shell-content');
    // Escopo no conteúdo: o rail do Chatter tem abas próprias ('Histórico',
    // 'Notas internas', 'Atividades') que não pertencem às 6 abas do documento.
    expect(within(conteudo).getAllByRole('tab').map((tab) => tab.textContent)).toEqual([
      'Resumo',
      'Itens',
      'Fornecedores',
      'Respostas',
      'Comparativo',
      'Histórico',
    ]);
  });

  it('a aba ativa continua sendo Resumo e o card de Origem segue dentro do conteúdo', async () => {
    await renderDetalhe();

    expect(await screen.findByRole('tab', { name: 'Resumo' })).toHaveAttribute('aria-selected', 'true');
    const conteudo = screen.getByTestId('form-shell-content');
    expect(within(conteudo).getByText('Origem')).toBeInTheDocument();
    expect(within(conteudo).getByText('Manual')).toBeInTheDocument();
  });
});
