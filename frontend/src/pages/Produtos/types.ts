/**
 * Tipos para a página de Produtos - Workspace migration (Fase 1)
 *
 * Padrão baseado em Colaboradores e CertificadosQualidade.
 * Estes tipos extraem as definições de estado do forms e tabs do
 * arquivo Produtos.tsx para permitir migração independente (Strangler Fig).
 */

import type {
  FamiliaProduto,
  ModoCodigoProduto,
  Produto,
  RequisitosProdutoDimensionais,
  RoscaConexao,
  ScheduleEspessura,
  TipoDimensional,
  TipoRegraCodigo,
  TipoControleUnidade,
  TipoFisicoProduto,
} from '@/types';

// --- Estados do formulário ---

/**
 * Estado do formulário de produto (sem o campo id obrigatório).
 * Correspondente ao `FormState` inline do Produtos.tsx (linha 82).
 */
export type ProdutoFormState = Omit<Produto, 'id'> & { id?: number };

/**
 * Estado do formulário rápido de família.
 * Correspondente ao retorno de `emptyFamiliaQuick()` do Produtos.tsx (linha 252).
 */
export type FamiliaQuickFormState = {
  codigo_figura: string;
  modo_codigo_figura: 'AUTOMATICO' | 'MANUAL';
  descricao_base: string;
  categoria_produto: 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE';
  tipo_regra_codigo: TipoRegraCodigo;
  tipo_dimensional: TipoDimensional;
  separador_base_medidas: string;
  ativo: boolean;
  usa_conversao_dimensional: boolean;
  controla_composicao_fisica: boolean;
  tipo_composicao_fisica: 'BARRA_M' | 'PECA_KG';
  tipo_fisico: TipoFisicoProduto | '';
  tipo_controle_unidade: TipoControleUnidade | '';
  unidade_estoque_padrao: string;
  unidade_venda_padrao: string;
  unidade_compra_padrao: string;
  unidade_fiscal_padrao: string;
  unidades_venda_permitidas: string[];
  unidades_compra_permitidas: string[];
  comprimento_padrao_barra_m: number | null;
  peso_por_metro_kg: number | null;
  peso_por_peca_kg: number | null;
  peso_por_chapa_kg: number | null;
  densidade: number | null;
  observacoes_conversao: string;
  ncm_padrao: number | null;
};

// --- Tipos de navegação (Tabs) ---

/**
 * Abas principais do workspace de produto.
 * Valor usado no `activeTab` state (linha 373 do Produtos.tsx).
 */
export type ProdutoMainTab = 'produtos' | 'familias';

/**
 * Abas da ficha do produto na página dedicada (ProdutoFormPage.tsx).
 * `configuracao` reúne Identificação + Classificação técnica na mesma aba.
 */
export type ProdutoFichaTab =
  | 'configuracao'
  | 'fiscal'
  | 'painel'
  | 'rastreabilidade'
  | 'historico';

/**
 * Modo de operação do workspace de produto.
 * Estados: create (criar), edit (editar), view (visualizar).
 */
export type ProdutoWorkspaceMode = 'create' | 'edit' | 'view';

// --- SelectOption genérico ---

/**
 * Opção genérica para campos de seleção (Select/AsyncAutocomplete).
 * Template do `SelectOption` do ui/cadastro, parametrizado com tipo T.
 */
export type SelectOption<T = string> = {
  value: T;
  label: string;
};

// --- Re-exports de @/types para conveniência ---

export type { FamiliaProduto, ModoCodigoProduto, Produto, RequisitosProdutoDimensionais, RoscaConexao, ScheduleEspessura, TipoDimensional, TipoRegraCodigo, TipoControleUnidade, TipoFisicoProduto };