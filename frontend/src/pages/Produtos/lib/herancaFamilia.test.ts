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
  norma_tecnica: 'ASME B16.34',
  pressao_nominal: 'Class 150',
  tipo_conexao: 'Flangeada',
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

  it('usa o padrão legado da família quando o campo técnico novo está vazio', () => {
    const f = familia({
      norma_tecnica: '',
      norma_base: 'DIN 3352',
      pressao_nominal: '',
      pressao_base: 'PN 16',
      tipo_conexao: '',
      conexao_base: 'Soldável',
    });
    const { form } = aplicarHerancaFamiliaProduto(formVazio(), f, 'INTERNO');

    expect(form.norma).toBe('DIN 3352');
    expect(form.pressao_nominal).toBe('PN 16');
    expect(form.conexao).toBe('Soldável');
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

describe('herança visível', () => {
  it('valorFamiliaParaCampo respeita a precedência novo > legado', () => {
    const f = familia({ norma_tecnica: 'ASME B16.34', norma_base: 'DIN 3352' });
    expect(valorFamiliaParaCampo(f, 'norma')).toBe('ASME B16.34');
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
