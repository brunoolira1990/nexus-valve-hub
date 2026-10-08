import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CotacoesFornecedores from './CotacoesFornecedores';
import CotacaoFornecedorNova from './CotacaoFornecedorNova';
import CotacaoFornecedorDetalhe from './CotacaoFornecedorDetalhe';
import type {
  CotacaoComparativo,
  CotacaoFornecedor,
  CotacaoFornecedorRespostaItem,
  Fornecedor,
  Proposta,
} from '@/types';

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  getById: vi.fn(),
  create: vi.fn(),
  addItem: vi.fn(),
  addParticipante: vi.fn(),
  resposta: vi.fn(),
  comparativo: vi.fn(),
  historico: vi.fn(),
  selecionarReferencia: vi.fn(),
  propostasGetAll: vi.fn(),
  fornecedoresGetAll: vi.fn(),
  produtosGetAll: vi.fn(),
}));

vi.mock('@/services/api/comercial', () => ({
  cotacoesFornecedoresService: {
    list: mocks.list,
    getById: mocks.getById,
    create: mocks.create,
    addItem: mocks.addItem,
    addParticipante: mocks.addParticipante,
    resposta: mocks.resposta,
    comparativo: mocks.comparativo,
    historico: mocks.historico,
    selecionarReferencia: mocks.selecionarReferencia,
  },
  propostasService: { getAll: mocks.propostasGetAll },
}));

vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: { getAll: mocks.fornecedoresGetAll },
}));

vi.mock('@/services/api/produtos', () => ({
  produtosService: { getAll: mocks.produtosGetAll },
}));

const fornecedor = (id: number, razao_social: string): Fornecedor => ({
  id,
  razao_social,
  nome_fantasia: '',
  cnpj: `00000000000${id}`,
  ativo: true,
} as Fornecedor);

const proposta = (): Proposta => ({
  id: 42,
  numero: 'P-0042',
  cliente_nome: 'Cliente Nexus',
  data: '2026-08-20',
  validade: '2026-09-20',
  vendedor: '',
  status: 'RASCUNHO',
  condicao_pagamento_texto: '',
  dias_parcelas: [],
  quantidade_parcelas: 0,
  vencimentos_previstos: [],
  valor_total: 100,
  itens: [{
    id: 420,
    produto_nome: 'Válvula esfera flangeada',
    quantidade: 5,
    quantidade_negociada: 5,
    unidade_negociada: 'PC',
  }],
} as Proposta);

const resposta = (patch: Partial<CotacaoFornecedorRespostaItem> = {}): CotacaoFornecedorRespostaItem => ({
  id: 900,
  participante: 70,
  cotacao_item: 80,
  fornecedor_id: 1,
  fornecedor_nome: 'Fornecedor Alpha',
  preco_unitario: 90,
  preco_unitario_bruto: 100,
  desconto: 10,
  quantidade_atendida: 2,
  unidade_cotada: 'PC',
  fator_conversao: 1,
  prazo_entrega: '10 dias',
  condicao_pagamento: '',
  frete: 20,
  frete_tipo: 'FOB',
  frete_tipo_codigo: 'FOB',
  ipi_custo: 5,
  icms_st_custo: 3,
  outros_tributos_custo: 2,
  despesas_adicionais: 1,
  marca_fabricante: '',
  validade: null,
  observacao: '',
  status_item: 'RESPONDIDO',
  completude: { status: 'COMPLETA PARA CALCULO', motivos: [], tipo_frete: 'FOB' },
  calculo_custo: {
    status: 'COMPLETA PARA CALCULO',
    motivos: [],
    tipo_frete: 'FOB',
    valor_produtos: '180.00',
    custo_total_estimado: '211.00',
    custo_unitario_efetivo: '105.50',
    quantidade_normalizada: '2.00',
    frete_efetivo: '20.00',
  },
  menor_preco: true,
  melhor_custo_total: true,
  custo_incompleto: false,
  motivos_incompletude: [],
  selecionada_como_referencia: false,
  selecionada_por: null,
  selecionada_por_nome: '',
  selecionada_em: null,
  ...patch,
});

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
  itens: [{
    id: 80,
    item_proposta_id: null,
    produto_id: null,
    produto_nome: '',
    produto_snapshot: {},
    descricao_item: 'Válvula esfera flangeada',
    unidade: 'PC',
    quantidade: 2,
    observacao_tecnica: '',
    status: 'PENDENTE',
    respostas: [],
  }],
  participantes: [{
    id: 70,
    fornecedor_id: 1,
    fornecedor_nome: 'Fornecedor Alpha',
    status: 'RESPONDIDO',
    enviado_em: null,
    respondido_em: '2026-08-31T11:00:00-03:00',
    observacao: '',
    respostas: [],
  }],
  ...patch,
});

