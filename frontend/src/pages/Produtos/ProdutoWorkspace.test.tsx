import { fireEvent, render, screen, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { ProdutoWorkspace } from '@/pages/Produtos/ProdutoWorkspace';
import { ProdutoFormTab } from './tabs/ProdutoFormTab';
import { produtoParaFormState } from './lib/produtoParaForm';
import type { FamiliaProduto, Produto, ProdutoFamiliaDaFicha } from '@/types';
import type { Material } from '@/types/material';
import type { ModoCodigoProduto, ProdutoFormState } from './types';
import { listProdutoComposicoes } from '@/services/api/produtoComposicao';

// O card 'Composição do produto' é espelhado como lista: busca ao montar, sem escrita.
vi.mock('@/services/api/produtoComposicao', () => ({
  listProdutoComposicoes: vi.fn().mockResolvedValue([]),
  createProdutoComposicao: vi.fn(),
  updateProdutoComposicao: vi.fn(),
  deleteProdutoComposicao: vi.fn(),
}));

// Catálogos que a Edição do Bloco 2 abre (rosca, schedule, polegada): resolvidos aqui,
// porque os testes da trava andam pelo DOM, não pela rede.
vi.mock('@/services/api/produtos', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@/services/api/produtos')>();
  const polegada = (id: number, oficial: string, mm: string) => ({
    id,
    codigo: String(id).padStart(2, '0'),
    codigo_oficial: oficial,
    descricao: `${oficial}"`,
    valor_decimal: '',
    valor_mm: mm,
    tipo_medida: 'NPS',
    ativo: true,
  });
  // As 13 roscas canônicas do seed (backend/apps/produtos/roscas_conexao_base.py), na
  // ordem em que `seed_roscas_conexao_canonicas()` as cria. A linha 1 é a sentinela com
  // `codigo` vazio e `descricao` 'BSP / padrão da família' — o dado que vazava na tela.
  const roscasCanonicas: [string, string][] = [
    ['', 'BSP / padrão da família'],
    ['N', 'NPT'],
    ['SW', 'Socket Weld / Solda de encaixe'],
    ['OD', 'OD / dupla anilha'],
    ['ODN', 'OD + NPT'],
    ['U', 'UNF'],
    ['JN', 'JIC x NPT'],
    ['NS', 'NPT x SW'],
    ['FN', 'Fêmea NPT'],
    ['FMN', 'Fêmea-macho NPT'],
    ['MFU', 'Macho-fêmea UNF x BSP'],
    ['FF', 'Fêmea-fêmea'],
    ['MMN', 'Macho-macho NPT'],
  ];
  return {
    ...mod,
    roscasConexaoService: {
      ...mod.roscasConexaoService,
      getAll: vi.fn(async () =>
        roscasCanonicas.map(([codigo, descricao], i) => ({
          id: i + 1,
          codigo,
          descricao,
          observacao: '',
          ativo: true,
        })),
      ),
    },
    schedulesEspessuraService: {
      ...mod.schedulesEspessuraService,
      getAll: vi.fn(async () => [
        { id: 8, codigo: '40', codigo_schedule: '40', descricao: 'Schedule 40' },
      ]),
      search: vi.fn(async () => []),
    },
    polegadasService: {
      ...mod.polegadasService,
      getById: vi.fn(async (id: number) =>
        id === 4 ? polegada(4, '3/4', '19.05') : polegada(3, '1/2', '12.7'),
      ),
      search: vi.fn(async () => []),
    },
    ncmApiService: { ...mod.ncmApiService, search: vi.fn(async () => []) },
  };
});

const NOME_FAMILIA = '0013 — FLANGE CEGO INOX 304';
const ROTULO_COMPOSICAO = 'Barra (comprimento em metros)';

/** Família como a ficha a entrega (com requisitos_produto): é o que ativa os blocos guiados. */
const FAMILIA_DA_FICHA = {
  id: 94,
  codigo_figura: '0013',
  descricao_base: 'FLANGE CEGO INOX 304',
  nome: NOME_FAMILIA,
  categoria_produto: 'PRODUTO_TECNICO',
  tipo_regra_codigo: 'FLANGE_CEGO',
  tipo_dimensional: 'ROSCA_NPT',
  material_vedacao: 'PTFE',
  material_base: 'ACO INOX 304',
  unidade_estoque_padrao: 'PC',
  unidade_venda_padrao: 'PC',
  unidade_compra_padrao: 'PC',
  unidade_fiscal_padrao: 'PC',
  unidades_venda_permitidas: ['PC'],
  unidades_compra_permitidas: ['PC'],
  tipo_controle_unidade: 'PECA',
  tipo_fisico: 'PECA',
  usa_conversao_dimensional: false,
  controla_composicao_fisica: false,
  tipo_composicao_fisica: 'BARRA_M',
  exige_certificado_qualidade: false,
  requisitos_produto: {
    usa_rosca_conexao: true,
    usa_schedule: true,
    usa_polegada_principal: true,
    usa_polegada_secundaria: true,
    exige_od_mm: false,
    exige_espessura_mm: false,
    exige_comprimento_mm: false,
    exige_diametro_interno_mm: false,
    exige_diametro_mostrador_mm: false,
    incluir_schedule_na_descricao: true,
  },
} as unknown as ProdutoFamiliaDaFicha;

