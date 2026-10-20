/**
 * Derivações puras a partir da família selecionada, extraídas dos useMemo locais
 * de ProdutoList.tsx (linhas 547–657). Consumidas principalmente pela aba
 * Classificação (Rodada 2); getFamReq também alimenta a página container.
 *
 * Na página, embrulhe cada uma em useMemo(() => getX(familiaSel), [familiaSel])
 * para preservar a memoização que o modal já tinha.
 */
import type { FamiliaProduto, RequisitosProdutoDimensionais } from '@/types';
import { flagsPorTipoRegra, normalizarTipoRegra } from '@/lib/familiaRegra';
import {
  DESCRICAO_TOKENS_TECNICOS,
  tokensDescricaoTecnicaConfigurados,
} from '@/lib/familiaRegra';

export function getFamReq(
  familiaSel: FamiliaProduto | null,
): RequisitosProdutoDimensionais | null {
  if (!familiaSel) return null;
  if (familiaSel.requisitos_produto) return familiaSel.requisitos_produto;
  const fl = flagsPorTipoRegra(
    normalizarTipoRegra(familiaSel.tipo_regra_codigo) || familiaSel.tipo_regra_codigo,
  );
  return {
    usa_rosca_conexao: fl.usa_rosca_conexao,
    usa_schedule: fl.usa_schedule,
    usa_polegada_principal: fl.usa_polegada_principal,
    usa_polegada_secundaria: fl.usa_polegada_secundaria,
    exige_od_mm: false,
    exige_espessura_mm: false,
    exige_comprimento_mm: false,
    exige_diametro_interno_mm: false,
    exige_diametro_mostrador_mm: false,
    incluir_schedule_na_descricao: fl.usa_schedule,
  };
}

export function getTdAtual(familiaSel: FamiliaProduto | null) {
  return familiaSel?.tipo_dimensional;
}

const TD_MATERIAIS = [
  'CHAPA_MM',
  'CHAPA_FURO_MM',
  'BARRA_CHATA_MM',
  'METALON_MM',
  'PERFIL_RETANGULAR_MM',
  'CANTONEIRA_MM',
  'CANTONEIRA_POLEGADA',
  'DIMENSIONAL_LIVRE_CONTROLADO',
];

export function getUsaDimensoesMateriais(familiaSel: FamiliaProduto | null): boolean {
  const td = familiaSel?.tipo_dimensional;
  return !!td && TD_MATERIAIS.includes(td);
}

export function getLabelCampoOdPrincipal(familiaSel: FamiliaProduto | null): string {
  const td = familiaSel?.tipo_dimensional;
  if (td === 'DN_MM') return 'Medida DN/MM';
  if (td === 'DN_MM_REDUCAO') return 'Medida maior DN/MM';
  if (td === 'OD_MM_REDUCAO') return 'OD maior (mm)';
  if (td === 'OD_MM' && familiaSel?.tipo_regra_codigo === 'BASE_OD_MM') return 'Medida OD/mm';
  return 'OD externo (mm)';
}

export function getLabelCampoEspessuraOuMenor(familiaSel: FamiliaProduto | null): string {
  const td = familiaSel?.tipo_dimensional;
  if (td === 'DN_MM_REDUCAO') return 'Medida menor DN/MM';
  if (td === 'OD_MM_REDUCAO') return 'OD menor (mm)';
  return 'Espessura (mm)';
}

/** Chaves de manômetro que hoje são colunas do Produto e não passam mais por dimensoes_json. */
const CHAVES_MANOMETRO_EM_COLUNA = new Set(['escala', 'unidade_escala', 'fluido']);

export function getAtributosTecnicosFamilia(familiaSel: FamiliaProduto | null) {
  if (familiaSel?.tipo_dimensional === 'MANOMETRO') {
    return DESCRICAO_TOKENS_TECNICOS.filter(({ key }) => !CHAVES_MANOMETRO_EM_COLUNA.has(key));
  }
  return tokensDescricaoTecnicaConfigurados(familiaSel?.descricao_base);
}
