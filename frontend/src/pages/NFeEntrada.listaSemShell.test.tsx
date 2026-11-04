import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import NFeEntrada from '@/pages/NFeEntrada';
import { nfeEntradasService } from '@/services/api/fiscal';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import type { NFeEntrada as NFeEntradaTipo } from '@/types';

/**
 * Trava da decisão da Sprint 3.18-4.
 *
 * A spec pedia FormShell + StatusPipeline + rail de Chatter na rota `/nfe-entrada`. A
 * auditoria da fase mostrou que a rota é a **lista de Entrada Própria** (o `PageHeader`
 * literal é `title="Entrada Própria"`, NFeEntrada.tsx:276) e que as NF-e de fornecedor
 * importadas têm página própria (`/nfe-entrada-historica-importada`). O PO decidiu, por
 * isso, NÃO embrulhar a lista: ela permanece com `PageHeader` (que é o único lugar onde a
 * busca dela vive hoje — o `FormShell` não encaminha `searchValue`/`onSearch`), sem pipeline
 * (o contrato exige `currentKey`, e cada linha tem o próprio status) e sem rail (o `Chatter`
 * com `entityId={null}` responde "Salve o registro primeiro…", frase que não faz sentido em
 * listagem, e os `w-80` do rail sairiam de uma tabela de 9 colunas).
 *
 * Então o espelho de `CotacaoFornecedorDetalhe.formShell.test.tsx` aqui é invertido: em vez
 * de provar que o shell existe, prova que ele **não** existe e que nada da lista foi movido
 * para dentro dele. É esse teste que impede uma próxima fase de "aplicar o padrão" sem
 * reabrir a decisão.
 */

const mockReload = vi.fn();
const mockSetSearch = vi.fn();

const paginatedListBase = {
  page: 1,
  pageSize: 25,
  totalPages: 1,
  search: '',
  setSearch: mockSetSearch,
  setPage: vi.fn(),
  setPageSize: vi.fn(),
  ordering: '',
  setOrdering: vi.fn(),
  filters: {} as Record<string, string>,
  setFilter: vi.fn(),
  setFilters: vi.fn(),
  reload: mockReload,
};

/**
 * Linha real da tela: `ENTRADA_PROPRIA_IMPORTADA` + `IMPORTADA_PENDENTE_CONFERENCIA` é o
 * par que o `nfeEntradaStatusToSteps` mapeia para o estágio 'rascunho' (tooltip "Importada:
 * ainda pendente de conferência"). Serve para provar que o status continua sendo badge de
 * linha, não banda de pipeline.
 */