/** Mesma família, mas exigindo certificado — único cenário em que o card Qualidade aparece. */
const FAMILIA_COM_CERTIFICADO = {
  ...FAMILIA_DA_FICHA,
  exige_certificado_qualidade: true,
} as unknown as ProdutoFamiliaDaFicha;

function produto(partial: Partial<Produto>): Produto {
  return {
    id: 77,
    descricao: 'FLANGE CEGO INOX 304 1/2"',
    unidade: 'PC',
    preco_custo: 0,
    preco_venda: 0,
    estoque_minimo: 0,
    codigo_completo: '0013.06',
    modo_codigo: 'INTERNO',
    familia_id: 94,
    familia_detalhes: {
      id: 94,
      codigo_figura: '0013',
      descricao_base: 'FLANGE CEGO INOX 304',
      nome: NOME_FAMILIA,
    },
    material: 'ACO CARBONO',
    material_label: 'Aço Carbono',
    material_nome: 'Aço Carbono A105',
    rosca_conexao_id: 2,
    rosca_conexao_detalhes: { id: 2, codigo: 'N', descricao: 'NPT' },
    schedule_ref_id: 8,
    schedule_ref_detalhes: {
      id: 8,
      codigo_schedule: '40',
      codigo: '40',
      descricao: 'Schedule 40',
    },
    polegada_principal_ref_id: 3,
    polegada_principal_ref_detalhes: {
      id: 3,
      codigo: '03',
      codigo_oficial: '1/2',
      descricao: '1/2"',
      tipo_medida: 'NPS',
      nome: 'NPS 1/2 — 1/2"',
    },
    polegada_secundaria_ref_id: 4,
    polegada_secundaria_ref_detalhes: {
      id: 4,
      codigo: '04',
      codigo_oficial: '3/4',
      descricao: '3/4"',
      tipo_medida: 'NPS',
      nome: 'NPS 3/4 — 3/4"',
    },
    tipo_controle_unidade: 'DIMENSIONAL',
    tipo_controle_unidade_display: 'Dimensional',
    tipo_fisico: 'PECA',
    tipo_fisico_display: 'Peça',
    tipo_composicao_fisica: 'BARRA_M',
    tipo_composicao_fisica_display: ROTULO_COMPOSICAO,
    tipo_controle_unidade_efetivo: 'PECA',
    tipo_controle_unidade_efetivo_display: 'Peça',
    tipo_fisico_efetivo: 'PECA',
    tipo_fisico_efetivo_display: 'Peça',
    tipo_composicao_fisica_efetivo: 'BARRA_M',
    tipo_composicao_fisica_efetivo_display: ROTULO_COMPOSICAO,
    unidade_estoque: 'PC',
    unidade_estoque_efetiva: 'PC',
    unidade_fiscal: 'PC',
    unidade_fiscal_efetiva: 'PC',
    ncm: '73072100',
    observacoes_conversao: 'Peso conferido no recebimento.',
    ...partial,
  } as Produto;
}

/** Produto com a família da ficha (payload do retrieve) — liga os blocos guiados pela família. */
function produtoComFamilia(partial: Partial<Produto> = {}): Produto {
  return produto({ familia_detalhes: FAMILIA_DA_FICHA, ...partial });
}

function abrirAba(nome: string) {
  const aba = screen.getByRole('tab', { name: nome });
  aba.focus();
  fireEvent.mouseDown(aba);
  fireEvent.click(aba);
}

/** O Painel Avançado nasce colapsado: o conteúdo só existe no DOM depois de abri-lo. */
function abrirPainelAvancado() {
  fireEvent.click(screen.getByRole('button', { name: /Painel Avançado/ }));
}

/**
 * O espelho é julgado card a card: sem escopo no card, um rótulo que aparecesse em outro lugar
 * da tela faria a asserção passar por engano. 'Conversão de Medidas' é heading 2x (título do
 * card + h3 interno do ConversaoMedidasBlock), por isso o primeiro match.
 */
function cardPorTitulo(nome: string) {
  const card = screen.getAllByRole('heading', { name: nome })[0].closest('div.rounded-lg');
  if (!(card instanceof HTMLElement)) throw new Error(`Card "${nome}" não encontrado`);
  return within(card);
}

