import { describe, expect, it } from 'vitest';
import { produtoParaFormState } from './produtoParaForm';
import { familiaDaFicha } from '@/types';
import type { Produto, ProdutoFamiliaDaFicha } from '@/types';

const minimo = (over: Partial<Produto> = {}): Produto =>
  ({
    id: 1,
    descricao: 'FLANGE CEGO INOX 304 1/2"',
    codigo_completo: '0013.06',
    unidade: 'PC',
    figura: '0013',
    sufixo: 'RF',
    schedule: '40',
    polegada_principal: '06',
    polegada_secundaria: '1/2',
    material: 'ACO INOX',
    tipo_peca: 'FLANGE',
    pressao_nominal: '150#',
    norma: 'ASME B16.5',
    conexao: 'SOLDAR',
    ncm: '73072100',
    tipo_controle_unidade: 'PECA',
    tipo_fisico: 'PECA',
    unidade_estoque: 'PC',
    unidade_venda_padrao: 'PC',
    unidade_compra_padrao: 'PC',
    unidade_fiscal: 'PC',
    observacoes_conversao: 'obs',
    preco_custo: 10,
    preco_venda: 20,
    estoque_minimo: 5,
    ...over,
  }) as Produto;

describe('produtoParaFormState', () => {
  it('mapeia código e descrição exatamente como o payload', () => {
    const form = produtoParaFormState(minimo());
    expect(form.descricao).toBe('FLANGE CEGO INOX 304 1/2"');
    expect(form.codigo_completo).toBe('0013.06');
    expect(form.figura).toBe('0013');
    expect(form.sufixo).toBe('RF');
    expect(form.polegada_principal).toBe('06');
    expect(form.tipo_peca).toBe('FLANGE');
    expect(form.pressao_nominal).toBe('150#');
  });

  it('usa as FKs *_ref_id que o formulário escreve, não os campos de texto', () => {
    const form = produtoParaFormState(
      minimo({
        modo_codigo: 'INTERNO',
        familia_id: 94,
        rosca_conexao_id: 12,
        schedule_ref_id: 8,
        polegada_principal_ref_id: 3,
        polegada_secundaria_ref_id: 4,
      }),
    );

    expect(form.modo_codigo).toBe('INTERNO');
    expect(form.familia_id).toBe(94);
    expect(form.rosca_conexao_id).toBe(12);
    expect(form.schedule_ref_id).toBe(8);
    expect(form.polegada_principal_ref_id).toBe(3);
    expect(form.polegada_secundaria_ref_id).toBe(4);
  });

  it('herda o tipo de composição efetivo quando o produto próprio está vazio', () => {
    const form = produtoParaFormState(
      minimo({ tipo_composicao_fisica: '', tipo_composicao_fisica_efetivo: 'PECA_KG' }),
    );
    expect(form.tipo_composicao_fisica).toBe('PECA_KG');
  });

  it('não inventa valor para campo ausente: modo vira LEGADO e as listas ficam vazias', () => {
    const form = produtoParaFormState(
      minimo({
        modo_codigo: undefined,
        familia_id: undefined,
        unidades_venda_permitidas: undefined,
        dimensoes_json: undefined,
        od_mm: undefined,
        preco_custo: undefined,
      }),
    );

    expect(form.modo_codigo).toBe('LEGADO');
    expect(form.familia_id).toBeNull();
    expect(form.unidades_venda_permitidas).toEqual([]);
    expect(form.unidades_compra_permitidas).toEqual([]);
    expect(form.dimensoes_json).toEqual({});
    expect(form.od_mm).toBeNull();
    expect(form.preco_custo).toBe(0);
  });
});

describe('familiaDaFicha', () => {
  const resumo = {
    id: 94,
    codigo_figura: '0013',
    descricao_base: 'FLANGE CEGO INOX 304',
    nome: '0013 — FLANGE CEGO INOX 304',
  };

  it('devolve null para o resumo de 4 chaves da listagem', () => {
    const produto = minimo({ familia_detalhes: resumo });
    expect(produto.familia_detalhes?.nome).toBe('0013 — FLANGE CEGO INOX 304');
    expect(familiaDaFicha(produto.familia_detalhes)).toBeNull();
  });

  it('estreita para a Família quando o payload da ficha traz requisitos_produto', () => {
    const ficha = {
      ...resumo,
      tipo_regra_codigo: 'BASE_POLEGADA',
      tipo_dimensional: 'MANOMETRO',
      material_vedacao: 'PTFE',
      requisitos_produto: {
        usa_rosca_conexao: true,
        usa_schedule: false,
        usa_polegada_principal: true,
        usa_polegada_secundaria: false,
        exige_od_mm: false,
        exige_espessura_mm: false,
        exige_comprimento_mm: false,
        exige_diametro_interno_mm: false,
        exige_diametro_mostrador_mm: true,
        incluir_schedule_na_descricao: false,
      },
    } as unknown as ProdutoFamiliaDaFicha;

    const familia = familiaDaFicha(ficha);
    expect(familia).not.toBeNull();
    expect(familia?.tipo_dimensional).toBe('MANOMETRO');
    expect(familia?.material_vedacao).toBe('PTFE');
    expect(familia?.requisitos_produto?.exige_diametro_mostrador_mm).toBe(true);
  });

  it('produto sem família continua null', () => {
    expect(familiaDaFicha(minimo({ familia_detalhes: null }).familia_detalhes)).toBeNull();
  });
});
