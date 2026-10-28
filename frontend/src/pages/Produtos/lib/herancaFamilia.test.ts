import { describe, expect, it } from 'vitest';
import type { FamiliaProduto } from '@/types';
import type { ProdutoFormState } from '../types';
import {
  aplicarHerancaFamiliaProduto,
  estaHerdadoDaFamilia,
  valorFamiliaParaCampo,
} from './herancaFamilia';

const familia = (over: Partial<FamiliaProduto> = {}) =>
  ({
    id: 7,
    codigo_figura: '6119',
    descricao_base: 'Válvula gaveta',
    tipo_regra_codigo: 'FIGURA_COMPLEMENTO',
    usa_rosca_conexao: false,
    usa_schedule: false,
    usa_polegada_principal: false,
    usa_polegada_secundaria: false,
    separador_base_medidas: '.',
    ...over,
  }) as unknown as FamiliaProduto;

const formVazio = (over: Partial<ProdutoFormState> = {}) =>
  ({
    modo_codigo: 'INTERNO',
    descricao: '',
    material: '',
    material_ref: null,
    tipo_peca: '',
    norma: '',
    pressao_nominal: '',
    conexao: '',
    unidades_venda_permitidas: [],
    unidades_compra_permitidas: [],
    ...over,
  }) as unknown as ProdutoFormState;

const familiaTecnica = familia({
  material_base: 'Aço Carbono',
  material_base_ref: 42,
  tipo_peca: 'Válvula',
  norma_base: 'ASME B16.34',
  pressao_base: 'Class 150',
  conexao_base: 'Flangeada',
});

describe('aplicarHerancaFamiliaProduto — campos técnicos', () => {
  it('herda material_ref e os 4 campos técnicos, reportando a lista', () => {
    const { form, herdou } = aplicarHerancaFamiliaProduto(formVazio(), familiaTecnica, 'INTERNO');

    expect(form.material_ref).toBe(42);
    expect(form.material).toBe('Aço Carbono');
    expect(form.tipo_peca).toBe('Válvula');
    expect(form.norma).toBe('ASME B16.34');
    expect(form.pressao_nominal).toBe('Class 150');
    expect(form.conexao).toBe('Flangeada');
    expect(new Set(herdou)).toEqual(
      new Set(['material_ref', 'tipo_peca', 'norma', 'pressao_nominal', 'conexao'])
    );
  });

  it('nada herda quando a família não tem padrão preenchido', () => {
    const f = familia({
      norma_base: '',
      pressao_base: '',
      conexao_base: '',
    });
    const { form, herdou } = aplicarHerancaFamiliaProduto(formVazio(), f, 'INTERNO');

    expect(form.norma).toBe('');
    expect(form.pressao_nominal).toBe('');
    expect(form.conexao).toBe('');
    expect(herdou).not.toContain('norma');
    expect(herdou).not.toContain('pressao_nominal');
    expect(herdou).not.toContain('conexao');
  });

  it('não sobrescreve override já digitado no produto', () => {
    const prev = formVazio({ norma: 'ASME B16.5' });
    const { form, herdou } = aplicarHerancaFamiliaProduto(prev, familiaTecnica, 'INTERNO');

    expect(form.norma).toBe('ASME B16.5');
    expect(herdou).not.toContain('norma');
    expect(herdou).toContain('tipo_peca');
  });

  it('não inventa material_ref quando a família não tem padrão', () => {
    const { form, herdou } = aplicarHerancaFamiliaProduto(
      formVazio(),
      familia({ material_base: 'Bronze', material_base_ref: null }),
      'INTERNO'
    );

    expect(form.material).toBe('Bronze');
    expect(form.material_ref).toBeNull();
    expect(herdou).not.toContain('material_ref');
  });
});

describe('aplicarHerancaFamiliaProduto — medidas só no produto novo', () => {
  const familiaMedidas = familia({ rosca_padrao_id: 12, schedule_padrao_id: 8 });

  it('pré-seleciona rosca e schedule do molde no produto novo', () => {
    const { form } = aplicarHerancaFamiliaProduto(formVazio(), familiaMedidas, 'INTERNO');

    expect(form.rosca_conexao_id).toBe(12);
    expect(form.schedule_ref_id).toBe(8);
  });

  // O código do produto é montado a partir das FKs dele (codigo_produto.py). Se a
  // herança escrevesse o padrão da família num SKU salvo, abrir a Edição e salvar
  // bastaria para o backend recalcular o codigo_completo daquele produto.
  it('não escreve rosca nem schedule no produto já salvo (escreverMedidas: false)', () => {
    const { form, herdou } = aplicarHerancaFamiliaProduto(
      formVazio({ rosca_conexao_id: null, schedule_ref_id: null }),
      familiaMedidas,
      'INTERNO',
      { escreverMedidas: false },
    );

    expect(form.rosca_conexao_id).toBeNull();
    expect(form.schedule_ref_id).toBeNull();
    expect(herdou).not.toContain('norma');
  });

  it('não afeta a herança técnica quando escreverMedidas é false', () => {
    const { form } = aplicarHerancaFamiliaProduto(
      formVazio(),
      familiaTecnica,
      'INTERNO',
      { escreverMedidas: false },
    );

    expect(form.material_ref).toBe(42);
    expect(form.norma).toBe('ASME B16.34');
  });
});

describe('herança visível', () => {
  it('valorFamiliaParaCampo lê o padrão da família', () => {
    const f = familia({ norma_base: 'DIN 3352' });
    expect(valorFamiliaParaCampo(f, 'norma')).toBe('DIN 3352');
  });

  it('badge aparece com valor igual ao da família e some no override', () => {
    expect(estaHerdadoDaFamilia(familiaTecnica, 'norma', 'ASME B16.34')).toBe(true);
    expect(estaHerdadoDaFamilia(familiaTecnica, 'norma', '  ASME B16.34  ')).toBe(true);
    expect(estaHerdadoDaFamilia(familiaTecnica, 'norma', 'ASME B16.5')).toBe(false);
    expect(estaHerdadoDaFamilia(familiaTecnica, 'norma', '')).toBe(false);
  });

  it('badge de material depende da FK da família', () => {
    expect(estaHerdadoDaFamilia(familiaTecnica, 'material_ref', 42)).toBe(true);
    expect(estaHerdadoDaFamilia(familiaTecnica, 'material_ref', 7)).toBe(false);
    expect(estaHerdadoDaFamilia(familia({ material_base_ref: null }), 'material_ref', 42)).toBe(false);
  });

  it('família sem valor nunca marca como herdado', () => {
    const f = familia({ tipo_peca: '' });
    expect(estaHerdadoDaFamilia(f, 'tipo_peca', '')).toBe(false);
    expect(estaHerdadoDaFamilia(null, 'tipo_peca', 'Válvula')).toBe(false);
  });
});