/* --- Fixture da Edição (o Material é o único campo julgado aqui) ------------- */

const MATERIAIS = [
  { id: 501, nome: 'AÇO INOX 304', categoria: 'ACO_INOX' },
  { id: 999, nome: 'AÇO CARBONO A105', categoria: 'ACO_CARBONO' },
] as unknown as Material[];

/** Família como a tela a recebe: `material_base_ref` é o que faz o Material ter molde. */
function familiaComMolde(overrides: Partial<FamiliaProduto> = {}): FamiliaProduto {
  return {
    id: 94,
    codigo_figura: '0013',
    descricao_base: 'FLANGE CEGO INOX 304',
    material_base: 'AÇO INOX 304',
    material_base_ref: 501,
    ...overrides,
  } as unknown as FamiliaProduto;
}

/**
 * Form de Edição construído a partir da ficha: os catálogos do Bloco 2 vêm do mock
 * de `@/services/api/produtos`, então nada aqui vai à rede.
 */
function formDeEdicao(overrides: Partial<ProdutoFormState> = {}): ProdutoFormState {
  return {
    ...produtoParaFormState(produtoComFamilia()),
    ncm: '',
    ...overrides,
  };
}

function renderEdicao(
  form: ProdutoFormState,
  familia: FamiliaProduto | null,
  opts: { produto?: Produto | null; ehAdmin?: boolean } = {},
) {
  const { produto = produtoComFamilia(), ehAdmin = false } = opts;
  render(
    <ProdutoFormTab
      form={form}
      setForm={vi.fn()}
      familiaSelecionada={familia}
      materiais={MATERIAIS}
      produto={produto}
      editingCodigo={produto?.codigo_completo ?? null}
      ehAdmin={ehAdmin}
    />,
  );
}

/** Família que pede medidas: é o `requisitos_produto` que liga o Bloco 2. */
function familiaComMedidas(overrides: Partial<FamiliaProduto> = {}): FamiliaProduto {
  return familiaComMolde({
    tipo_dimensional: 'NPS',
    requisitos_produto: {
      usa_rosca_conexao: true,
      usa_schedule: true,
      usa_polegada_principal: true,
      usa_polegada_secundaria: true,
      exige_od_mm: true,
      exige_espessura_mm: false,
      exige_comprimento_mm: false,
      exige_diametro_interno_mm: false,
      exige_diametro_mostrador_mm: false,
      incluir_schedule_na_descricao: true,
    },
    ...overrides,
  });
}

const AVISO_MEDIDAS_TRAVADAS =
  'As medidas definem o código deste produto. Para um tamanho diferente, crie um novo produto.';

/** Fonte da aba: as sentinelas de <option> do Radix só existem no DOM com o seletor aberto. */
const tabSrc = readFileSync(
  resolve(process.cwd(), 'src/pages/Produtos/tabs/ProdutoFormTab.tsx'),
  'utf8',
);

