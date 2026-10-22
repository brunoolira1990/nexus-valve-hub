import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ProdutoWorkspace } from '@/pages/Produtos/ProdutoWorkspace';
import type { Produto } from '@/types';

const NOME_FAMILIA = '0013 — FLANGE CEGO INOX 304';
const ROTULO_COMPOSICAO = 'Barra (comprimento em metros)';

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
    ...partial,
  } as Produto;
}

function abrirAba(nome: string) {
  const aba = screen.getByRole('tab', { name: nome });
  aba.focus();
  fireEvent.mouseDown(aba);
  fireEvent.click(aba);
}

/**
 * 'Schedule' e 'Polegada principal/secundária' só existem no card 'Identidade técnica', mas a
 * asserção de ausência na 'Identificação' precisa do card certo para não passar por engano
 * quando o rótulo some das duas telas.
 */
function cardPorTitulo(nome: string) {
  const card = screen.getByRole('heading', { name: nome }).closest('div.rounded-lg');
  if (!(card instanceof HTMLElement)) throw new Error(`Card "${nome}" não encontrado`);
  return within(card);
}

describe('ProdutoWorkspace (visualização)', () => {
  it('mostra o código completo uma única vez, dentro de Identificação', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    expect(screen.getAllByText('0013.06')).toHaveLength(1);
  });

  it('não repete o código como campo manual no modo MANUAL', () => {
    render(<ProdutoWorkspace produto={produto({ modo_codigo: 'MANUAL', familia_id: null })} mode="view" />);
    expect(screen.getAllByText('0013.06')).toHaveLength(1);
  });

  it('abre com as mesmas 5 abas da ficha de edição, na mesma ordem', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    expect(screen.getAllByRole('tab').map((aba) => aba.textContent)).toEqual([
      'Configuração do Produto',
      'Fiscal',
      'Painel operacional',
      'Rastreabilidade',
      'Histórico',
    ]);
    expect(screen.queryByRole('tab', { name: 'Geral' })).toBeNull();
    expect(screen.queryByRole('tab', { name: 'Classificação industrial' })).toBeNull();
  });

  it('mostra Identificação, Preços e Classificação técnica na mesma aba, sem trocar de aba', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    expect(screen.getByText('Identificação')).toBeInTheDocument();
    expect(screen.getByText('Preços e estoque')).toBeInTheDocument();
    expect(screen.getByText('Identidade técnica')).toBeInTheDocument();
    expect(screen.getByText('Unidades e controle físico')).toBeInTheDocument();
  });

  it('mantém Fiscal em aba separada, fora da Configuração do Produto', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    expect(screen.queryByText('NCM efetivo para tributação')).toBeNull();

    abrirAba('Fiscal');
    expect(screen.getByText('NCM efetivo para tributação')).toBeInTheDocument();
  });

  it('mostra o nome da família em vez do id do banco', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    expect(screen.getByText(NOME_FAMILIA)).toBeInTheDocument();
    expect(screen.queryByText('#94')).toBeNull();
  });

  it('na aba Configuração do Produto a classificação técnica usa rótulos e nomes em vez de enums e ids', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    expect(screen.getByText('Aço Carbono A105')).toBeInTheDocument();
    expect(screen.getByText('NPT')).toBeInTheDocument();
    expect(screen.getByText('40')).toBeInTheDocument();
    expect(screen.getByText('1/2"')).toBeInTheDocument();
    expect(screen.getByText('Dimensional')).toBeInTheDocument();
    expect(screen.getByText('Peça')).toBeInTheDocument();

    expect(screen.queryByText('ACO CARBONO')).toBeNull();
    expect(screen.queryByText('PECA')).toBeNull();
    expect(screen.queryByText('DIMENSIONAL')).toBeNull();
    expect(screen.queryByText('#12')).toBeNull();
    expect(screen.queryByText('#8')).toBeNull();
    expect(screen.queryByText('#3')).toBeNull();
  });

  it('mostra a polegada sem o rótulo técnico NPS', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);

    expect(screen.queryByText('NPS 1/2 — 1/2"')).toBeNull();
    expect(screen.queryByText(/^NPS\s/)).toBeNull();
  });

  it('traduz o modo de código em vez do código cru', () => {
    const { rerender } = render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    expect(screen.getByText('Interno')).toBeInTheDocument();

    rerender(<ProdutoWorkspace produto={produto({ modo_codigo: 'MANUAL' })} mode="view" />);
    expect(screen.getByText('Manual')).toBeInTheDocument();

    rerender(<ProdutoWorkspace produto={produto({ modo_codigo: 'LEGADO' })} mode="view" />);
    expect(screen.getByText('Legado')).toBeInTheDocument();

    expect(screen.queryByText(/^(INTERNO|MANUAL|LEGADO)$/)).toBeNull();
  });

  it('na aba Configuração do Produto a polegada das dimensões aparece em formato amigável', () => {
    render(
      <ProdutoWorkspace
        produto={produto({
          dim_aba_mm: 12.7,
          dim_aba_polegada_ref: 5,
          dim_aba_polegada_ref_detalhes: {
            id: 5,
            codigo: '55',
            codigo_oficial: '3/4',
            descricao: '3/4"',
            tipo_medida: 'OD',
            nome: 'OD 3/4 — 3/4"',
          },
          dim_espessura_polegada_ref: 6,
          dim_espessura_polegada_ref_detalhes: {
            id: 6,
            codigo: '56',
            codigo_oficial: '1/4',
            descricao: '1/4"',
            tipo_medida: 'OD',
            nome: 'OD 1/4 — 1/4"',
          },
        })}
        mode="view"
      />,
    );

    expect(screen.getByText('3/4"')).toBeInTheDocument();
    expect(screen.getByText('1/4"')).toBeInTheDocument();
    expect(screen.queryByText('OD 3/4 — 3/4"')).toBeNull();
    expect(screen.queryByText('OD 1/4 — 1/4"')).toBeNull();
    expect(screen.queryByText('#5')).toBeNull();
    expect(screen.queryByText('#6')).toBeNull();
  });

  it('na aba Fiscal mantém só a unidade efetiva e traduz o tipo de composição', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    abrirAba('Fiscal');

    expect(screen.getByText('Unidade estoque efetiva')).toBeInTheDocument();
    expect(screen.getByText('Unidade fiscal efetiva')).toBeInTheDocument();
    expect(screen.queryByText('Unidade fiscal')).toBeNull();
    expect(screen.getByText(ROTULO_COMPOSICAO)).toBeInTheDocument();
  });

  it('exibe a última compra e a última venda praticadas e mantém o cadastro menor', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ ultimo_preco_compra: 900, ultimo_preco_venda: 1450.75, preco_custo: 300, preco_venda: 700 })}
        mode="view"
      />,
    );

    expect(screen.getByText('Última compra')).toBeInTheDocument();
    expect(screen.getByText('900,00')).toBeInTheDocument();
    expect(screen.getByText('1.450,75')).toBeInTheDocument();

    expect(screen.getByText('Valores do cadastro')).toBeInTheDocument();
    expect(screen.getByText('300,00')).toBeInTheDocument();
    expect(screen.getByText('700,00')).toBeInTheDocument();
    expect(screen.getByText('Preço de custo').closest('div')).toHaveTextContent(/^Preço de custo\s*300,00$/);
  });

  it('deixa o preço em branco quando o item nunca passou por uma NF-e', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ ultimo_preco_compra: null, ultimo_preco_venda: null, preco_custo: 0 })}
        mode="view"
      />,
    );

    expect(screen.getByText('Última compra').closest('div')).toHaveTextContent(/^Última compra\s*—$/);
    expect(screen.getByText('Última venda').closest('div')).toHaveTextContent(/^Última venda\s*—$/);
  });

  it('remove o campo Figura da Identificação: o nome da Família já traz o código da figura', () => {
    render(
      <ProdutoWorkspace produto={produto({ modo_codigo: 'INTERNO', figura: '0013', sufixo: 'RF' })} mode="view" />,
    );

    expect(screen.queryByText('Figura')).toBeNull();
    expect(screen.getByText(NOME_FAMILIA)).toBeInTheDocument();
    expect(screen.getByText('Sufixo')).toBeInTheDocument();
  });

  it('não repete schedule nem polegadas na Identificação mesmo com o código cru preenchido', () => {
    render(
      <ProdutoWorkspace
        produto={produto({
          modo_codigo: 'INTERNO',
          sufixo: 'RF',
          schedule: '40',
          polegada_principal: '06',
          polegada_secundaria: '1/2',
        })}
        mode="view"
      />,
    );

    const identificacao = cardPorTitulo('Identificação');
    expect(identificacao.queryByText('Schedule')).toBeNull();
    expect(identificacao.queryByText('Polegada principal')).toBeNull();
    expect(identificacao.queryByText('Polegada secundária')).toBeNull();
    expect(identificacao.getByText('Sufixo').closest('div')).toHaveTextContent(/^Sufixo\s*RF$/);
    expect(identificacao.getByText('Família')).toBeInTheDocument();
  });

  it('deixa o par resolvido de Identidade técnica como única exibição desses campos', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ schedule: '40', polegada_principal: '06', polegada_secundaria: '1/2' })}
        mode="view"
      />,
    );

    const tecnica = cardPorTitulo('Identidade técnica');
    expect(tecnica.getByText('Schedule').closest('div')).toHaveTextContent(/^Schedule\s*40$/);
    expect(tecnica.getByText('Polegada principal').closest('div')).toHaveTextContent(
      /^Polegada principal\s*1\/2"$/,
    );
    expect(tecnica.getByText('Polegada secundária')).toBeInTheDocument();
  });

  it('esconde o Sufixo vazio no modo INTERNO, deixando só a Família no bloco', () => {
    render(
      <ProdutoWorkspace produto={produto({ modo_codigo: 'INTERNO', sufixo: '' })} mode="view" />,
    );

    const identificacao = cardPorTitulo('Identificação');
    expect(identificacao.queryByText('Sufixo')).toBeNull();
    expect(identificacao.getByText('Família')).toBeInTheDocument();
    expect(identificacao.getByText(NOME_FAMILIA)).toBeInTheDocument();
  });

  it('no modo LEGADO a Identificação mostra só o Sufixo, sem as polegadas do código', () => {
    render(
      <ProdutoWorkspace
        produto={produto({
          modo_codigo: 'LEGADO',
          figura: '0013',
          sufixo: 'RF',
          schedule: '40',
          polegada_principal: '06',
          polegada_secundaria: '1/2',
        })}
        mode="view"
      />,
    );

    const identificacao = cardPorTitulo('Identificação');
    expect(screen.queryByText('Figura')).toBeNull();
    expect(identificacao.getByText('Sufixo').closest('div')).toHaveTextContent(/^Sufixo\s*RF$/);
    expect(identificacao.queryByText('Schedule')).toBeNull();
    expect(identificacao.queryByText('Polegada principal')).toBeNull();
    expect(identificacao.queryByText('Polegada secundária')).toBeNull();
  });

  it('não deixa o bloco do LEGADO virar um separador vazio quando nada está preenchido', () => {
    const { container } = render(
      <ProdutoWorkspace
        produto={produto({
          modo_codigo: 'LEGADO',
          sufixo: '',
          schedule: '',
          polegada_principal: '',
          polegada_secundaria: '',
        })}
        mode="view"
      />,
    );

    expect(container.querySelector('.border-t')).toBeNull();
  });

  it('esconde "Valores do cadastro" quando custo e venda de cadastro são zero', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ preco_custo: 0, preco_venda: 0, ultimo_preco_compra: 900 })}
        mode="view"
      />,
    );

    expect(screen.queryByText('Valores do cadastro')).toBeNull();
    expect(screen.queryByText('Preço de custo')).toBeNull();
    expect(screen.queryByText('Preço de venda')).toBeNull();
    expect(screen.getByText('Última compra').closest('div')).toHaveTextContent(/^Última compra\s*900,00$/);
  });

  it('mostra "Valores do cadastro" quando apenas um dos preços de cadastro está preenchido', () => {
    render(<ProdutoWorkspace produto={produto({ preco_custo: 0, preco_venda: 700 })} mode="view" />);

    expect(screen.getByText('Valores do cadastro')).toBeInTheDocument();
    expect(screen.getByText('Preço de venda').closest('div')).toHaveTextContent(/^Preço de venda\s*700,00$/);
  });

  it('mostra o estoque atual ao lado do estoque mínimo', () => {
    render(<ProdutoWorkspace produto={produto({ estoque_atual: 26.847, estoque_minimo: 5 })} mode="view" />);

    expect(screen.getByText('Estoque atual').closest('div')).toHaveTextContent(/^Estoque atual\s*26,847$/);
    expect(screen.getByText('Estoque mínimo').closest('div')).toHaveTextContent(/^Estoque mínimo\s*5$/);
  });

  it('mostra estoque atual zerado sem casas forçadas', () => {
    render(<ProdutoWorkspace produto={produto({ estoque_atual: 0 })} mode="view" />);

    expect(screen.getByText('Estoque atual').closest('div')).toHaveTextContent(/^Estoque atual\s*0$/);
  });

  it('põe travessão no estoque atual quando o payload não traz o campo', () => {
    render(<ProdutoWorkspace produto={produto({ estoque_atual: undefined })} mode="view" />);

    expect(screen.getByText('Estoque atual').closest('div')).toHaveTextContent(/^Estoque atual\s*—$/);
  });

  it('esconde o card de composição quando nenhum controle efetivo está ligado', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ usa_conversao_dimensional_efetivo: false, controla_composicao_fisica_efetivo: false })}
        mode="view"
      />,
    );

    expect(screen.queryByText('Composição e conversões')).toBeNull();
  });

  it('mostra o card quando a conversão dimensional efetiva está ligada', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ usa_conversao_dimensional_efetivo: true, controla_composicao_fisica_efetivo: false })}
        mode="view"
      />,
    );

    expect(screen.getByText('Composição e conversões')).toBeInTheDocument();
  });

  it('mostra o card quando a composição física efetiva está ligada', () => {
    render(
      <ProdutoWorkspace
        produto={produto({ usa_conversao_dimensional_efetivo: false, controla_composicao_fisica_efetivo: true })}
        mode="view"
      />,
    );

    expect(screen.getByText('Composição e conversões')).toBeInTheDocument();
  });

  it('decide o card pelo controle efetivo, ignorando o flag cru ligado no produto', () => {
    render(
      <ProdutoWorkspace
        produto={produto({
          usa_conversao_dimensional: true,
          controla_composicao_fisica: true,
          usa_conversao_dimensional_efetivo: false,
          controla_composicao_fisica_efetivo: false,
        })}
        mode="view"
      />,
    );

    expect(screen.queryByText('Composição e conversões')).toBeNull();
  });

  it('mostra o card herdado da família com o controle efetivo e o tipo de composição', () => {
    render(
      <ProdutoWorkspace
        produto={produto({
          usa_conversao_dimensional: false,
          controla_composicao_fisica: false,
          usa_conversao_dimensional_efetivo: true,
          controla_composicao_fisica_efetivo: true,
        })}
        mode="view"
      />,
    );

    expect(screen.getByText('Composição e conversões')).toBeInTheDocument();
    expect(screen.getByText('Controla composição física').closest('div')).toHaveTextContent(
      /^Controla composição física\s*Sim$/,
    );
    expect(screen.getByText('Usa conversão dimensional').closest('div')).toHaveTextContent(
      /^Usa conversão dimensional\s*Sim$/,
    );
    expect(screen.getByText(ROTULO_COMPOSICAO)).toBeInTheDocument();
  });
});
