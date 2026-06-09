import { describe, expect, it } from 'vitest';

import {
  formatProdutoMaterial,
  materialParaPayload,
  materialValorParaForm,
} from '@/lib/produtoMaterial';
import type { Produto } from '@/types';

describe('produtoMaterial', () => {
  it('usa material_label na listagem', () => {
    expect(
      formatProdutoMaterial({ material: 'ACO CARBONO', material_label: 'Aço Carbono' } as Produto),
    ).toBe('Aço Carbono');
  });

  it('usa material quando label ausente', () => {
    expect(formatProdutoMaterial({ material: 'ACO CARBONO' } as Produto)).toBe('Aco Carbono');
  });

  it('mostra traco quando ausente', () => {
    expect(formatProdutoMaterial({ material: '' } as Produto)).toBe('—');
  });

  it('form carrega material existente', () => {
    expect(
      materialValorParaForm({ material: 'ACO CARBONO', material_label: 'Aço Carbono' } as Produto),
    ).toBe('Aço Carbono');
  });

  it('payload preserva material em edicao sem enviar vazio', () => {
    expect(materialParaPayload('', { material: 'ACO CARBONO' } as Produto)).toEqual({});
  });

  it('payload envia material quando preenchido', () => {
    expect(materialParaPayload('Aço Inoxidável', null)).toEqual({ material: 'Aço Inoxidável' });
  });
});
