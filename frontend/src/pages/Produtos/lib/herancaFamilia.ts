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
 * como herdados. A família guarda esses padrões nos campos `*_base`; os antigos
 * campos técnicos "novos" da família (norma_tecnica/pressao_nominal/tipo_conexao)
 * foram removidos na limpeza da Sprint 3.6.
 */
export const HERANCA_TECNICA: readonly {
  produto: 'tipo_peca' | 'norma' | 'pressao_nominal' | 'conexao';
  fontes: readonly (keyof FamiliaProduto)[];
}[] = [
  { produto: 'tipo_peca', fontes: ['tipo_peca'] },
  { produto: 'norma', fontes: ['norma_base'] },
  { produto: 'pressao_nominal', fontes: ['pressao_base'] },
  { produto: 'conexao', fontes: ['conexao_base'] },
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

/** Valores exibidos pelo card de Conversão de Medidas do produto. */
export type ValoresConversaoVisiveis = {
  usaConversao: boolean;
  controlaComposicaoFisica: boolean;
  tipoComposicaoFisica: string;
  tipoFisicoEfetivo: string;
  tipoFisico: string;
  tipoControleUnidade: string;
  unidadeEstoque: string;
  unidadeVenda: string;
  unidadeCompra: string;
  unidadeFiscal: string;
  unidadesVenda: string[];
  unidadesCompra: string[];
  comprimentoBarra: number | null;
  pesoMetro: number | null;
  pesoPeca: number | null;
  pesoChapa: number | null;
  densidade: number | null;
  observacoes: string;
};

/** Modo Manual/Legado: o produto é dono das próprias medidas. */
export function valoresConversaoProduto(form: ProdutoFormState): ValoresConversaoVisiveis {
  return {
    usaConversao: !!form.usa_conversao_dimensional,
    controlaComposicaoFisica: !!form.controla_composicao_fisica,
    tipoComposicaoFisica: form.tipo_composicao_fisica || 'BARRA_M',
    tipoFisicoEfetivo: form.tipo_fisico_efetivo || form.tipo_fisico || '',
    tipoFisico: form.tipo_fisico || '',
    tipoControleUnidade: form.tipo_controle_unidade || '',
    unidadeEstoque: form.unidade_estoque || '',
    unidadeVenda: form.unidade_venda_padrao || '',
    unidadeCompra: form.unidade_compra_padrao || '',
    unidadeFiscal: form.unidade_fiscal || '',
    unidadesVenda: form.unidades_venda_permitidas || [],
    unidadesCompra: form.unidades_compra_permitidas || [],
    comprimentoBarra: form.comprimento_padrao_barra_m ?? null,
    pesoMetro: form.peso_por_metro_kg ?? null,
    pesoPeca: form.peso_por_peca_kg ?? null,
    pesoChapa: form.peso_por_chapa_kg ?? null,
    densidade: form.densidade ?? null,
    observacoes: form.observacoes_conversao || '',
  };
}

/**
 * Com família, o card mostra o valor efetivo — o do produto quando ele tem um,
 * senão o da família. Mesma precedência de `Produto._fallback_familia_attr`
 * (`unidade_*_padrao` → `unidade_padrao`), para tela e API concordarem.
 */
export function valoresConversaoHerdados(
  form: ProdutoFormState,
  familia: FamiliaProduto,
): ValoresConversaoVisiveis {
  const texto = (produto: string | undefined, ...familiaVals: Array<string | undefined>) =>
    (produto || '').trim() || familiaVals.map((v) => (v || '').trim()).find(Boolean) || '';
  const numero = (produto: number | null | undefined, fam: number | null | undefined) =>
    produto ?? fam ?? null;
  const unidades = (produto: string[] | undefined, fam: string[] | undefined) =>
    (produto || []).length ? [...(produto || [])] : [...(fam || [])];
  const tipoFisico = texto(form.tipo_fisico, familia.tipo_fisico);
  return {
    usaConversao: !!form.usa_conversao_dimensional || !!familia.usa_conversao_dimensional,
    controlaComposicaoFisica:
      !!form.controla_composicao_fisica || !!familia.controla_composicao_fisica,
    tipoComposicaoFisica: texto(form.tipo_composicao_fisica, familia.tipo_composicao_fisica) || 'BARRA_M',
    tipoFisicoEfetivo: texto(form.tipo_fisico_efetivo, form.tipo_fisico, familia.tipo_fisico),
    tipoFisico,
    tipoControleUnidade: texto(form.tipo_controle_unidade, familia.tipo_controle_unidade),
    unidadeEstoque: texto(form.unidade_estoque, familia.unidade_estoque_padrao, familia.unidade_padrao),
    unidadeVenda: texto(form.unidade_venda_padrao, familia.unidade_venda_padrao, familia.unidade_padrao),
    unidadeCompra: texto(form.unidade_compra_padrao, familia.unidade_compra_padrao, familia.unidade_padrao),
    unidadeFiscal: texto(form.unidade_fiscal, familia.unidade_fiscal_padrao, familia.unidade_padrao),
    unidadesVenda: unidades(form.unidades_venda_permitidas, familia.unidades_venda_permitidas),
    unidadesCompra: unidades(form.unidades_compra_permitidas, familia.unidades_compra_permitidas),
    comprimentoBarra: numero(form.comprimento_padrao_barra_m, familia.comprimento_padrao_barra_m),
    pesoMetro: numero(form.peso_por_metro_kg, familia.peso_por_metro_kg),
    pesoPeca: numero(form.peso_por_peca_kg, familia.peso_por_peca_kg),
    pesoChapa: numero(form.peso_por_chapa_kg, familia.peso_por_chapa_kg),
    densidade: numero(form.densidade, familia.densidade),
    observacoes: texto(form.observacoes_conversao, familia.observacoes_conversao),
  };
}
