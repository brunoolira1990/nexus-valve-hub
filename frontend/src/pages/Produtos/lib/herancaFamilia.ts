/**
 * Herança de família -> produto, extraída de ProdutoList.tsx (linhas 305/312).
 * Funções puras (sem estado) — seguras para mover.
 */
import type { FamiliaProduto, ModoCodigoProduto } from '@/types';
import type { ProdutoFormState } from '../types';
import { normalizarTipoRegra } from '@/lib/familiaRegra';

export function familiaEhManualFabricante(familia: FamiliaProduto): boolean {
  return (
    normalizarTipoRegra(familia.tipo_regra_codigo) === 'MANUAL_FABRICANTE' ||
    familia.categoria_produto === 'MANUAL_FABRICANTE'
  );
}

export function aplicarHerancaFamiliaProduto(
  prev: ProdutoFormState,
  familia: FamiliaProduto,
  modo: ModoCodigoProduto,
  opts?: { forcarCamposIniciais?: boolean },
): ProdutoFormState {
  const forcar = opts?.forcarCamposIniciais ?? false;
  const next = { ...prev };

  const setStrSeVazio = (key: keyof ProdutoFormState, value: string | undefined | null) => {
    const v = (value || '').trim();
    if (!v) return;
    const atual = String(next[key] ?? '').trim();
    if (forcar || !atual) next[key] = v as ProdutoFormState[typeof key];
  };

  if (modo === 'INTERNO') {
    if ((forcar || !next.rosca_conexao_id) && familia.rosca_padrao_id) {
      next.rosca_conexao_id = familia.rosca_padrao_id;
    }
    if ((forcar || !next.schedule_ref_id) && familia.schedule_padrao_id) {
      next.schedule_ref_id = familia.schedule_padrao_id;
    }
  }

  if (modo === 'MANUAL') {
    setStrSeVazio('descricao', familia.descricao_base);
    setStrSeVazio('ncm', familia.ncm_padrao_info?.codigo);
  }

  setStrSeVazio('unidade', familia.unidade_padrao || familia.unidade_estoque_padrao);
  setStrSeVazio('unidade_estoque', familia.unidade_estoque_padrao);
  setStrSeVazio('unidade_venda_padrao', familia.unidade_venda_padrao);
  setStrSeVazio('unidade_compra_padrao', familia.unidade_compra_padrao);
  setStrSeVazio('unidade_fiscal', familia.unidade_fiscal_padrao);
  setStrSeVazio('material', familia.material_base);
  setStrSeVazio('pressao_nominal', familia.pressao_base);
  setStrSeVazio('norma', familia.norma_base);
  setStrSeVazio('conexao', familia.conexao_base);

  if (forcar || !(next.unidades_venda_permitidas || []).length) {
    if (familia.unidades_venda_permitidas?.length) {
      next.unidades_venda_permitidas = [...familia.unidades_venda_permitidas];
    }
  }
  if (forcar || !(next.unidades_compra_permitidas || []).length) {
    if (familia.unidades_compra_permitidas?.length) {
      next.unidades_compra_permitidas = [...familia.unidades_compra_permitidas];
    }
  }
  if ((forcar || !next.tipo_fisico) && familia.tipo_fisico) next.tipo_fisico = familia.tipo_fisico;
  if ((forcar || !next.tipo_controle_unidade) && familia.tipo_controle_unidade) {
    next.tipo_controle_unidade = familia.tipo_controle_unidade;
  }

  return next;
}
