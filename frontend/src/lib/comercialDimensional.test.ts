import { describe, expect, it } from 'vitest';
import { unidadesNegociacaoCompraProduto } from '@/lib/comercialDimensional';
import type { Produto } from '@/types';

function produto(partial: Partial<Produto>): Produto {
  return {
    id: 1,
    descricao: 'Tubo',
    unidade: 'BR',
    preco_custo: 0,
    preco_venda: 0,
    estoque_minimo: 0,
    codigo_completo: 'T1',
    ...partial,
  } as Produto;
}

describe('unidadesNegociacaoCompraProduto', () => {
  it('inclui M em produto dimensional BARRA_M mesmo com fallback BR', () => {
    const un = unidadesNegociacaoCompraProduto(
      produto({
        unidade_estoque_efetiva: 'BR',
        unidade_compra_efetiva: 'BR',
        usa_conversao_dimensional_efetivo: true,
        tipo_composicao_fisica_efetivo: 'BARRA_M',
        unidades_compra_permitidas: [],
      }),
    );
    expect(un).toContain('M');
    expect(un).toContain('BR');
  });

  it('respeita lista efetiva e ainda inclui M em barra dimensional', () => {
    const un = unidadesNegociacaoCompraProduto(
      produto({
        unidades_compra_permitidas_efetivas: ['BR'],
        usa_conversao_dimensional_efetivo: true,
        tipo_composicao_fisica_efetivo: 'BARRA_M',
        unidade_compra_efetiva: 'BR',
      }),
    );
    expect(un[0]).toBe('BR');
    expect(un).toContain('M');
  });
});