const comparativo = (row = resposta()): CotacaoComparativo => ({
  cotacao_id: 7,
  numero: 'CF-20260831-0007',
  proposta_id: null,
  status: 'RASCUNHO',
  itens: [{
    cotacao_item_id: 80,
    item_proposta_id: null,
    produto_id: null,
    descricao: 'Válvula esfera flangeada',
    unidade: 'PC',
    quantidade: 2,
    respostas: [row],
  }],
});

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="location">{location.pathname}{location.search}</p>;
}

function activateTab(name: string) {
  const tab = screen.getByRole('tab', { name });
  fireEvent.pointerDown(tab, { button: 0, ctrlKey: false });
  fireEvent.click(tab);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([]);
  mocks.propostasGetAll.mockResolvedValue([]);
  mocks.fornecedoresGetAll.mockResolvedValue([
    fornecedor(1, 'Fornecedor Alpha'),
    fornecedor(2, 'Fornecedor Beta'),
  ]);
  mocks.produtosGetAll.mockResolvedValue([]);
  mocks.create.mockResolvedValue(cotacao());
  mocks.addItem.mockResolvedValue({});
  mocks.addParticipante.mockResolvedValue({});
  mocks.selecionarReferencia.mockResolvedValue({});
});

describe('home de Cotações com Fornecedores', () => {
  it('mantém a listagem vazia e só abre Nova cotação pela ação explícita', async () => {
    render(
      <MemoryRouter initialEntries={['/cotacoes-fornecedores']}>
        <Routes>
          <Route path="/cotacoes-fornecedores" element={<CotacoesFornecedores />} />
          <Route path="/cotacoes-fornecedores/nova" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Nenhuma cotação criada ainda.')).toBeInTheDocument();
    expect(screen.queryByText('Origem da cotação')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Criar primeira cotação' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/cotacoes-fornecedores/nova');
  });

  it('lista várias origens e status, filtra no frontend e abre o detalhe', async () => {
    const manual = cotacao();
    const vinculada = cotacao({
      id: 8,
      numero: 'CF-20260831-0008',
      proposta_id: 42,
      responsavel_nome: 'Ana',
      status: 'CONCLUIDA',
    });
    mocks.list.mockResolvedValue([manual, vinculada]);
    mocks.propostasGetAll.mockResolvedValue([proposta()]);

    render(
      <MemoryRouter initialEntries={['/cotacoes-fornecedores']}>
        <Routes>
          <Route path="/cotacoes-fornecedores" element={<CotacoesFornecedores />} />
          <Route path="/cotacoes-fornecedores/:id" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    const table = await screen.findByRole('table');
    expect(within(table).getByText('CF-20260831-0007')).toBeInTheDocument();
    expect(within(table).getByText('CF-20260831-0008')).toBeInTheDocument();
    expect(within(table).getByText('Manual')).toBeInTheDocument();
    expect(within(table).getByText('Vinculada à Proposta')).toBeInTheDocument();
    expect(within(table).getByText('P-0042')).toBeInTheDocument();
    expect(within(table).getByText('Concluída')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Filtrar por origem'), { target: { value: 'MANUAL' } });
    expect(within(table).queryByText('CF-20260831-0008')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Filtrar por origem'), { target: { value: 'TODAS' } });
    fireEvent.change(screen.getByLabelText('Filtrar por status'), { target: { value: 'CONCLUIDA' } });
    expect(within(table).queryByText('CF-20260831-0007')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Filtrar por status'), { target: { value: 'TODOS' } });
    fireEvent.change(screen.getByPlaceholderText('Buscar por número, Proposta ou responsável...'), { target: { value: 'Ana' } });
    expect(within(table).getByText('CF-20260831-0008')).toBeInTheDocument();

    fireEvent.click(within(table).getByRole('button', { name: 'Abrir' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/cotacoes-fornecedores/8');
  });
});

describe('Nova cotação', () => {
  it('cria uma cotação Manual com item, busca, seleção/remoção e resumo', async () => {
    render(
      <MemoryRouter initialEntries={['/cotacoes-fornecedores/nova']}>
        <Routes>
          <Route path="/cotacoes-fornecedores/nova" element={<CotacaoFornecedorNova />} />
          <Route path="/cotacoes-fornecedores/:id" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Origem da cotação')).toBeInTheDocument();
    expect(screen.getByText('Selecione pelo menos um item.')).toBeInTheDocument();
    expect(screen.getByText('Selecione pelo menos um fornecedor.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Buscar fornecedor'), { target: { value: 'Beta' } });
    expect(screen.getByText('Fornecedor Beta')).toBeInTheDocument();
    expect(screen.queryByText('Fornecedor Alpha')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Buscar fornecedor'), { target: { value: '' } });

    fireEvent.change(screen.getByPlaceholderText('Descreva o item que será cotado'), { target: { value: 'Válvula manual' } });
    fireEvent.change(screen.getByPlaceholderText('Ex.: PC'), { target: { value: 'PC' } });
    fireEvent.change(screen.getByPlaceholderText('0,000'), { target: { value: '3' } });

    fireEvent.click(screen.getByRole('button', { name: 'Adicionar item' }));
    expect(screen.getByText('Item 2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Remover item 2' }));
    expect(screen.queryByText('Item 2')).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/Fornecedor Alpha/));
    expect(screen.getAllByText('Fornecedor Alpha').length).toBeGreaterThan(1);
    expect(screen.getByText('Pronta para criar')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Criar cotação' }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ proposta: null, observacao: 'Cotação manual.' }));
    expect(mocks.addItem).toHaveBeenCalledWith(7, { descricao_item: 'Válvula manual', unidade: 'PC', quantidade: 3 });
    expect(mocks.addParticipante).toHaveBeenCalledWith(7, 1);
    expect(screen.getByTestId('location')).toHaveTextContent('/cotacoes-fornecedores/7');
  });

  it('abre pelo atalho contextual já vinculada e preserva o payload da Proposta', async () => {
    mocks.propostasGetAll.mockResolvedValue([proposta()]);
    render(
      <MemoryRouter initialEntries={['/cotacoes-fornecedores/nova?proposta_id=42']}>
        <Routes>
          <Route path="/cotacoes-fornecedores/nova" element={<CotacaoFornecedorNova />} />
          <Route path="/cotacoes-fornecedores/:id" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Cliente Nexus')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Vinculada à Proposta/ })).toBeChecked();
    expect(screen.getByLabelText('Selecionar Proposta')).toHaveValue('42');
    fireEvent.click(screen.getByLabelText(/Válvula esfera flangeada/));
    fireEvent.click(screen.getByLabelText(/Fornecedor Alpha/));
    expect(screen.getByText('Pronta para criar')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Criar cotação' }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ proposta: 42, observacao: 'Cotação criada a partir da Proposta.' }));
    expect(mocks.addItem).toHaveBeenCalledWith(7, { item_proposta_id: 420 });
    expect(mocks.addParticipante).toHaveBeenCalledWith(7, 1);
  });
});

describe('Detalhe da cotação', () => {
  it('abre existente, mantém o comparativo econômico, a seleção manual e o histórico', async () => {
    mocks.getById.mockResolvedValue(cotacao());
    mocks.comparativo.mockResolvedValue(comparativo());
    mocks.historico.mockResolvedValue([{ id: 1, evento: 'COTACAO_CRIADA', descricao: 'Cotação criada', dados_json: {}, usuario: 1, usuario_nome: 'Bruno', criado_em: '2026-08-31T10:00:00-03:00' }]);

    render(
      <MemoryRouter initialEntries={['/cotacoes-fornecedores/7']}>
        <Routes><Route path="/cotacoes-fornecedores/:id" element={<CotacaoFornecedorDetalhe />} /></Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'CF-20260831-0007' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Resumo' })).toBeInTheDocument();
    activateTab('Comparativo');
    expect(await screen.findByText('MENOR PREÇO')).toBeInTheDocument();
    expect(screen.getByText('MELHOR CUSTO TOTAL')).toBeInTheDocument();
    expect(screen.getByText('Custo total estimado')).toBeInTheDocument();
    expect(screen.getByText('Custo unitário efetivo')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Usar como referência' }));
    await waitFor(() => expect(mocks.selecionarReferencia).toHaveBeenCalledWith(7, 900));

    activateTab('Histórico');
    expect(await screen.findByText('Cotação criada')).toBeInTheDocument();
    expect(screen.getByText(/Bruno/)).toBeInTheDocument();
  });
});