describe('ProdutoWorkspace (espelho da Edição — Sprint 3.7)', () => {
  it('abre com as mesmas 4 abas da ficha de edição, na mesma ordem', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    expect(screen.getAllByRole('tab').map((aba) => aba.textContent)).toEqual([
      'Configuração do Produto',
      'Painel operacional',
      'Rastreabilidade',
      'Histórico',
    ]);
  });

  it('renderiza os 4 blocos visíveis com o Painel Avançado colapsado', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    [
      'Identificação',
      'Identidade técnica',
      'Medidas',
      'Preços e Estoque',
      'Fiscal',
    ].forEach((nome) => expect(screen.getByText(nome)).toBeInTheDocument());

    // Bloco 1 não repete mais o molde: sem 'Produto guiado', sem 'Obrigatórios', sem tipo de cadastro.
    expect(screen.queryByText('Produto guiado pela Família/Figura')).toBeNull();
    expect(screen.queryByText(/^Obrigatórios:/)).toBeNull();
    expect(screen.queryByText('Tipo de cadastro')).toBeNull();

    // Nada dos blocos avançados antes de abrir o painel.
    expect(screen.queryByText('Conversão de Medidas')).toBeNull();
    expect(screen.queryByText('Composição do produto')).toBeNull();
    expect(screen.queryByText('Fiscal (avançado)')).toBeNull();
  });

  it('abre o Painel Avançado e mostra os blocos avançados', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);
    abrirPainelAvancado();

    // 'Conversão de Medidas' é heading 2x (card + h3 interno), por isso o match por presença.
    ['Cadastro e código', 'Fiscal (avançado)', 'Conversão de Medidas', 'Composição do produto'].forEach(
      (nome) => expect(screen.getAllByText(nome).length).toBeGreaterThan(0),
    );
    // Qualidade só aparece quando a família exige o certificado.
    expect(screen.queryByText('Qualidade')).toBeNull();
  });

  it('mostra o conteúdo do payload em campos desabilitados, sem o estado vazio do formulário', () => {
    render(<ProdutoWorkspace produto={produto({ preco_custo: 300, preco_venda: 700 })} mode="view" />);

    expect(cardPorTitulo('Identificação').getByDisplayValue('FLANGE CEGO INOX 304 1/2"')).toBeDisabled();
    const precos = cardPorTitulo('Preços e Estoque');
    expect(precos.getByDisplayValue('300,00')).toBeDisabled();
    expect(precos.getByDisplayValue('700,00')).toBeDisabled();
    expect(precos.getByDisplayValue('PC')).toBeDisabled();
  });

  it('troca o RadioGroup de tipo de cadastro por texto, sem controle de escrita', () => {
    const casos: Array<[ModoCodigoProduto, string]> = [
      ['INTERNO', 'Código interno por regra (família / figura)'],
      ['MANUAL', 'Código manual / fabricante'],
      ['LEGADO', 'Legado (campos texto livres)'],
    ];

    casos.forEach(([modo, rotulo]) => {
      const { unmount } = render(
        <ProdutoWorkspace produto={produto({ modo_codigo: modo })} mode="view" />,
      );
      abrirPainelAvancado();
      expect(cardPorTitulo('Cadastro e código').getByText(rotulo)).toBeInTheDocument();
      expect(screen.queryByRole('radiogroup')).toBeNull();
      unmount();
    });
  });

  it('esconde as ações de escrita da Identificação', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    expect(screen.queryByText('+ Nova família')).toBeNull();
    expect(screen.queryByText(/Usar descrição sugerida/)).toBeNull();
    // AsyncAutocomplete continua montado (o nome vem do payload), mas não aceita digitação.
    expect(screen.getByDisplayValue(NOME_FAMILIA)).toBeDisabled();
  });

  it('lê o material do payload em vez de montar o select do catálogo', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    const tecnica = cardPorTitulo('Identidade técnica');
    const material = tecnica.getByDisplayValue('Aço Carbono A105');
    expect(material).toBeDisabled();
    expect(material.tagName).toBe('INPUT');
    expect(tecnica.queryByText('Selecione...')).toBeNull();
    expect(tecnica.queryByText('Nenhum material cadastrado.')).toBeNull();
  });

  it('reúne rosca, schedule e polegadas num único bloco de Medidas, resolvido pelo payload', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    const medidas = cardPorTitulo('Medidas');
    expect(medidas.getByDisplayValue('NPT')).toBeDisabled();
    expect(medidas.getByDisplayValue('40 — Schedule 40')).toBeDisabled();
    expect(medidas.getByDisplayValue('1/2"')).toBeDisabled();
    expect(medidas.getByDisplayValue('3/4"')).toBeDisabled();
    expect(medidas.getByText('Espessura da parede (schedule)')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Busque por código, polegada, decimal ou mm')).toBeNull();
  });

  it('rosca sem código mostra apenas a descrição', () => {
    render(
      <ProdutoWorkspace
        produto={produtoComFamilia({
          rosca_conexao_detalhes: { id: 12, codigo: '', descricao: 'BSP FÊMEA' },
        })}
        mode="view"
      />,
    );

    expect(cardPorTitulo('Medidas').getByDisplayValue('BSP FÊMEA')).toBeDisabled();
  });

  it('mostra a polegada sem o rótulo técnico NPS', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    expect(screen.queryByText('NPS 1/2 — 1/2"')).toBeNull();
    expect(screen.queryByText(/^NPS\s/)).toBeNull();
  });

  it('não deixa badge de herança com botão "Limpar" na ficha', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);
    abrirPainelAvancado();

    expect(screen.queryByText('Herdado da Família')).toBeNull();
    expect(screen.queryByLabelText(/Remover herança de/)).toBeNull();
    expect(screen.queryByText(/Herdados da família ao selecioná-la/)).toBeNull();
    expect(screen.queryByRole('button', { name: 'Limpar seleção' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Limpar' })).toBeNull();
  });

  // Botão desabilitado é só ruído na ficha: em leitura ele não aparece, e não existe escrita possível.
  it('esconde os botões de ação dos autocompletes e da Conversão de Medidas', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);
    abrirPainelAvancado();

    const conversao = cardPorTitulo('Conversão de Medidas');
    expect(conversao.queryByText(/Sugestão linear/)).toBeNull();
    expect(conversao.queryByText(/Sugestão chapa/)).toBeNull();
    expect(conversao.queryByText('Limpar (herdar da família no produto)')).toBeNull();
    // Os checkboxes de unidades continuam visíveis, só que inertes.
    expect(conversao.getAllByRole('checkbox').length).toBeGreaterThan(0);
    conversao.getAllByRole('checkbox').forEach((c) => expect(c).toBeDisabled());
  });

  it('mantém os campos derivados da família somente leitura, com o valor da família', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    const tecnica = cardPorTitulo('Identidade técnica');
    expect(tecnica.getByDisplayValue('PTFE')).toBeDisabled();
    expect(tecnica.getByText('Material de vedação')).toBeInTheDocument();
    // Sem fallback: norma/pressão da família não preenchidas (0/117) não viram linha vazia na tela.
    expect(tecnica.queryByText('Norma técnica')).toBeNull();
    expect(tecnica.queryByText('Pressão nominal')).toBeNull();
  });

  it('exibe a observação de conversão uma única vez, dentro de Conversão de Medidas', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    abrirPainelAvancado();

    const conversao = cardPorTitulo('Conversão de Medidas');
    expect(conversao.getByText('5. Observações')).toBeInTheDocument();
    expect(conversao.getByDisplayValue('Peso conferido no recebimento.')).toBeDisabled();
    expect(screen.getAllByDisplayValue('Peso conferido no recebimento.')).toHaveLength(1);
    // O card 'Observações' duplicado da Edição não existe mais — nem aqui nem lá.
    expect(screen.queryByRole('heading', { name: 'Observações' })).toBeNull();
  });

  it('desabilita os controles de unidade, os selects e as flags de conversão', () => {
    render(
      <ProdutoWorkspace
        produto={produtoComFamilia({ controla_composicao_fisica: true, usa_conversao_dimensional: true })}
        mode="view"
      />,
    );
    abrirPainelAvancado();

    const conversao = cardPorTitulo('Conversão de Medidas');
    conversao.getAllByDisplayValue('PC').forEach((campo) => expect(campo).toBeDisabled());
    conversao.getAllByRole('checkbox').forEach((flag) => expect(flag).toBeDisabled());
    conversao.getAllByRole('combobox').forEach((seletor) => expect(seletor).toBeDisabled());
    expect(conversao.getByText('Barra — comprimento em metros (tubo)')).toBeInTheDocument();
    expect(conversao.getByText(/Efetivo na tela:/)).toBeInTheDocument();
  });

  it('mostra o interruptor de Qualidade desabilitado quando a família exige certificado', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ familia_detalhes: FAMILIA_COM_CERTIFICADO })}
        mode="view"
      />,
    );
    abrirPainelAvancado();

    const qualidade = cardPorTitulo('Qualidade');
    expect(qualidade.getByRole('switch')).toBeDisabled();
    expect(qualidade.getByText('Exige Certificado de Qualidade')).toBeInTheDocument();
  });

  it('mantém os preços praticados e o estoque atual no bloco principal', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ ultimo_preco_compra: 900, ultimo_preco_venda: 1450.75, estoque_atual: 26.847 })}
        mode="view"
      />,
    );

    const precos = cardPorTitulo('Preços e Estoque');
    ['Última Compra', 'Última Venda', 'Estoque Atual'].forEach((label) =>
      expect(precos.getByText(label)).toBeInTheDocument(),
    );
    expect(precos.getByDisplayValue('900,00')).toBeDisabled();
    expect(precos.getByDisplayValue('1.450,75')).toBeDisabled();
    expect(precos.getByDisplayValue('26,847')).toBeDisabled();
  });

  // Sprint 3.7: o bloco de preços é sempre visível — o cadastro zerado continua aparecendo como 0,00.
  it('mostra o bloco inteiro de preços mesmo com o cadastro zerado', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    const precos = cardPorTitulo('Preços e Estoque');
    ['Unidade Comercial', 'Preço Custo', 'Preço Venda', 'Estoque Mínimo'].forEach((label) =>
      expect(precos.getByText(label)).toBeInTheDocument(),
    );
    // Custo e venda de cadastro zerados continuam na tela: agora a linha é sempre visível.
    expect(precos.getAllByDisplayValue('0,00')).toHaveLength(2);
    expect(precos.getByDisplayValue('PC')).toBeDisabled();
  });

  it('põe travessão no preço e no estoque quando o payload não traz o campo', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ ultimo_preco_compra: null, ultimo_preco_venda: null, estoque_atual: undefined })}
        mode="view"
      />,
    );

    // Escopado ao card: sem unidade de venda/compra o <select> também exibe '—' (option vazia).
    const precos = cardPorTitulo('Preços e Estoque');
    ['Última Compra', 'Última Venda', 'Estoque Atual'].forEach((label) =>
      expect(precos.getByText(label)).toBeInTheDocument(),
    );
    expect(precos.getAllByDisplayValue('—')).toHaveLength(3);
  });

  it('lista as composições da ficha sem nenhum botão de escrita', async () => {
    vi.mocked(listProdutoComposicoes).mockResolvedValueOnce([
      {
        id: 5,
        produto_final_id: 77,
        nome: 'CONJ UNIAO 1/2',
        tipo_composicao: 'MONTAGEM_SIMPLES',
        ativo: true,
        padrao: true,
        itens: [{ componente_produto_id: 12, quantidade_por_unidade_final: '2', obrigatorio: true, ordem: 0 }],
      },
    ] as unknown as Awaited<ReturnType<typeof listProdutoComposicoes>>);

    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    abrirPainelAvancado();

    const composicao = cardPorTitulo('Composição do produto');
    expect(await composicao.findByText('CONJ UNIAO 1/2')).toBeInTheDocument();
    expect(listProdutoComposicoes).toHaveBeenCalledWith(77);
    expect(composicao.queryByRole('button', { name: /Nova composição/ })).toBeNull();
    expect(composicao.queryByRole('button', { name: 'Editar' })).toBeNull();
    expect(composicao.queryByRole('button', { name: 'Inativar' })).toBeNull();
  });

  it('espelha o bloco Fiscal em somente leitura, sem a ação de remover override', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    const fiscal = cardPorTitulo('Fiscal');
    expect(fiscal.getByDisplayValue('73072100')).toBeDisabled();
    expect(fiscal.getByText(/CST\/CSOSN e alíquotas são configurados no módulo fiscal/)).toBeInTheDocument();
    expect(screen.queryByText('Remover override e usar NCM da família')).toBeNull();
    expect(screen.queryByText('Nenhum NCM encontrado')).toBeNull();

    // O override é o espelho do editor da Edição: aparece no Avançado, desabilitado e sem botão.
    abrirPainelAvancado();
    const avancado = cardPorTitulo('Fiscal (avançado)');
    expect(avancado.getByDisplayValue('73072100')).toBeDisabled();
    expect(avancado.getByDisplayValue('PC')).toBeDisabled();
    expect(avancado.queryByText('Remover override e usar NCM da família')).toBeNull();
  });

  it('não mostra o bloco de Medidas nem linhas técnicas vazias quando o produto não tem família', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    expect(screen.queryByText('Medidas')).toBeNull();
    expect(screen.queryByText('Material de vedação')).toBeNull();
    const tecnica = cardPorTitulo('Identidade técnica');
    expect(tecnica.getByDisplayValue('Aço Carbono A105')).toBeDisabled();
    expect(tecnica.queryByText('Norma técnica')).toBeNull();
  });

  it('renderiza o bloco LEGADO inteiro e desabilitado para um produto legado', () => {
    render(
      <ProdutoWorkspace
        produto={produto({
          modo_codigo: 'LEGADO',
          familia_id: null,
          familia_detalhes: null,
          figura: '6119',
          sufixo: 'F04',
          schedule: '40',
          polegada_principal: '1 1/2"',
          polegada_secundaria: '3/4"',
        })}
        mode="view"
      />,
    );
    abrirPainelAvancado();

    const cadastro = cardPorTitulo('Cadastro e código');
    ['6119', 'F04', '40', '1 1/2"', '3/4"'].forEach((valor) =>
      expect(cadastro.getByDisplayValue(valor)).toBeDisabled(),
    );
    expect(cadastro.queryByText(/apenas segmentos preenchidos entram no código/)).toBeNull();
  });

  it('mantém a aba Fiscal antiga fora da ficha: nenhuma âncora "Fiscal" duplicada', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    expect(screen.queryByRole('tab', { name: 'Fiscal' })).toBeNull();
    abrirAba('Painel operacional');
    expect(screen.getByRole('tab', { name: 'Painel operacional' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });
});

