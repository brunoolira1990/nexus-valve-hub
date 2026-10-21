import { fireEvent, render, screen } from '@testing-library/react';
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

describe('ProdutoWorkspace (visualização)', () => {
  it('mostra o código completo uma única vez, dentro de Identificação', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    expect(screen.getAllByText('0013.06')).toHaveLength(1);
  });

  it('não repete o código como campo manual no modo MANUAL', () => {
    render(<ProdutoWorkspace produto={produto({ modo_codigo: 'MANUAL', familia_id: null })} mode="view" />);
    expect(screen.getAllByText('0013.06')).toHaveLength(1);
  });

  it('mostra o nome da família em vez do id do banco', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    expect(screen.getByText(NOME_FAMILIA)).toBeInTheDocument();
    expect(screen.queryByText('#94')).toBeNull();
  });

  it('na aba Classificação usa rótulos e nomes em vez de enums e ids', () => {
    render(<ProdutoWorkspace produto={produto({})} mode="view" />);
    abrirAba('Classificação industrial');

    expect(screen.getByText('Aço Carbono A105')).toBeInTheDocument();
    expect(screen.getByText('NPT')).toBeInTheDocument();
    expect(screen.getByText('40')).toBeInTheDocument();
    expect(screen.getByText('NPS 1/2 — 1/2"')).toBeInTheDocument();
    expect(screen.getByText('Dimensional')).toBeInTheDocument();
    expect(screen.getByText('Peça')).toBeInTheDocument();

    expect(screen.queryByText('ACO CARBONO')).toBeNull();
    expect(screen.queryByText('PECA')).toBeNull();
    expect(screen.queryByText('DIMENSIONAL')).toBeNull();
    expect(screen.queryByText('#12')).toBeNull();
    expect(screen.queryByText('#8')).toBeNull();
    expect(screen.queryByText('#3')).toBeNull();
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

  it('na aba Classificação mostra o nome da polegada das dimensões, não o id', () => {
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
    abrirAba('Classificação industrial');

    expect(screen.getByText('OD 3/4 — 3/4"')).toBeInTheDocument();
    expect(screen.getByText('OD 1/4 — 1/4"')).toBeInTheDocument();
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
});
