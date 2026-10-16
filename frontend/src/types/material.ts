/** Types para o model Material (Sprint 3.5A+). */

export type MaterialCategoria =
  | 'ACO_CARBONO'
  | 'ACO_INOX'
  | 'FERRO_FUNDIDO'
  | 'ACO_LIGA'
  | 'NAO_FERROSO'
  | 'POLIMERO'
  | 'OUTRO';

export const MATERIAL_CATEGORIA_LABELS: Record<MaterialCategoria, string> = {
  ACO_CARBONO:   'Aço Carbono',
  ACO_INOX:      'Aço Inox',
  FERRO_FUNDIDO: 'Ferro Fundido',
  ACO_LIGA:      'Aço Liga',
  NAO_FERROSO:   'Não-ferroso',
  POLIMERO:      'Polímero',
  OUTRO:         'Outro',
};

export const MATERIAL_CATEGORIA_OPTIONS = Object.entries(MATERIAL_CATEGORIA_LABELS).map(
  ([value, label]) => ({ value: value as MaterialCategoria, label }),
);

export interface Material {
  id: number;
  codigo: string;            // read-only: MAT-0001
  nome: string;
  nome_curto: string;
  categoria: MaterialCategoria;
  norma_astm: string;
  ncm_sugerido: string;
  densidade_kg_m3: string | null;   // DecimalField vem como string da DRF
  aliases: string[];
  ativo: boolean;
  ordem: number;
  criado_em: string;
  atualizado_em: string;
  produtos_count: number;   // SerializerMethodField — read-only
}

/**
 * Subconjunto do Material embutido em Produto/FamiliaProduto via
 * *_ref_detalhes no serializer (evita depender do Material completo).
 */
export interface MaterialResumo {
  id: number;
  codigo: string;
  nome: string;
  nome_curto: string;
  categoria: MaterialCategoria;
  norma_astm: string;
  ncm_sugerido: string;
}

export type MaterialFormState = Omit<Material, 'id' | 'codigo' | 'criado_em' | 'atualizado_em' | 'produtos_count'>;

export function materialFormDefault(): MaterialFormState {
  return {
    nome: '',
    nome_curto: '',
    categoria: 'ACO_CARBONO',
    norma_astm: '',
    ncm_sugerido: '',
    densidade_kg_m3: null,
    aliases: [],
    ativo: true,
    ordem: 100,
  };
}