describe('ProdutoFormTab (Edição) — Material segue o molde da família (Sprint 3.8, decisão 1)', () => {
  it('trava o Material quando a família tem o padrão e o produto o repete', () => {
    renderEdicao(formDeEdicao({ material_ref: 501, material: 'AÇO INOX 304' }), familiaComMolde());

    const tecnica = cardPorTitulo('Identidade técnica');
    const campo = tecnica.getByDisplayValue('AÇO INOX 304');
    expect(campo.tagName).toBe('INPUT');
    expect(campo).toBeDisabled();
    expect(tecnica.queryByRole('combobox')).toBeNull();
    expect(tecnica.getByText(/Herdado da família 0013/)).toBeInTheDocument();
    // travado e preenchido pelo molde não se anuncia como campo a preencher
    expect(tecnica.getByText('Material').textContent).not.toMatch(/\*/);
  });

  it('deixa o Material editável quando a família não tem padrão (material_base_ref vazio)', () => {
    renderEdicao(
      formDeEdicao({ material_ref: 999, material: 'AÇO CARBONO A105' }),
      familiaComMolde({ material_base_ref: null }),
    );

    const tecnica = cardPorTitulo('Identidade técnica');
    expect(tecnica.getByRole('combobox')).toBeEnabled();
    expect(tecnica.queryByText(/Herdado da família/)).toBeNull();
    expect(tecnica.queryByText(/diferente do padrão da família/)).toBeNull();
  });

  // Sem esta exceção a regra 'família tem molde => travado' trancaria um override já salvo:
  // o produto ficaria com material diferente da família sem poder voltar ao padrão.
  it('mantém editável e declara o override quando o produto usa outro material que não o do molde', () => {
    renderEdicao(formDeEdicao({ material_ref: 999, material: 'AÇO CARBONO A105' }), familiaComMolde());

    const tecnica = cardPorTitulo('Identidade técnica');
    expect(tecnica.getByRole('combobox')).toBeEnabled();
    expect(tecnica.getByText(/Este produto usa material diferente do padrão da família/)).toBeInTheDocument();
    expect(tecnica.queryByText(/Herdado da família/)).toBeNull();
  });

  it('não trava o Material vazio de um produto novo antes de a herança preencher o molde', () => {
    renderEdicao(formDeEdicao({ material_ref: null, material: '' }), familiaComMolde());

    const tecnica = cardPorTitulo('Identidade técnica');
    expect(tecnica.getByRole('combobox')).toBeEnabled();
    expect(tecnica.getByText('Material').textContent).toMatch(/\*/);
  });

  it('mostra o material salvo no select, resolvido pelo catálogo que o container trouxe', () => {
    renderEdicao(formDeEdicao({ material_ref: 999, material: 'AÇO CARBONO A105' }), familiaComMolde());
    expect(cardPorTitulo('Identidade técnica').getByRole('combobox')).toHaveTextContent('AÇO CARBONO A105');
  });
});

