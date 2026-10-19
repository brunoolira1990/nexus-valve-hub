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

/**
 * Campos técnicos que o produto pode receber da família e que a tela marca
 * como herdados. `fontes` é a ordem de precedência: o padrão técnico novo da
 * família vence o campo legado `*_base`.
 */
export const HERANCA_TECNICA: readonly {
  produto: 'tipo_peca' | 'norma' | 'pressao_nominal' | 'conexao';
  fontes: readonly (keyof FamiliaProduto)[];
}[] = [
  { produto: 'tipo_peca', fontes: ['tipo_peca'] },
  { produto: 'norma', fontes: ['norma_tecnica', 'norma_base'] },
  { produto: 'pressao_nominal', fontes: ['pressao_nominal', 'pressao_base'] },
  { produto: 'conexao', fontes: ['tipo_conexao', 'conexao_base'] },
];

export type CampoHerancaTecnica = (typeof HERANCA_TECNICA)[number]['produto'];

/** Campo do produto que a badge de herança também cobre (FK de material). */
export type CampoHerancaVisivel = CampoHerancaTecnica | 'material_ref';

const CAMPOS_HERDADOS_VISIVEIS = new Set<CampoHerancaVisivel>([
  'material_ref',
  'tipo_peca',
  'norma',
  'pressao_nominal',
  'conexao',
]);

/** Valor que a família oferece para um campo técnico (primeira fonte não vazia). */
export function valorFamiliaParaCampo(familia: FamiliaProduto | null, campo: CampoHerancaTecnica): string {
  if (!familia) return '';
  const spec = HERANCA_TECNICA.find((h) => h.produto === campo);
  if (!spec) return '';
  for (const fonte of spec.fontes) {
    const v = String(familia[fonte] ?? '').trim();
    if (v) return v;
  }
  return '';
}

/**
 * A badge depende da igualdade valor atual == valor da família (família com
 * valor preenchido). Isso também marca como herdado produto já salvo, sem
 * precisar de estado extra — e deixa de ser badge no primeiro caractere
 * diferente (override).
 */
export function estaHerdadoDaFamilia(
  familia: FamiliaProduto | null,
  campo: CampoHerancaVisivel,
  valorProduto: unknown
): boolean {
  if (!familia) return false;
  if (campo === 'material_ref') {
    const refFamilia = familia.material_base_ref ?? null;
    return !!refFamilia && Number(valorProduto ?? null) === refFamilia;
  }
  const v = valorFamiliaParaCampo(familia, campo);
  return !!v && v === String(valorProduto ?? '').trim();
}

export interface ResultadoHeranca {
  form: ProdutoFormState;
  /** Campos efetivamente preenchidos por esta ação de herança. */
  herdou: CampoHerancaVisivel[];
}

export function aplicarHerancaFamiliaProduto(
  prev: ProdutoFormState,
  familia: FamiliaProduto,
  modo: ModoCodigoProduto,
  opts?: { forcarCamposIniciais?: boolean },
): ResultadoHeranca {
  const forcar = opts?.forcarCamposIniciais ?? false;
  const next = { ...prev };
  const herdou = new Set<CampoHerancaVisivel>();

  // Escrita por chave variável: Object.assign evita o erro de atribuição em
  // chave union (que o cast para ProdutoFormState[typeof key] não resolvia).
  const escrever = (key: keyof ProdutoFormState, value: unknown) => {
    Object.assign(next, { [key]: value });
  };

  const setStrSeVazio = (key: keyof ProdutoFormState, value: string | undefined | null) => {
    const v = (value || '').trim();
    if (!v) return;
    const atual = String(next[key] ?? '').trim();
    if (forcar || !atual) {
      escrever(key, v);
      if (CAMPOS_HERDADOS_VISIVEIS.has(key as CampoHerancaVisivel)) {
        herdou.add(key as CampoHerancaVisivel);
      }
    }
  };

  if (modo === 'INTERNO') {
    if ((forcar || !next.rosca_conexao_id) && familia.rosca_padrao_id) {
      escrever('rosca_conexao_id', familia.rosca_padrao_id);
    }
    if ((forcar || !next.schedule_ref_id) && familia.schedule_padrao_id) {
      escrever('schedule_ref_id', familia.schedule_padrao_id);
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

  // Material: a string legada continua espelhando o nome; a FK vem do padrão
  // da família. Sem FK o produto fica fora do catálogo (a validação mínima da
  // página bloqueia em modo INTERNO).
  setStrSeVazio('material', familia.material_base);
  if ((forcar || !next.material_ref) && familia.material_base_ref) {
    escrever('material_ref', familia.material_base_ref);
    herdou.add('material_ref');
  }

  for (const { produto } of HERANCA_TECNICA) {
    setStrSeVazio(produto, valorFamiliaParaCampo(familia, produto));
  }

  if (forcar || !(next.unidades_venda_permitidas || []).length) {
    if (familia.unidades_venda_permitidas?.length) {
      escrever('unidades_venda_permitidas', [...familia.unidades_venda_permitidas]);
    }
  }
  if (forcar || !(next.unidades_compra_permitidas || []).length) {
    if (familia.unidades_compra_permitidas?.length) {
      escrever('unidades_compra_permitidas', [...familia.unidades_compra_permitidas]);
    }
  }
  if ((forcar || !next.tipo_fisico) && familia.tipo_fisico) escrever('tipo_fisico', familia.tipo_fisico);
  if ((forcar || !next.tipo_controle_unidade) && familia.tipo_controle_unidade) {
    escrever('tipo_controle_unidade', familia.tipo_controle_unidade);
  }

  return { form: next, herdou: [...herdou] };
}
