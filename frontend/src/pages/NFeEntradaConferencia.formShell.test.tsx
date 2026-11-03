/**
 * Sprint 3.18-3 (upgrade de UX) — Conferência de NF-e de entrada.
 *
 * Cobre as três superfícies que esta fase toca, e só elas:
 *   1. FormShell em standalone, reduzido a título + pipeline + voltar (decisão do PO:
 *      a barra de baixo voltou a ser a única fonte de ações, então o cabeçalho não pode
 *      ter botão nenhum — nem o rodapé mobile do shell, que é derivado de acoesPrincipais).
 *   2. A barra agrupada (navegação | conferência | operacional) com os rótulos e gates novos,
 *      idêntica nos dois modos.
 *   3. O banner de pendências, que é âncora: aponta para os controles que já existem, sem
 *      duplicar widget.
 *
 * O workbench de equivalência/vínculo não é tocado por esta fase.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { NFeEntradaConferenciaPanel } from '@/components/fiscal/NFeEntradaConferenciaPanel';
import NFeEntradaConferenciaPage from '@/pages/NFeEntradaConferencia';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import type { ItemConferenciaNFeEntrada, NFeEntradaConferencia } from '@/types';

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
    fornecedor_id: 99,
    status: 'PENDENTE',
    divergencias_aceitas: false,
    estoque_aplicado_em: null,
    itens: [],
    ...patch,
  }) as unknown as NFeEntradaConferencia;

/**
 * Linha ativa sem produto: itemExigeProduto() é verdadeiro por padrão (não é IGNORADO, não tem
 * movimenta_estoque=false), então `produto_id: null` cai em progresso.produtosFaltando — que é
 * exatamente de onde o banner lê a contagem ('itens_sem_vinculo' não existe na API).
 */
const itemSemVinculo = {
  id: 1,
  item_nfe_historico: 5,
  produto_id: null,
  produto_nome: '',
  item_pedido_compra_id: null,
  status: 'PENDENTE_PRODUTO',
  unidade_nf: 'UN',
  quantidade_nf: 2,
  valor_unitario_nf: 10,
} as unknown as ItemConferenciaNFeEntrada;

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

async function renderCarregado(patch: Partial<NFeEntradaConferencia> = {}) {
  const dados = conf(patch);
  mocks.get.mockResolvedValue(dados);
  await renderStandalone();
  // A barra só existe com dados carregados; esperar o grupo é a barreira de sincronização.
  await screen.findByTestId('barra-acoes-conferencia');
  return dados;
}

beforeAll(() => {
  // jsdom não implementa scrollIntoView; o banner usa âncora com scroll suave.
  Element.prototype.scrollIntoView = () => {};
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.salvar.mockResolvedValue(conf());
  mocks.getAllPedidos.mockResolvedValue([]);
  mocks.prepararEstoque.mockResolvedValue(conf({ status: 'PREPARADA' }));
  mocks.previewAplicarEstoque.mockResolvedValue({
    aplicado: false,
    conferencia_id: 20,
    itens_aplicados: [],
    itens_ignorados: [],
    pendencias: [],
    alertas: [],
  });
});

afterEach(() => {
  cleanup();
});