describe('ProdutoFormTab (Edição) — Rosca é dado do produto (Sprint 3.8, tarefa 1)', () => {
  it('abre a rosca como select editável do catálogo, com o código comercial da linha salva', async () => {
    renderEdicao(formDeEdicao(), familiaComMedidas(), { produto: null });

    const medidas = cardPorTitulo('Medidas');
    const seletor = medidas.getByRole('combobox');
    expect(seletor).toBeEnabled();
    expect(await medidas.findByText('NPT')).toBeInTheDocument();
  });

  // A linha-sentinela do catálogo (codigo vazio, descricao 'BSP / padrão da família') é o
  // dado que aparecia na tela. O backend já a converte para 'BSP' em
  // `_descricao_rosca_comercial`; a ficha tem de mostrar o mesmo.
  it('mostra BSP — e nunca o metadado do catálogo — na rosca-sentinela de produto salvo', () => {
    renderEdicao(
      formDeEdicao({ od_mm: 19.05 }),
      familiaComMedidas(),
      { produto: produtoComFamilia({ rosca_conexao_detalhes: { id: 1, codigo: '', descricao: 'BSP / padrão da família' } }) },
    );

    const medidas = cardPorTitulo('Medidas');
    expect(medidas.getByDisplayValue('BSP')).toBeDisabled();
    expect(medidas.queryByText(/padrão da família/)).toBeNull();
  });

  it('mostra BSP na Visualização para a mesma linha-sentinela', () => {
    render(
      <ProdutoWorkspace
        produto={produtoComFamilia({
          rosca_conexao_id: 1,
          rosca_conexao_detalhes: { id: 1, codigo: '', descricao: 'BSP / padrão da família' },
        })}
        mode="view"
      />,
    );

    const medidas = cardPorTitulo('Medidas');
    expect(medidas.getByDisplayValue('BSP')).toBeDisabled();
    expect(medidas.queryByText(/padrão da família/)).toBeNull();
  });

  it('mantém a sentinela de edição como opção neutra do select', () => {
    expect(tabSrc).toMatch(/<SelectItem value=\{SEM_ROSCA\}>— \{SEM_ROSCA_LABEL\} —<\/SelectItem>/);
  });

  // O texto antigo dizia que a família resolvia a rosca; `montar_codigo_interno` só lê
  // produto.rosca_conexao, então a frase mentia na tela e escondia que o campo é do produto.
  it('remove do Bloco 2 todo texto que apresentava a rosca como padrão da família', () => {
    expect(tabSrc).not.toMatch(/Sem rosca específica/);
    expect(tabSrc).not.toMatch(/usa o padrão da família/);
  });

  it('nenhum componente de Produto renderiza o rótulo interno da linha-sentinela', () => {
    const arquivos = [
      'src/pages/Produtos/tabs/ProdutoFormTab.tsx',
      'src/pages/Produtos/ProdutoWorkspace.tsx',
      'src/pages/Produtos/ProdutoList.tsx',
      'src/pages/Produtos/hooks/useProdutoForm.ts',
      'src/components/familias/FamiliaDominioCard.tsx',
      'src/lib/roscaLabel.ts',
    ];
    for (const caminho of arquivos) {
      const fonte = readFileSync(resolve(process.cwd(), caminho), 'utf8');
      for (const linha of fonte.split('\n')) {
        if (!/rosca/i.test(linha)) continue;
        if (linha.trimStart().startsWith('*') || linha.trimStart().startsWith('//')) continue;
        expect(`${caminho} → ${linha}`).not.toMatch(/padr[ãa]o da fam[íi]lia/i);
      }
    }
  });

  it('mostra a sentinela neutra quando o produto não tem rosca', () => {
    render(
      <ProdutoWorkspace
        produto={produtoComFamilia({ rosca_conexao_id: null, rosca_conexao_detalhes: null })}
        mode="view"
      />,
    );

    expect(cardPorTitulo('Medidas').getByDisplayValue('Sem rosca / conexão')).toBeDisabled();
  });

  it('usa o rótulo amigável na polegada escolhida, sem NPS nem mm no campo', async () => {
    renderEdicao(formDeEdicao(), familiaComMedidas(), { produto: null });

    const medidas = cardPorTitulo('Medidas');
    expect(await medidas.findByDisplayValue('1/2"')).toBeEnabled();
    expect(await medidas.findByDisplayValue('3/4"')).toBeEnabled();
    expect(medidas.queryByDisplayValue(/NPS|mm/)).toBeNull();
  });
});

