import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProdutoWorkspace } from '@/pages/Produtos/ProdutoWorkspace';
import type { Produto, ProdutoFamiliaDaFicha } from '@/types';
import type { ModoCodigoProduto } from './types';
import { listProdutoComposicoes } from '@/services/api/produtoComposicao';

// O card 'Composição do produto' é espelhado como lista: busca ao montar, sem escrita.
vi.mock('@/services/api/produtoComposicao', () => ({
  listProdutoComposicoes: vi.fn().mockResolvedValue([]),
  createProdutoComposicao: vi.fn(),
  updateProdutoComposicao: vi.fn(),
  deleteProdutoComposicao: vi.fn(),
}));

const NOME_FAMILIA = '0013 — FLANGE CEGO INOX 304';
const ROTULO_COMPOSICAO = 'Barra (comprimento em metros)';

/** Família como a ficha a entrega (com requisitos_produto): é o que ativa os cards de herança. */
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
    rosca_conexao_id: 12,
    rosca_conexao_detalhes: { id: 12, codigo: 'NPT', descricao: 'NPT' },
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

/** Produto com a família da ficha (payload do retrieve) — liga os cards guiados pela família. */
function produtoComFamilia(partial: Partial<Produto> = {}): Produto {
  return produto({ familia_detalhes: FAMILIA_DA_FICHA, ...partial });
}