const entrada: NFeEntradaTipo = {
  id: 42,
  numero: '1001',
  serie: '1',
  chave_acesso: '35250612345678901234567890123456789012345678',
  fornecedor_nome: 'Empresa Nexus Ltda',
  destinatario_nome: 'Cliente ABC',
  data: '2025-06-01',
  valor_total: 1234.56,
  tipo_origem: 'ENTRADA_PROPRIA_IMPORTADA',
  tipo_origem_label: 'Entrada própria',
  status_operacional: 'IMPORTADA_PENDENTE_CONFERENCIA',
  status_operacional_label: 'Importada — pendente conferência',
  importado_em: '2025-06-02T10:30:00',
  itens: [],
} as unknown as NFeEntradaTipo;

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock('@/hooks/usePaginatedList', () => ({ usePaginatedList: vi.fn() }));

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: {
    listPaginated: vi.fn(),
    getById: vi.fn(),
    importarEntradaPropriaEmitida: vi.fn(),
    criarEntradaPropriaEmitida: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('@/components/fiscal/NFeEntradaDetalheDrawer', () => ({
  NFeEntradaDetalheDrawer: () => null,
}));

vi.mock('@/components/fiscal/NFeEntradaRevisaoDrawer', () => ({
  NFeEntradaRevisaoDrawer: () => null,
}));

function renderLista() {
  return render(
    <MemoryRouter>
      <NFeEntrada />
    </MemoryRouter>,
  );
}

/** Sonda de navegação: é assim que o "Ir para Base NF-e Entrada Importada" é provado. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-probe">{location.pathname}</div>;
}

function renderComRotas() {
  return render(
    <MemoryRouter initialEntries={['/nfe-entrada']}>
      <Routes>
        <Route path="/nfe-entrada" element={<NFeEntrada />} />
        <Route path="/nfe-entrada-historica-importada" element={<LocationProbe />} />
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(usePaginatedList).mockReturnValue({
    ...paginatedListBase,
    items: [entrada],
    count: 1,
    loading: false,
    error: null,
  } as never);
});

describe('NFeEntrada (lista de Entrada Própria) — permanece fora do FormShell (3.18-4)', () => {
  it('não renderiza shell, nem pipeline, nem rail — e mantém o título da tela', () => {
    renderLista();

    expect(screen.getByRole('heading', { name: 'Entrada Própria' })).toBeInTheDocument();
    expect(screen.queryByTestId('form-shell')).toBeNull();
    expect(screen.queryByTestId('form-shell-header')).toBeNull();
    expect(screen.queryByTestId('form-shell-content')).toBeNull();
    expect(screen.queryByTestId('status-pipeline')).toBeNull();
    expect(screen.queryByTestId('chatter')).toBeNull();
  });

  it('a busca continua sendo do cabeçalho da página (nenhum campo migrado para dentro de shell)', () => {
    renderLista();

    const busca = screen.getByPlaceholderText('Digite parte do número da NF-e de entrada.');
    expect(busca).toBeInTheDocument();
    // O formulário da lista fica intacto: o filtro por busca é o mesmo `setSearch` do hook.
    fireEvent.change(busca, { target: { value: '1001' } });
    expect(mockSetSearch).toHaveBeenCalledWith('1001');
  });

  it('as três ações de listagem seguem no cabeçalho e nenhuma vira ação principal do shell', () => {
    renderLista();

    expect(screen.getByRole('button', { name: /Ir para Base NF-e Entrada Importada/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Importar entrada própria já emitida/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Emitir entrada própria$/i })).toBeInTheDocument();

    // `acoesPrincipais` só existem dentro do FormShell; sem shell, o rodapé mobile fixo
    // (que a conferência perdeu por decisão de header) também não pode aparecer aqui.
    expect(screen.queryByTestId('form-shell-rodape-mobile')).toBeNull();
    expect(screen.queryByTestId('form-shell-acao-principal-mobile')).toBeNull();
  });

  it('"Emitir entrada própria" abre o modal de criação, sem chamar service novo', async () => {
    renderLista();

    fireEvent.click(screen.getByRole('button', { name: /^Emitir entrada própria$/i }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('heading', { name: 'Emitir entrada própria' })).toBeInTheDocument();
    expect(nfeEntradasService.criarEntradaPropriaEmitida).not.toHaveBeenCalled();
  });

  it('"Importar entrada própria já emitida" abre o modal de importação sem tocar na API', async () => {
    renderLista();

    fireEvent.click(screen.getByRole('button', { name: /Importar entrada própria já emitida/i }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('heading', { name: 'Importar entrada própria já emitida' })).toBeInTheDocument();
    expect(
      within(dialog).getByText(/XML de NF-e de entrada própria já emitida pela empresa/i),
    ).toBeInTheDocument();
    expect(nfeEntradasService.importarEntradaPropriaEmitida).not.toHaveBeenCalled();
  });

  it('a ação de navegação leva à página das NF-e importadas (as duas telas continuam separadas)', async () => {
    renderComRotas();

    fireEvent.click(screen.getByRole('button', { name: /Ir para Base NF-e Entrada Importada/i }));
    await waitFor(() =>
      expect(screen.getByTestId('location-probe')).toHaveTextContent('/nfe-entrada-historica-importada'),
    );
  });

  it('o status de cada linha segue sendo badge da tabela, não banda de status da tela', () => {
    renderLista();

    // `labelStatusOperacionalNfeEntrada` (lib/nfeEntradaOperacionalLabels.ts:12) tem mapa
    // próprio e ganha do `status_operacional_label` da API: IMPORTADA_PENDENTE_CONFERENCIA
    // aparece como 'Pendente conferência'. É o pipeline real desta tela — um badge por linha.
    expect(screen.getByText('Pendente conferência')).toBeInTheDocument();
    expect(screen.getByText(/R\$\s*1\.234,56/)).toBeInTheDocument();
    expect(screen.queryByTestId('status-pipeline')).toBeNull();
  });
});