describe('ProdutoFormTab (Edição) — medidas travadas em produto salvo (Sprint 3.8, tarefa 3)', () => {
  it('põe o Bloco 2 inteiro em leitura e avisa que as medidas definem o código', () => {
    renderEdicao(formDeEdicao({ od_mm: 19.05 }), familiaComMedidas());

    const medidas = cardPorTitulo('Medidas');
    ['NPT', '40 — Schedule 40', '1/2"', '3/4"', '19,05'].forEach((valor) =>
      expect(medidas.getByDisplayValue(valor)).toBeDisabled(),
    );
    expect(medidas.getByText(AVISO_MEDIDAS_TRAVADAS)).toBeInTheDocument();
    expect(medidas.queryByRole('combobox')).toBeNull();
    expect(medidas.getByText('Rosca / conexão').textContent).not.toContain('*');
  });

  it('esconde o botão de liberação de quem não é admin', () => {
    renderEdicao(formDeEdicao(), familiaComMedidas(), { ehAdmin: false });
    expect(cardPorTitulo('Medidas').queryByRole('button', { name: /Liberar edição de medidas/ })).toBeNull();
  });

  it('libera as medidas para admin somente depois de confirmar o risco', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderEdicao(formDeEdicao({ od_mm: 19.05 }), familiaComMedidas(), { ehAdmin: true });
    const medidas = cardPorTitulo('Medidas');
    const botao = medidas.getByRole('button', { name: 'Liberar edição de medidas' });

    fireEvent.click(botao);
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(medidas.queryByRole('combobox')).toBeNull();
    expect(medidas.getByDisplayValue('NPT')).toBeDisabled();

    confirm.mockReturnValue(true);
    fireEvent.click(medidas.getByRole('button', { name: 'Liberar edição de medidas' }));
    expect(medidas.getByRole('combobox')).toBeEnabled();
    expect(medidas.getByDisplayValue('19,05')).toBeEnabled();
    expect(medidas.getByText(/^Edição de medidas liberada/)).toBeInTheDocument();
    confirm.mockRestore();
  });

  it('deixa o Bloco 2 editável na criação de produto', () => {
    renderEdicao(formDeEdicao({ od_mm: 19.05 }), familiaComMedidas(), { produto: null });

    const medidas = cardPorTitulo('Medidas');
    expect(medidas.queryByText(AVISO_MEDIDAS_TRAVADAS)).toBeNull();
    expect(medidas.getByRole('combobox')).toBeEnabled();
    expect(medidas.getByDisplayValue('19,05')).toBeEnabled();
  });

  it('na Visualização o Bloco 2 fica em leitura sem o aviso, que é da Edição', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);
    const medidas = cardPorTitulo('Medidas');
    expect(medidas.getByDisplayValue('NPT')).toBeDisabled();
    expect(medidas.queryByText(AVISO_MEDIDAS_TRAVADAS)).toBeNull();
    expect(medidas.queryByRole('button', { name: /Liberar edição de medidas/ })).toBeNull();
  });
});