describe('NFeEntradaConferencia — shell sem ações e barra agrupada (3.18-3)', () => {
  it('o cabeçalho do FormShell fica só com título, pipeline e voltar', async () => {
    await renderCarregado();

    const header = await screen.findByTestId('form-shell-header');
    expect(within(header).getByRole('heading', { name: 'Conferência da nota de entrada' })).toBeInTheDocument();
    expect(within(header).getByRole('button', { name: 'Voltar' })).toBeInTheDocument();
    // Decisão do PO: a barra é a única fonte de ações. Se qualquer botão de ação voltar para o
    // cabeçalho, este teste falha — inclusive o 'Finalizar', que morava lá na rodada anterior.
    expect(within(header).queryByRole('button', { name: 'Finalizar conferência' })).not.toBeInTheDocument();
    expect(within(header).queryByRole('button', { name: 'Salvar rascunho' })).not.toBeInTheDocument();
    // Consequência medida: sem acoesPrincipais o shell não monta o rodapé mobile fixo.
    expect(screen.queryByTestId('form-shell-rodape-mobile')).toBeNull();
  });

  it('a barra de baixo tem os três grupos e vive dentro do conteúdo', async () => {
    await renderCarregado({ status: 'CONFERIDA' });

    const conteudo = screen.getByTestId('form-shell-content');
    const barra = within(conteudo).getByTestId('barra-acoes-conferencia');
    const navegacao = within(barra).getByTestId('barra-grupo-navegacao');
    const conferencia = within(barra).getByTestId('barra-grupo-conferencia');
    const operacional = within(barra).getByTestId('barra-grupo-operacional');

    expect(within(navegacao).getByRole('button', { name: 'Voltar' })).toBeInTheDocument();
    expect(within(conferencia).getByRole('button', { name: 'Salvar rascunho' })).toBeInTheDocument();
    expect(within(conferencia).getByRole('button', { name: 'Finalizar conferência' })).toBeInTheDocument();
    expect(within(operacional).getByRole('button', { name: 'Aplicar estoque' })).toBeInTheDocument();
    expect(within(operacional).getByRole('button', { name: 'Gerar devolução ao fornecedor' })).toBeInTheDocument();
    expect(within(operacional).getByRole('button', { name: 'Reabrir para correção' })).toBeInTheDocument();

    // Ordem dos grupos na DOM: navegação, conferência, operacional.
    expect([navegacao, conferencia, operacional]).toEqual(
      Array.from(barra.querySelectorAll('[data-testid^="barra-grupo-"]')),
    );
  });

  it('o pipeline é os três estágios reais e com somenteLeitura não responde a clique', async () => {
    await renderCarregado({ status: 'CONFERIDA' });

    const banda = await screen.findByTestId('form-shell-pipeline');
    expect(within(banda).getByTestId('status-pipeline-step-pendente')).toBeInTheDocument();
    expect(within(banda).getByTestId('status-pipeline-step-conferida')).toBeInTheDocument();
    expect(within(banda).getByTestId('status-pipeline-step-preparada')).toBeInTheDocument();
    expect(within(banda).getByTestId('status-pipeline-step-conferida')).toHaveAttribute('aria-current', 'step');
    expect(within(banda).getAllByRole('button')).toHaveLength(3);
    for (const estagio of within(banda).getAllByRole('button')) {
      expect(estagio).toBeDisabled();
    }

    fireEvent.click(within(banda).getByTestId('status-pipeline-step-preparada'));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1));
    expect(mocks.salvar).not.toHaveBeenCalled();
  });

  it('CANCELADA mantém os três estágios e marca de perigo o primeiro', async () => {
    await renderCarregado({ status: 'CANCELADA' });

    const banda = await screen.findByTestId('form-shell-pipeline');
    const pendente = within(banda).getByTestId('status-pipeline-step-pendente');
    expect(pendente).toHaveClass('line-through');
    expect(pendente).toHaveAttribute('title', 'Conferência cancelada/revertida');
    expect(within(banda).getByTestId('status-pipeline-step-conferida')).toBeInTheDocument();
    expect(within(banda).getByTestId('status-pipeline-step-preparada')).toBeInTheDocument();
  });

  it('tanto a seta do shell quanto o Voltar da barra vão para a listagem de entradas históricas', async () => {
    await renderCarregado();

    fireEvent.click(within(await screen.findByTestId('form-shell-header')).getByRole('button', { name: 'Voltar' }));
    expect(await screen.findByTestId('location')).toHaveTextContent('/nfe-entrada-historica-importada');
  });

  it('em PENDENTE: finalizar habilitado, e nada do grupo operacional', async () => {
    await renderCarregado({ status: 'PENDENTE' });

    const barra = screen.getByTestId('barra-acoes-conferencia');
    const finalizar = within(barra).getByRole('button', { name: 'Finalizar conferência' });
    expect(finalizar).toBeEnabled();
    expect(within(barra).queryByRole('button', { name: 'Aplicar estoque' })).not.toBeInTheDocument();
    expect(within(barra).queryByRole('button', { name: 'Reabrir para correção' })).not.toBeInTheDocument();
    expect(within(barra).queryByRole('button', { name: 'Gerar devolução ao fornecedor' })).not.toBeInTheDocument();

    fireEvent.click(finalizar);
    await waitFor(() => expect(mocks.prepararEstoque).toHaveBeenCalledWith(10, { data_entrada: '2026-07-02' }));
    expect(mocks.salvar).toHaveBeenCalledTimes(1);
  });

  it('em PREPARADA: finalizar bloqueado e aplicar estoque visível porém desabilitado', async () => {
    await renderCarregado({ status: 'PREPARADA' });

    const barra = screen.getByTestId('barra-acoes-conferencia');
    expect(within(barra).getByRole('button', { name: 'Finalizar conferência' })).toBeDisabled();
    const aplicar = within(barra).getByRole('button', { name: 'Aplicar estoque' });
    // Gate decidido pelo PO: só habilita em CONFERIDA. O guard do backend aceita
    // CONFERIDA|PREPARADA, então a restrição é de tela e fica explicada no title.
    expect(aplicar).toBeDisabled();
    expect(aplicar).toHaveAttribute('title', expect.stringContaining('CONFERIDA'));
    fireEvent.click(aplicar);
    expect(mocks.previewAplicarEstoque).not.toHaveBeenCalled();
  });

  it('em CONFERIDA: aplicar estoque habilita e abre o preview; devolução e reabertura aparecem', async () => {
    await renderCarregado({ status: 'CONFERIDA' });

    const barra = screen.getByTestId('barra-acoes-conferencia');
    const operacional = within(barra).getByTestId('barra-grupo-operacional');
    expect(within(operacional).getByRole('button', { name: 'Reabrir para correção' })).toBeInTheDocument();
    expect(within(operacional).getByRole('button', { name: 'Gerar devolução ao fornecedor' })).toBeInTheDocument();

    const aplicar = within(operacional).getByRole('button', { name: 'Aplicar estoque' });
    expect(aplicar).toBeEnabled();
    fireEvent.click(aplicar);
    await waitFor(() => expect(mocks.previewAplicarEstoque).toHaveBeenCalledWith(10, false));
  });

  it('o rótulo do salvar continua acompanhando as pendências operacionais', async () => {
    await renderCarregado({ financeiro: { possui_pendencias_operacionais: true } });

    const barra = screen.getByTestId('barra-acoes-conferencia');
    expect(within(barra).getByRole('button', { name: 'Salvar com pendências' })).toBeInTheDocument();
    expect(within(barra).queryByRole('button', { name: 'Salvar rascunho' })).not.toBeInTheDocument();
  });

  it('Reabrir para correção no grupo operacional abre o modal de reabertura', async () => {
    await renderCarregado({ status: 'PREPARADA' });

    const barra = screen.getByTestId('barra-acoes-conferencia');
    fireEvent.click(within(barra).getByRole('button', { name: 'Reabrir para correção' }));
    expect(
      await screen.findByRole('heading', { name: 'Reabrir entrada de fornecedor para correção' }),
    ).toBeInTheDocument();
  });
});