function abrirAba(nome: string) {
  const aba = screen.getByRole('tab', { name: nome });
  aba.focus();
  fireEvent.mouseDown(aba);
  fireEvent.click(aba);
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

describe('ProdutoWorkspace (espelho da Edição)', () => {
  it('abre com as mesmas 5 abas da ficha de edição, na mesma ordem', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    expect(screen.getAllByRole('tab').map((aba) => aba.textContent)).toEqual([
      'Configuração do Produto',
      'Fiscal',
      'Painel operacional',
      'Rastreabilidade',
      'Histórico',
    ]);
  });

  it('renderiza na aba Configuração os mesmos cards da Edição', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    [
      'Identificação',
      'Preços e estoque',
      'Identidade técnica',
      'Tipo de peça e conexão',
      'Padrões da Família/Figura',
      'Requisitos da Família/Figura',
      'Polegadas de referência',
      'Qualidade',
      'Composição do produto',
    ].forEach((nome) => expect(screen.getByText(nome)).toBeInTheDocument());
    // Título do card e o h3 interno do ConversaoMedidasBlock: a única ocorrência dupla da tela.
    expect(screen.getAllByText('Conversão de Medidas')).toHaveLength(2);
  });

  it('mostra o conteúdo do payload em campos desabilitados, sem o estado vazio do formulário', () => {
    render(<ProdutoWorkspace produto={produto({ preco_custo: 300, preco_venda: 700 })} mode="view" />);

    expect(cardPorTitulo('Identificação').getByDisplayValue('FLANGE CEGO INOX 304 1/2"')).toBeDisabled();
    expect(cardPorTitulo('Preços e estoque').getByDisplayValue('300')).toBeDisabled();
    expect(cardPorTitulo('Preços e estoque').getByDisplayValue('700')).toBeDisabled();
    expect(cardPorTitulo('Preços e estoque').getByDisplayValue('PC')).toBeDisabled();
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
      expect(screen.getAllByText(rotulo).length).toBeGreaterThan(0);
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

  it('resolve rosca, schedule e polegadas com os *_detalhes do payload, sem abrir catálogo', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    expect(cardPorTitulo('Requisitos da Família/Figura').getByDisplayValue('NPT — NPT')).toBeDisabled();
    expect(
      cardPorTitulo('Requisitos da Família/Figura').getByDisplayValue('40 — Schedule 40'),
    ).toBeDisabled();
    expect(cardPorTitulo('Polegadas de referência').getByDisplayValue('1/2"')).toBeDisabled();
    expect(cardPorTitulo('Polegadas de referência').getByDisplayValue('3/4"')).toBeDisabled();
    expect(screen.queryByPlaceholderText('Busque por código, polegada, decimal ou mm')).toBeNull();
  });

  it('mostra a polegada sem o rótulo técnico NPS', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    expect(screen.queryByText('NPS 1/2 — 1/2"')).toBeNull();
    expect(screen.queryByText(/^NPS\s/)).toBeNull();
  });

  it('não deixa badge de herança com botão "Limpar" na ficha', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    expect(screen.queryByText('Herdado da Família')).toBeNull();
    expect(screen.queryByLabelText(/Remover herança de/)).toBeNull();
    expect(screen.queryByText(/Herdados da família ao selecioná-la/)).toBeNull();
  });

  it('mantém os campos derivados da família somente leitura, com o valor da família', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);

    const padroes = cardPorTitulo('Padrões da Família/Figura');
    expect(padroes.getByDisplayValue('PTFE')).toBeDisabled();
    expect(padroes.getByText('Material de vedação')).toBeInTheDocument();
  });

  it('exibe a observação de conversão uma única vez, dentro de Conversão de Medidas', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

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

    const conversao = cardPorTitulo('Conversão de Medidas');
    conversao.getAllByDisplayValue('PC').forEach((campo) => expect(campo).toBeDisabled());
    conversao.getAllByRole('checkbox').forEach((flag) => expect(flag).toBeDisabled());
    conversao.getAllByRole('combobox').forEach((seletor) => expect(seletor).toBeDisabled());
    expect(conversao.getByText('Barra — comprimento em metros (tubo)')).toBeInTheDocument();
    expect(conversao.getByText(/Efetivo na tela:/)).toBeInTheDocument();
    expect(cardPorTitulo('Qualidade').getByRole('switch')).toBeDisabled();
  });

  it('mantém os preços praticados e o estoque atual na tela principal', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ ultimo_preco_compra: 900, ultimo_preco_venda: 1450.75, estoque_atual: 26.847 })}
        mode="view"
      />,
    );

    const precos = cardPorTitulo('Preços e estoque');
    expect(precos.getByText('Últimos Preços e Estoque')).toBeInTheDocument();
    expect(precos.getByDisplayValue('900,00')).toBeDisabled();
    expect(precos.getByDisplayValue('1.450,75')).toBeDisabled();
    expect(precos.getByDisplayValue('26,847')).toBeDisabled();
  });

  // Cadastro zerado não diz nada na ficha: o que vale é o preço praticado na NF-e.
  it('esconde a linha do cadastro quando custo e venda de cadastro são zero', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    const precos = cardPorTitulo('Preços e estoque');
    ['Unidade comercial', 'Preço Custo', 'Preço Venda', 'Estoque Mínimo'].forEach((label) =>
      expect(precos.queryByText(label)).toBeNull(),
    );
    expect(precos.queryByDisplayValue('PC')).toBeNull();
    expect(precos.getByText('Últimos Preços e Estoque')).toBeInTheDocument();
  });

  it('mostra a linha inteira do cadastro quando basta um preço maior que zero', () => {
    render(<ProdutoWorkspace produto={produto({ preco_venda: 700 })} mode="view" />);

    const precos = cardPorTitulo('Preços e estoque');
    ['Unidade comercial', 'Preço Custo', 'Preço Venda', 'Estoque Mínimo'].forEach((label) =>
      expect(precos.getByText(label)).toBeInTheDocument(),
    );
    expect(precos.getByDisplayValue('PC')).toBeDisabled();
    expect(precos.getByDisplayValue('700')).toBeDisabled();
  });

  it('mostra a linha inteira do cadastro quando só o estoque mínimo é maior que zero', () => {
    render(
      <ProdutoWorkspace produto={produto({ preco_custo: 0, preco_venda: 0, estoque_minimo: 50 })} mode="view" />,
    );

    const precos = cardPorTitulo('Preços e estoque');
    ['Unidade comercial', 'Preço Custo', 'Preço Venda', 'Estoque Mínimo'].forEach((label) =>
      expect(precos.getByText(label)).toBeInTheDocument(),
    );
    expect(precos.getByDisplayValue('50')).toBeDisabled();
  });

  it('põe travessão no preço e no estoque quando o payload não traz o campo', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ ultimo_preco_compra: null, ultimo_preco_venda: null, estoque_atual: undefined })}
        mode="view"
      />,
    );

    // Escopado ao card: sem unidade de venda/compra o <select> também exibe '—' (option vazia).
    const precos = cardPorTitulo('Preços e estoque');
    ['Última compra', 'Última venda', 'Estoque atual'].forEach((label) =>
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

    const composicao = cardPorTitulo('Composição do produto');
    expect(await composicao.findByText('CONJ UNIAO 1/2')).toBeInTheDocument();
    expect(listProdutoComposicoes).toHaveBeenCalledWith(77);
    expect(composicao.queryByRole('button', { name: /Nova composição/ })).toBeNull();
    expect(composicao.queryByRole('button', { name: 'Editar' })).toBeNull();
    expect(composicao.queryByRole('button', { name: 'Inativar' })).toBeNull();
  });

  it('espelha a aba Fiscal com os campos desabilitados e sem a ação de remover override', () => {
    render(<ProdutoWorkspace produto={produtoComFamilia()} mode="view" />);
    abrirAba('Fiscal');

    expect(screen.getByText('NCM efetivo para tributação')).toBeInTheDocument();
    expect(screen.getByDisplayValue('73072100')).toBeDisabled();
    expect(screen.queryByText('Remover override e usar NCM da família')).toBeNull();
    expect(screen.queryByText('Nenhum NCM encontrado')).toBeNull();
  });

  it('não mostra os cards condicionais quando o produto não tem família', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    expect(screen.queryByText('Padrões da Família/Figura')).toBeNull();
    expect(screen.queryByText('Requisitos da Família/Figura')).toBeNull();
    expect(screen.queryByText('Polegadas de referência')).toBeNull();
    expect(cardPorTitulo('Conversão de Medidas').getByText('5. Observações')).toBeInTheDocument();
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

    const identificacao = cardPorTitulo('Identificação');
    ['6119', 'F04', '40', '1 1/2"', '3/4"'].forEach((valor) =>
      expect(identificacao.getByDisplayValue(valor)).toBeDisabled(),
    );
    expect(identificacao.queryByText(/apenas segmentos preenchidos entram no código/)).toBeNull();
  });
});
