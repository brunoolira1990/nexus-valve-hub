import { describe, expect, it } from 'vitest';

import {
  clienteQuickToPayload,
  emptyClienteQuickForm,
  validarClienteQuickForm,
} from '@/lib/cadastroRapidoCliente';
import {
  emptyProdutoQuickForm,
  produtoQuickToPayload,
  validarProdutoQuickForm,
} from '@/lib/cadastroRapidoProduto';
import { itemPedidoQuantidadeEditavel, pedidoItensBloqueados } from '@/lib/nfeSaidaUi';
import { inputNumberValue } from '@/lib/numberFormat';

describe('cadastroRapido40136', () => {
  it('valida cliente quick com CNPJ obrigatório', () => {
    expect(validarClienteQuickForm(emptyClienteQuickForm())).toMatch(/CNPJ/);
    const ok = { ...emptyClienteQuickForm(), razao_social: 'Teste', cnpj: '03.999.102/0001-50' };
    expect(validarClienteQuickForm(ok)).toBeNull();
  });

  it('monta payload de produto manual', () => {
    const q = { ...emptyProdutoQuickForm(), codigo_completo: 'X1', descricao: 'Prod' };
    const p = produtoQuickToPayload(q);
    expect(p.modo_codigo).toBe('MANUAL');
    expect(p.codigo_completo).toBe('X1');
  });

  it('produto quick exige código e descrição', () => {
    expect(validarProdutoQuickForm(emptyProdutoQuickForm())).toMatch(/código/i);
  });

  it('inputNumberValue evita NaN no campo quantidade', () => {
    expect(inputNumberValue(10)).toBe(10);
    expect(inputNumberValue(undefined, 1)).toBe('');
  });

  it('quantidade editável só em pedido aberto', () => {
    expect(pedidoItensBloqueados('FATURADO')).toBe(true);
    expect(itemPedidoQuantidadeEditavel({ status_item: 'PENDENTE' }, 'ABERTO')).toBe(true);
    expect(itemPedidoQuantidadeEditavel({ status_item: 'PENDENTE' }, 'FATURADO')).toBe(false);
  });

  it('clienteQuickToPayload normaliza campos mínimos', () => {
    const p = clienteQuickToPayload({
      ...emptyClienteQuickForm(),
      razao_social: 'ACME',
      cnpj: '03.999.102/0001-50',
    });
    expect(p.razao_social).toBe('ACME');
    expect(p.ativo).toBe(true);
  });
});