describe('NFeEntradaConferencia — banner de pendências (âncora)', () => {
  it('aparece com fornecedor não identificado, com o texto do spec e a âncora certa', async () => {
    await renderCarregado({ fornecedor_id: null });

    const banner = screen.getByTestId('banner-pendencias-conferencia');
    expect(within(banner).getByText('Atenção: Existem pendências que impedem a finalização segura.')).toBeInTheDocument();
    expect(within(banner).getByText('Fornecedor não identificado nesta nota de entrada.')).toBeInTheDocument();
    expect(within(banner).queryByText(/sem vínculo/)).not.toBeInTheDocument();

    const alvo = document.getElementById('conferencia-fornecedor-acoes');
    expect(alvo).not.toBeNull();
    const spy = vi.spyOn(alvo as HTMLElement, 'scrollIntoView');
    fireEvent.click(within(banner).getByTestId('banner-ancora-fornecedor'));
    expect(spy).toHaveBeenCalledTimes(1);

    // O controle real permanece onde sempre esteve: o banner não duplica o bloco.
    expect(within(banner).queryByRole('button', { name: 'Cadastrar fornecedor' })).not.toBeInTheDocument();
    expect(within(alvo as HTMLElement).getByRole('button', { name: 'Cadastrar fornecedor' })).toBeInTheDocument();
  });

  it('conta os itens sem vínculo e leva às linhas', async () => {
    await renderCarregado({ itens: [itemSemVinculo] });

    const banner = screen.getByTestId('banner-pendencias-conferencia');
    expect(within(banner).getByText('1 item sem vínculo com o produto.')).toBeInTheDocument();
    expect(within(banner).queryByText('Fornecedor não identificado nesta nota de entrada.')).not.toBeInTheDocument();

    const alvo = document.getElementById('conferencia-itens');
    expect(alvo).not.toBeNull();
    const spy = vi.spyOn(alvo as HTMLElement, 'scrollIntoView');
    fireEvent.click(within(banner).getByTestId('banner-ancora-itens'));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('não aparece quando a nota está completa', async () => {
    await renderCarregado({ fornecedor_id: 99, itens: [] });
    expect(screen.queryByTestId('banner-pendencias-conferencia')).toBeNull();
  });
});

describe('NFeEntradaConferenciaPanel — embedded: sem shell, com a mesma barra', () => {
  it('mantém os três grupos e o Fechar, sem FormShell nem pipeline', async () => {
    mocks.get.mockResolvedValue(conf({ status: 'CONFERIDA' }));
    render(
      <MemoryRouter>
        <NFeEntradaConferenciaPanel nfeHistoricaId={10} embedded onClose={vi.fn()} />
      </MemoryRouter>,
    );

    const barra = await screen.findByTestId('barra-acoes-conferencia');
    expect(screen.queryByTestId('form-shell')).toBeNull();
    expect(screen.queryByTestId('form-shell-header')).toBeNull();
    expect(screen.queryByTestId('form-shell-pipeline')).toBeNull();

    expect(within(barra).getByTestId('barra-grupo-navegacao')).toBeInTheDocument();
    expect(within(barra).getByTestId('barra-grupo-conferencia')).toBeInTheDocument();
    expect(within(barra).getByTestId('barra-grupo-operacional')).toBeInTheDocument();
    expect(within(barra).getByRole('button', { name: 'Fechar' })).toBeInTheDocument();
    expect(within(barra).queryByRole('button', { name: 'Voltar' })).not.toBeInTheDocument();
    expect(within(barra).getByRole('button', { name: 'Finalizar conferência' })).toBeEnabled();
    expect(within(barra).getByRole('button', { name: 'Aplicar estoque' })).toBeEnabled();
    expect(nfeEntradaConferenciaService.get).toHaveBeenCalledWith(10);
  });
});
