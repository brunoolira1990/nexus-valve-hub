/**
 * Constantes compartilhadas para abas de produto.
 * Extraídas de ProdutoList.tsx e ProdutoFiscalFormTab.tsx
 * para evitar importação de constantes privadas.
 */

export const MATERIAIS = [
  'Aço Carbono',
  'Aço Inox',
  'Alumínio',
  'Bronze',
  'Ferro Fundido',
  'Latão',
  'PVC',
  'PTFE',
  'Borracha',
  'Outro',
] as const;

export const ORIGEM_MERCADORIA_OPTIONS = [
  { value: '0', label: '0 - Nacional, exceto as indicadas nos códigos 3, 4, 5 e 8' },
  { value: '1', label: '1 - Estrangeira - Importação direta, exceto a indicada no código 6' },
  { value: '2', label: '2 - Estrangeira - Adquirida no mercado interno, exceto a indicada no código 7' },
  { value: '3', label: '3 - Nacional, mercadoria ou bem com Conteúdo de Importação superior a 40%' },
  { value: '4', label: '4 - Nacional, cuja produção tenha sido feita em conformidade com os processos produtivos básicos de que tratam as legislações citadas nos ajustes' },
  { value: '5', label: '5 - Nacional, mercadoria ou bem com Conteúdo de Importação inferior ou igual a 40%' },
  { value: '6', label: '6 - Estrangeira - Importação direta, sem similar nacional, constante em lista da CAMEX' },
  { value: '7', label: '7 - Estrangeira - Adquirida no mercado interno, sem similar nacional, constante em lista da CAMEX' },
  { value: '8', label: '8 - Nacional, mercadoria ou bem com Conteúdo de Importação superior a 70%' },
] as const;

// Constantes para campos que atualmente são texto livre.
// Mantidas como arrays vazios para futuras expansões (ex.: autocomplete com sugestões).
export const NORMAS: readonly string[] = [];
export const TIPOS_PECA: readonly string[] = [];
export const CONEXOES: readonly string[] = [];
export const UNIDADES: readonly string[] = [];
export const Roscas: readonly string[] = [];

// Type helpers para inferir tipos literais das constantes
export type Material = (typeof MATERIAIS)[number];
export type OrigemMercadoria = (typeof ORIGEM_MERCADORIA_OPTIONS)[number]['value'];
export type Norma = (typeof NORMAS)[number];
export type TipoPeca = (typeof TIPOS_PECA)[number];
export type Conexao = (typeof CONEXOES)[number];
export type Unidade = (typeof UNIDADES)[number];
export type Rosca = (typeof Roscas)[number];