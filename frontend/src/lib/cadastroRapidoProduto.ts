import type { Produto } from '@/types';

export type ProdutoQuickForm = {
  codigo_completo: string;
  descricao: string;
  unidade: string;
  ncm: string;
  material: string;
  preco_venda: string;
  preco_custo: string;
};

export function emptyProdutoQuickForm(prefill = ''): ProdutoQuickForm {
  return {
    codigo_completo: '',
    descricao: prefill,
    unidade: 'PC',
    ncm: '',
    material: 'Aço Carbono',
    preco_venda: '0',
    preco_custo: '0',
  };
}

export function validarProdutoQuickForm(q: ProdutoQuickForm): string | null {
  if (!q.codigo_completo.trim()) return 'Informe o código do produto.';
  if (!q.descricao.trim()) return 'Informe a descrição.';
  if (!q.unidade.trim()) return 'Informe a unidade.';
  const ncm = q.ncm.replace(/\D/g, '');
  if (ncm && ncm.length !== 8) return 'NCM deve ter 8 dígitos quando informado.';
  return null;
}

export function produtoQuickToPayload(q: ProdutoQuickForm): Omit<Produto, 'id'> {
  const ncm = q.ncm.replace(/\D/g, '').slice(0, 8);
  return {
    modo_codigo: 'MANUAL',
    figura: '',
    sufixo: '',
    schedule: '',
    polegada_principal: '',
    polegada_secundaria: '',
    descricao: q.descricao.trim(),
    material: q.material.trim() || 'Aço Carbono',
    tipo_peca: '',
    pressao_nominal: '',
    norma: '',
    conexao: '',
    ncm,
    unidade: q.unidade.trim().toUpperCase(),
    ncm_especifico: '',
    unidade_especifica: '',
    codigo_completo: q.codigo_completo.trim(),
    preco_venda: Number(q.preco_venda) || 0,
    preco_custo: Number(q.preco_custo) || 0,
    estoque_minimo: 0,
  } as Omit<Produto, 'id'>;
}

export const AVISO_PRODUTO_SEM_NCM =
  'Produto sem NCM pode ser usado em proposta/pedido, mas será necessário informar NCM antes da NF-e.';
