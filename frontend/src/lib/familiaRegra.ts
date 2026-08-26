import type { FamiliaProduto, RequisitosProdutoDimensionais, TipoDimensional, TipoRegraCodigo } from '@/types';
import { normalizarDescricaoProduto } from '@/lib/descricaoProduto';

export const DESCRICAO_TOKEN_POLEGADA_PRINCIPAL = '[P]';

export const DESCRICAO_TOKENS_TECNICOS = [
  { token: '[ESCALA]', key: 'escala', label: 'Escala', hint: 'Ex.: 0 A 4' },
  { token: '[UNIDADE]', key: 'unidade_escala', label: 'Unidade da escala', hint: 'Ex.: BAR' },
  { token: '[PONTEIRO]', key: 'ponteiro', label: 'Ponteiro', hint: 'Ex.: MICROMÉTRICO' },
  { token: '[VIDRO]', key: 'vidro', label: 'Vidro', hint: 'Ex.: SAFETY GLASS' },
  { token: '[CLASSE]', key: 'classe', label: 'Classe', hint: 'Ex.: A1' },
  { token: '[FLUIDO]', key: 'fluido', label: 'Fluido / preenchimento', hint: 'Ex.: GLICERINA' },
  { token: '[CERTIFICACAO]', key: 'certificacao', label: 'Certificação', hint: 'Ex.: RBC INMETRO' },
] as const;

export type TokenDescricaoTecnica = (typeof DESCRICAO_TOKENS_TECNICOS)[number];

export function tokensDescricaoTecnicaConfigurados(descricaoBase: string | undefined | null): TokenDescricaoTecnica[] {
  const base = (descricaoBase || '').toUpperCase();
  return DESCRICAO_TOKENS_TECNICOS.filter(({ token }) => base.includes(token));
}

export type CategoriaProdutoSugestao = 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE';

export type SugestaoConfiguracaoFamilia = {
  categoria_produto: CategoriaProdutoSugestao;
  tipo_dimensional: TipoDimensional;
  tipo_regra_codigo: TipoRegraCodigo;
  campos_obrigatorios_labels: string[];
  observacao?: string;
};

export type FlagsFamilia = {
  usa_rosca_conexao: boolean;
  usa_schedule: boolean;
  usa_polegada_principal: boolean;
  usa_polegada_secundaria: boolean;
};

const TABLE: Record<TipoRegraCodigo, FlagsFamilia> = {
  BASE_POLEGADA: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: false },
  BASE_ROSCA_POLEGADA: { usa_rosca_conexao: true, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: false },
  BASE_DUAS_POLEGADAS: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: true },
  BASE_ROSCA_DUAS_POLEGADAS: { usa_rosca_conexao: true, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: true },
  BASE_SCHEDULE_POLEGADA: { usa_rosca_conexao: false, usa_schedule: true, usa_polegada_principal: true, usa_polegada_secundaria: false },
  BASE_SCHEDULE_DUAS_POLEGADAS: { usa_rosca_conexao: false, usa_schedule: true, usa_polegada_principal: true, usa_polegada_secundaria: true },
  BASE_ROSCA_SCHEDULE_POLEGADA: { usa_rosca_conexao: true, usa_schedule: true, usa_polegada_principal: true, usa_polegada_secundaria: false },
  BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS: { usa_rosca_conexao: true, usa_schedule: true, usa_polegada_principal: true, usa_polegada_secundaria: true },
  UNDERSCORE_POLEGADA: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: false },
  BASE_OD_MM_ESPESSURA: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: false, usa_polegada_secundaria: false },
  BASE_OD_POLEGADA_ESPESSURA: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: false },
  BASE_DN_MM: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: false, usa_polegada_secundaria: false },
  BASE_DN_MM_REDUCAO: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: false, usa_polegada_secundaria: false },
  BASE_BITOLA_POLEGADA: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: false },
  BASE_OD_MM: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: false, usa_polegada_secundaria: false },
  BASE_OD_MM_REDUCAO: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: false, usa_polegada_secundaria: false },
  BASE_OD_MM_X_ROSCA: { usa_rosca_conexao: true, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: false },
  BASE_ESPIGAO_FLANGE_NPS: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: true },
  MANUAL_FABRICANTE: { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: false, usa_polegada_secundaria: false },
};

/** Mapeia tipos antigos da API (pré-migração) para os novos códigos. */
const LEGACY_MAP: Partial<Record<string, TipoRegraCodigo>> = {
  BASE_PP: 'BASE_POLEGADA',
  BASE_ROSCA_PP: 'BASE_ROSCA_POLEGADA',
  BASE_DOIS_P: 'BASE_DUAS_POLEGADAS',
  BASE_ROSCA_DOIS_P: 'BASE_ROSCA_DUAS_POLEGADAS',
  BASE_SCHED_PP: 'BASE_SCHEDULE_POLEGADA',
  BASE_SCHED_DOIS_P: 'BASE_SCHEDULE_DUAS_POLEGADAS',
  BASE_UNDERSCORE_P: 'UNDERSCORE_POLEGADA',
};

export function normalizarTipoRegra(tipo: string | undefined | null): TipoRegraCodigo | null {
  if (!tipo) return null;
  if (tipo in TABLE) return tipo as TipoRegraCodigo;
  const m = LEGACY_MAP[tipo];
  return m ?? null;
}

export function flagsPorTipoRegra(tipo: string | undefined | null): FlagsFamilia {
  const n = normalizarTipoRegra(tipo);
  if (!n) {
    return { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: false };
  }
  return TABLE[n];
}

export function labelsCamposObrigatorios(flags: FlagsFamilia, td?: TipoDimensional | null): string[] {
  const r: string[] = [];
  if (flags.usa_rosca_conexao) r.push('Rosca / conexão');
  if (flags.usa_schedule) r.push('Schedule / espessura');
  if (flags.usa_polegada_principal) {
    r.push(
      td === 'ESPIGAO_X_FLANGE'
        ? 'Medida do espigão (NPS)'
        : td === 'BITOLA_POLEGADA' || td === 'OD_MM_X_ROSCA'
          ? 'Bitola'
          : 'Polegada principal (ID)',
    );
  }
  if (flags.usa_polegada_secundaria) {
    r.push(td === 'ESPIGAO_X_FLANGE' ? 'Medida da flange (NPS)' : 'Polegada secundária (ID)');
  }
  const extra: string[] = [];
  if (td === 'DN_MM') extra.push('Medida DN/MM');
  if (td === 'DN_MM_REDUCAO') {
    extra.push('Medida maior DN/MM');
    extra.push('Medida menor DN/MM');
  }
  if (td === 'OD_MM_REDUCAO') {
    extra.push('OD maior (mm)');
    extra.push('OD menor (mm)');
  }
  if (td === 'OD_MM') extra.push('Medida OD/mm');
  if (td === 'OD_POLEGADA_X_ESPESSURA') extra.push('Espessura (mm)');
  if (td === 'OD_MM_X_ROSCA') extra.push('Medida OD/mm');
  const out = [...r, ...extra];
  if (out.length === 0) out.push('Nenhum (código manual no produto)');
  return out;
}

/** Texto curto explicando o tipo dimensional (UI família/produto). */
export function hintTipoDimensional(td: TipoDimensional | undefined | null): string {
  switch (td) {
    case 'NPS_SCHEDULE':
    case 'REDUCAO_NPS':
      return 'NPS/SCH — usa Schedule + polegada(s) nominal(is). OD não é NPS/SCH.';
    case 'OD_POLEGADA':
      return 'OD em polegada — medida OD no cadastro mestre de polegadas; sem schedule.';
    case 'OD_POLEGADA_X_ESPESSURA':
      return 'OD em polegada + espessura mm — fração preservada na descrição (ex.: OD 1/2" x 1,50 mm).';
    case 'OD_POLEGADA_X_ROSCA':
      return 'OD x Rosca — medida OD + tipo de rosca + medida da rosca; sem schedule.';
    case 'OD_MM':
    case 'OD_MM_X_ESPESSURA':
    case 'OD_MM_X_ESPESSURA_X_COMPRIMENTO':
      return 'OD em mm — valores numéricos (mm); use regra 11 no código; sem NPS/SCH.';
    case 'DN_MM':
      return 'DN/mm — medida única em milímetros (PVC/CPVC/PPR); sem schedule industrial.';
    case 'DN_MM_REDUCAO':
      return 'DN/mm redução — duas medidas em mm (maior × menor); sem schedule industrial.';
    case 'BITOLA_POLEGADA':
      return 'Bitola — medida em polegada pela tabela oficial (condulete); rótulo Bitola, não NPS industrial.';
    case 'OD_MM_REDUCAO':
      return 'PU / pneumático — OD maior × menor em mm.';
    case 'OD_MM_X_ROSCA':
      return 'PU / pneumático — OD em mm com rosca e bitola (push-in); sem NPS/schedule industrial.';
    case 'CHAPA_MM':
      return 'Chapa mm — espessura, largura e comprimento (prévia assistida).';
    case 'CHAPA_FURO_MM':
      return 'Chapa com furo mm — furo, espessura, largura e comprimento.';
    case 'BARRA_CHATA_MM':
      return 'Barra chata mm — largura e espessura (comprimento opcional).';
    case 'METALON_MM':
      return 'Metalon mm — altura, largura e espessura.';
    case 'CANTONEIRA_MM':
      return 'Cantoneira mm — aba e espessura (comprimento opcional).';
    case 'CANTONEIRA_POLEGADA':
      return 'Cantoneira polegada — aba e espessura em polegada (tabela de medidas).';
    case 'DIMENSIONAL_LIVRE_CONTROLADO':
      return 'Dimensional livre controlado — campos estruturados sem NPS/SCH/OD técnico.';
    case 'PERFIL_RETANGULAR_MM':
      return 'Perfil retangular mm — preparado para fluxo dimensional assistido.';
    case 'NPS_X_ROSCA':
      return 'NPS x Rosca — polegada nominal com rosca no código (regra 2).';
    case 'ESPIGAO_X_FLANGE':
      return 'Espigão x Flange — duas medidas NPS da tabela oficial; código E…F….';
    default:
      return 'Tipo dimensional orienta rótulos e obrigatoriedade; a regra de código monta o código.';
  }
}

export function labelPolegadaPrincipal(td: TipoDimensional | undefined | null): string {
  if (td === 'ESPIGAO_X_FLANGE') return 'Medida do espigão';
  if (td === 'OD_POLEGADA' || td === 'OD_POLEGADA_X_ESPESSURA' || td === 'OD_POLEGADA_X_ROSCA') return 'Medida OD (cadastro mestre)';
  if (td === 'CANTONEIRA_POLEGADA') return 'Aba em polegada';
  if (td === 'BITOLA_POLEGADA' || td === 'OD_MM_X_ROSCA') return 'Bitola';
  if (td === 'NPS_SCHEDULE' || td === 'NPS') return 'Polegada nominal (NPS)';
  if (td === 'REDUCAO_NPS') return 'Polegada maior';
  return 'Polegada principal (código oficial)';
}

export function labelPolegadaSecundaria(td: TipoDimensional | undefined | null): string {
  if (td === 'ESPIGAO_X_FLANGE') return 'Medida da flange';
  if (td === 'REDUCAO_NPS') return 'Polegada menor';
  if (td === 'OD_POLEGADA_X_ROSCA') return 'Medida da rosca';
  if (td === 'CANTONEIRA_POLEGADA') return 'Espessura em polegada';
  return 'Polegada secundária (redução / segunda medida)';
}

/** Campos obrigatórios no produto após combinar API requisitos_produto + tipo dimensional (rótulos). */
export function labelsCamposObrigatoriosProduto(familia: FamiliaProduto | null): string[] {
  if (!familia) return [];
  const req: RequisitosProdutoDimensionais | undefined = familia.requisitos_produto;
  const td = familia.tipo_dimensional;
  if (!req) {
    return labelsCamposObrigatorios(flagsPorTipoRegra(familia.tipo_regra_codigo), td);
  }
  const r: string[] = [];
  if (req.usa_schedule) r.push('Schedule / espessura');
  if (req.usa_rosca_conexao) r.push('Rosca / conexão');
  if (req.usa_polegada_principal) r.push(labelPolegadaPrincipal(td));
  if (req.usa_polegada_secundaria) r.push(labelPolegadaSecundaria(td));
  if (req.exige_od_mm) {
    if (td === 'DN_MM') r.push('Medida DN/MM');
    else if (td === 'DN_MM_REDUCAO') r.push('Medida maior DN/MM');
    else if (td === 'OD_MM_REDUCAO') r.push('OD maior (mm)');
    else if (td === 'OD_MM' && familia.tipo_regra_codigo === 'BASE_OD_MM') r.push('Medida OD/mm');
    else r.push('OD externo (mm)');
  }
  if (req.exige_espessura_mm) {
    if (td === 'DN_MM_REDUCAO') r.push('Medida menor DN/MM');
    else if (td === 'OD_MM_REDUCAO') r.push('OD menor (mm)');
    else r.push('Espessura (mm)');
  }
  if (req.exige_comprimento_mm) r.push('Comprimento (mm ou padrão da família)');
  if (r.length === 0) r.push('Nenhum campo automático (ver modo manual)');
  return r;
}

/** Espigão × flange (E…F…): mesma regra do backend `familia_espigao_x_flange_nps`. */
export function familiaEhEspigaoFlangeNps(td: TipoDimensional | undefined | null, tipoRegra: string | undefined | null): boolean {
  const n = normalizarTipoRegra(tipoRegra);
  return td === 'ESPIGAO_X_FLANGE' || n === 'BASE_ESPIGAO_FLANGE_NPS';
}

/** Expansão fixa VEM/VEB/VET no início (igual ao backend em `codigo_produto`). */
export function expandirSiglasValvulaDescricaoBase(descricaoBase: string): string {
  const raw = (descricaoBase || '').trim();
  if (!raw) return '';
  const upper = raw.toUpperCase();
  const pairs: [string, string][] = [
    ['VET ', 'VALVULA ESFERA TRIPARTIDA '],
    ['VEB ', 'VALVULA ESFERA BIPARTIDA '],
    ['VEM ', 'VALVULA ESFERA MONOBLOCO '],
  ];
  for (const [pref, repl] of pairs) {
    if (upper.startsWith(pref)) {
      const rest = raw.slice(pref.length).trimStart();
      return `${repl}${rest}`.replace(/\s+/g, ' ').trim();
    }
  }
  const exact: [string, string][] = [
    ['VET', 'VALVULA ESFERA TRIPARTIDA'],
    ['VEB', 'VALVULA ESFERA BIPARTIDA'],
    ['VEM', 'VALVULA ESFERA MONOBLOCO'],
  ];
  for (const [tok, repl] of exact) {
    if (upper === tok) return repl;
  }
  return raw;
}

/** Coerência tipo dimensional → regra (espelha `regraSugeridaPorTipoDimensional` da página Produtos). */
export function sugerirTipoRegraPorDimensional(td: TipoDimensional): TipoRegraCodigo {
  if (td === 'DN_MM') return 'BASE_DN_MM';
  if (td === 'DN_MM_REDUCAO') return 'BASE_DN_MM_REDUCAO';
  if (td === 'BITOLA_POLEGADA') return 'BASE_BITOLA_POLEGADA';
  if (td === 'OD_MM_REDUCAO') return 'BASE_OD_MM_REDUCAO';
  if (td === 'OD_MM_X_ROSCA') return 'BASE_OD_MM_X_ROSCA';
  if (td === 'OD_MM') return 'BASE_OD_MM';
  if (td === 'NPS_SCHEDULE') return 'BASE_SCHEDULE_POLEGADA';
  if (td === 'REDUCAO_NPS') return 'BASE_SCHEDULE_DUAS_POLEGADAS';
  if (td === 'OD_POLEGADA') return 'BASE_POLEGADA';
  if (td === 'OD_POLEGADA_X_ESPESSURA') return 'BASE_OD_POLEGADA_ESPESSURA';
  if (td === 'OD_POLEGADA_X_ROSCA') return 'BASE_ROSCA_DUAS_POLEGADAS';
  if (td === 'OD_MM_X_ESPESSURA' || td === 'OD_MM_X_ESPESSURA_X_COMPRIMENTO') return 'BASE_OD_MM_ESPESSURA';
  if (td === 'NPS_X_ROSCA') return 'BASE_ROSCA_POLEGADA';
  if (td === 'ESPIGAO_X_FLANGE') return 'BASE_ESPIGAO_FLANGE_NPS';
  if (td === 'CANTONEIRA_POLEGADA') return 'BASE_POLEGADA';
  if (td === 'ROSCA_X_ROSCA') return 'BASE_ROSCA_DUAS_POLEGADAS';
  if (td === 'MANUAL') return 'MANUAL_FABRICANTE';
  return 'BASE_POLEGADA';
}

function _norm(s: string): string {
  return normalizarDescricaoProduto(s);
}

function _has(u: string, re: RegExp): boolean {
  return re.test(u);
}

/**
 * Heurística a partir da descrição base da família; o usuário pode ajustar depois.
 * Regras alinhadas ao pedido operacional (material, OD, NPS×rosca, redução, flange, válvula, tubo…).
 */
export function sugerirConfiguracaoFamilia(descricaoBase: string): SugestaoConfiguracaoFamilia {
  const raw = (descricaoBase || '').trim();
  if (!raw) {
    const td: TipoDimensional = 'SIMPLES';
    const tr = sugerirTipoRegraPorDimensional(td);
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Digite a descrição base para obter uma sugestão.',
    };
  }

  const u0 = _norm(raw);
  const u = _norm(expandirSiglasValvulaDescricaoBase(raw));

  const fab = _has(
    u,
    /\b(JEFFERSON|DANFOSS|VALMICRO|SOLENOIDE|ATUADOR|CONECTOR CABO|MANOMETRO|KIT REPARO|KIT TEFLON|ALAVANCA|JUNTA|MANGUEIRA|ABRACADEIRA|ABRAÇADEIRA|PARAFUSO|PORCA|ARRUELA|GRAMPO|FOLHA TEADIT)\b/,
  );
  if (fab) {
    const td: TipoDimensional = 'MANUAL';
    const tr: TipoRegraCodigo = 'MANUAL_FABRICANTE';
    return {
      categoria_produto: 'MANUAL_FABRICANTE',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Descrição sugere item de fabricante/manual — revise NCM e unidade.',
    };
  }

  const mat = _has(u, /\b(CHAPA|BARRA CHATA|METALON|CANTONEIRA|TARUGO|PERFIL|TUBO QUADRADO)\b/);
  if (mat) {
    let td: TipoDimensional = 'DIMENSIONAL_LIVRE_CONTROLADO';
    let hint = 'Material dimensional — refine o tipo (chapa, barra, metalon…).';
    if (_has(u, /\bCHAPA\b/) && _has(u, /\b(FURO|MOEDA)\b/)) {
      td = 'CHAPA_FURO_MM';
      hint = 'Chapa com furo — espessura, largura e comprimento em mm.';
    } else if (_has(u, /\bCHAPA\b/)) {
      td = 'CHAPA_MM';
      hint = 'Chapa — espessura × largura × comprimento (mm).';
    } else if (_has(u, /\bBARRA CHATA\b/)) {
      td = 'BARRA_CHATA_MM';
      hint = 'Barra chata mm.';
    } else if (_has(u, /\bMETALON\b/)) {
      td = 'METALON_MM';
      hint = 'Metalon mm.';
    } else if (_has(u, /\bCANTONEIRA\b/)) {
      td = /\bCANTONEIRA\b.*\bPOLEGADA\b/i.test(u) ? 'CANTONEIRA_POLEGADA' : 'CANTONEIRA_MM';
      hint = td === 'CANTONEIRA_POLEGADA' ? 'Cantoneira em polegada (aba × espessura).' : 'Cantoneira mm.';
    } else if (_has(u, /\b(TARUGO|PERFIL)\b/)) {
      td = 'DIMENSIONAL_LIVRE_CONTROLADO';
      hint = 'Tarugo/perfil — dimensional livre controlado ou ajuste manual.';
    }
    const tr = sugerirTipoRegraPorDimensional(td);
    return {
      categoria_produto: 'MATERIAL_DIMENSIONAL',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: hint,
    };
  }

  if (_has(u, /\bESPIG\w*\s+.*\bFLANGE\b/) || _has(u, /\bESPIGAO\b.*\bFLANGE\b/) || _has(u0, /\bESP\s+X\s+FL\b/i)) {
    const td: TipoDimensional = 'ESPIGAO_X_FLANGE';
    const tr = sugerirTipoRegraPorDimensional(td);
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Espigão × flange — duas medidas NPS (espigão e flange).',
    };
  }

  const roscaKw = /\b(BSP|NPT|SW|ROSCA|M-F|F-M|MACHO|FEMEA|FÊMEA)\b/;

  if (_has(u, /\bCONDULETE\b/)) {
    const td: TipoDimensional = 'BITOLA_POLEGADA';
    const tr: TipoRegraCodigo = 'BASE_BITOLA_POLEGADA';
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Condulete — campo Bitola (tabela de polegadas), sem NPS/schedule industrial.',
    };
  }

  const puLine =
    /\b(PU|PUSH-IN|PUSH\s+IN|ENGATE\s+RAPIDO|ENGATE\s+RÁPIDO|DUPLA\s+ANILHA|PNEUMATICO|PNEUMÁTICO|CONECTOR\s+MACHO\s+PU|CONECTOR\s+FEMEA\s+PU|COTOVELO\s+MACHO\s+GIR\s+PU|UNI(AO|ÃO)\s+PU|MANGUEIRA\s+AZUL\s+PU)\b/i;
  if (_has(u, puLine)) {
    const reduPu = _has(u, /\b(REDU(CAO|ÇÃO))\b/);
    const roscaPu = _has(u, roscaKw);
    let td: TipoDimensional;
    let tr: TipoRegraCodigo;
    if (reduPu) {
      td = 'OD_MM_REDUCAO';
      tr = 'BASE_OD_MM_REDUCAO';
    } else if (roscaPu) {
      td = 'OD_MM_X_ROSCA';
      tr = 'BASE_OD_MM_X_ROSCA';
    } else {
      td = 'OD_MM';
      tr = 'BASE_OD_MM';
    }
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Pneumático / PU — medida em mm (sem NPS/schedule industrial).',
    };
  }

  const pvcLine = /\b(PVC\s+MARRON|PVC\s+BRANCO|PVC\s+AZUL|CPVC|PPR)\b/i;
  if (_has(u, pvcLine)) {
    const reduPvc = _has(u, /\b(LUVA\s+REDUC|BUCHA\s+REDUC|REDU(CAO|ÇÃO)|BUCHA\s+REDU)\b/i);
    const td: TipoDimensional = reduPvc ? 'DN_MM_REDUCAO' : 'DN_MM';
    const tr: TipoRegraCodigo = reduPvc ? 'BASE_DN_MM_REDUCAO' : 'BASE_DN_MM';
    let obs = 'Tubulação leve — medidas DN em mm (sem schedule/rosca industrial).';
    if (/\bTUBO\b/i.test(u)) obs += ' Unidade comum: PC ou M (ajuste manual).';
    else if (/\bMANGUEIRA\b/i.test(u)) obs += ' Unidade comum: M (ajuste manual).';
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: obs,
    };
  }

  const odKw =
    /\b(OD|DUPLA ANILHA|ANILHA|PORCA|INSERT|UNI(AO|ÃO) DUPLA|UNI(AO|ÃO) REDUTORA|CONECTOR MACHO|CONECTOR FEMEA|CONECTOR FÊMEA|ADAPTADOR RETO)\b/;
  if (_has(u, odKw)) {
    const comRosca = _has(u, roscaKw);
    const td: TipoDimensional = comRosca ? 'OD_POLEGADA_X_ROSCA' : 'OD_POLEGADA';
    const tr = sugerirTipoRegraPorDimensional(td);
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: comRosca ? 'OD em polegada com rosca — medida OD + tipo de rosca + medida da rosca.' : 'OD em polegada — medidas da tabela oficial tipo OD.',
    };
  }

  const redu = _has(u, /\b(REDUÇÃO|REDUCAO|REDUTOR)\b/);
  const schKw = /\b(SCH\d*|CURVA|TE\s*90|TE\s*45|TE90|TE45|CAP\b|NIPLE\s+CONC|NIPLE\s+EXC|PESTANA)\b/;
  const soldaReducao = redu && _has(u, schKw);
  const roscaReducao = redu && _has(u, roscaKw);
  if (redu) {
    if (roscaReducao && !soldaReducao) {
      const td: TipoDimensional = 'ROSCA_X_ROSCA';
      const tr: TipoRegraCodigo = 'BASE_ROSCA_DUAS_POLEGADAS';
      return {
        categoria_produto: 'PRODUTO_TECNICO',
        tipo_dimensional: td,
        tipo_regra_codigo: tr,
        campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
        observacao: 'Redução roscada — duas polegadas NPS + rosca.',
      };
    }
    const td: TipoDimensional = 'REDUCAO_NPS';
    const tr = sugerirTipoRegraPorDimensional(td);
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Redução com schedule — duas polegadas NPS + schedule.',
    };
  }

  if (_has(u, schKw) && !_has(u, roscaKw)) {
    const td: TipoDimensional = 'NPS_SCHEDULE';
    const tr = sugerirTipoRegraPorDimensional(td);
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Curva/te/cap/niple com schedule — NPS + schedule.',
    };
  }

  if (_has(u, /\bFLANGE\b/)) {
    const cego = _has(u, /\b(CEGO|LISO|SO\b|SOLTO)\b/);
    const soldaFl = _has(u, /\b(WN|SW|SO SW|LISO SW)\b/);
    const td: TipoDimensional = cego && !soldaFl ? 'FLANGE' : 'NPS_SCHEDULE';
    const tr = sugerirTipoRegraPorDimensional(td);
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: soldaFl
        ? 'Flange soldável (WN/SW etc.) — costuma exigir schedule; pode mudar para Flange simples se não usar SCH.'
        : 'Flange cego/liso/SO — em geral só NPS nominal.',
    };
  }

  if (_has(u, /\bTUBO\b/)) {
    const odMm = _has(u, /\b(ASTM A-269|S\/C|C\/C|OD)\b/i);
    const npsSch = _has(u, /\b(API 5L|A-106|SCH|NBR5580|NBR5590)\b/);
    if (odMm && !npsSch) {
      const td: TipoDimensional = 'OD_MM_X_ESPESSURA_X_COMPRIMENTO';
      const tr = sugerirTipoRegraPorDimensional(td);
      return {
        categoria_produto: 'PRODUTO_TECNICO',
        tipo_dimensional: td,
        tipo_regra_codigo: tr,
        campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
        observacao: 'Tubo OD mm — OD + espessura (+ comprimento).',
      };
    }
    if (npsSch) {
      const td: TipoDimensional = 'NPS_SCHEDULE';
      const tr = sugerirTipoRegraPorDimensional(td);
      return {
        categoria_produto: 'PRODUTO_TECNICO',
        tipo_dimensional: td,
        tipo_regra_codigo: tr,
        campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
        observacao: 'Tubo linha API/NBR com schedule — NPS + SCH.',
      };
    }
  }

  if (_has(u, /\bVALVULA ESFERA\b/) || _has(u0, /^(VEM|VEB|VET)\b/)) {
    const flangeada = _has(u, /\b(FLANGEADA|FL\s*ANSI|ANSI|DIN|PN\d+)\b/);
    const roscada = _has(u, roscaKw);
    const fabValv = _has(
      u,
      /\b(JEFFERSON|DANFOSS|VALMICRO|SOLENOIDE|ATUADOR|CONECTOR CABO|MANOMETRO)\b/,
    );
    if (fabValv) {
      const td: TipoDimensional = 'MANUAL';
      const tr: TipoRegraCodigo = 'MANUAL_FABRICANTE';
      return {
        categoria_produto: 'MANUAL_FABRICANTE',
        tipo_dimensional: td,
        tipo_regra_codigo: tr,
        campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
        observacao: 'Válvula com referência de fabricante — código manual.',
      };
    }
    if (flangeada) {
      const td: TipoDimensional = 'VALVULA';
      const tr: TipoRegraCodigo = 'BASE_POLEGADA';
      return {
        categoria_produto: 'PRODUTO_TECNICO',
        tipo_dimensional: td,
        tipo_regra_codigo: tr,
        campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
        observacao: 'Válvula flangeada — em geral NPS nominal (ajuste se usar schedule).',
      };
    }
    if (roscada) {
      const td: TipoDimensional = 'NPS_X_ROSCA';
      const tr = sugerirTipoRegraPorDimensional(td);
      return {
        categoria_produto: 'PRODUTO_TECNICO',
        tipo_dimensional: td,
        tipo_regra_codigo: tr,
        campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
        observacao: 'Válvula roscada — NPS × rosca.',
      };
    }
    const td: TipoDimensional = 'VALVULA';
    const tr: TipoRegraCodigo = 'BASE_POLEGADA';
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Válvula esfera — refine NPS/schedule/rosca conforme o modelo.',
    };
  }

  if (_has(u, roscaKw) && !_has(u, odKw)) {
    const td: TipoDimensional = 'NPS_X_ROSCA';
    const tr = sugerirTipoRegraPorDimensional(td);
    return {
      categoria_produto: 'PRODUTO_TECNICO',
      tipo_dimensional: td,
      tipo_regra_codigo: tr,
      campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
      observacao: 'Conexão roscada (BSP/NPT etc.) sem OD dedicado — NPS × rosca.',
    };
  }

  const td: TipoDimensional = 'SIMPLES';
  const tr = sugerirTipoRegraPorDimensional(td);
  return {
    categoria_produto: 'PRODUTO_TECNICO',
    tipo_dimensional: td,
    tipo_regra_codigo: tr,
    campos_obrigatorios_labels: labelsCamposObrigatorios(flagsPorTipoRegra(tr), td),
    observacao: 'Sem padrão específico — ajuste tipo dimensional e regra manualmente.',
  };
}

/**
 * Combina regra de código + tipo dimensional como o backend em `requisitos_efetivos_produto`
 * (campos que o produto passa a exigir após salvar a família).
 */
export function requisitosMedidasPermitidasModal(
  td: TipoDimensional | undefined | null,
  tipoRegra: string | undefined | null,
): FlagsFamilia {
  const flags = flagsPorTipoRegra(tipoRegra);
  const r: FlagsFamilia = { ...flags };
  const t = (td || 'SIMPLES') as TipoDimensional;
  const tr = normalizarTipoRegra(tipoRegra);

  if (tr === 'BASE_OD_MM_ESPESSURA') {
    return { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: false, usa_polegada_secundaria: false };
  }

  if (tr === 'BASE_OD_POLEGADA_ESPESSURA') {
    return { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: true, usa_polegada_secundaria: false };
  }

  if (['BASE_DN_MM', 'BASE_DN_MM_REDUCAO', 'BASE_OD_MM', 'BASE_OD_MM_REDUCAO'].includes(tr || '')) {
    return { usa_rosca_conexao: false, usa_schedule: false, usa_polegada_principal: false, usa_polegada_secundaria: false };
  }

  const odOuMmSemSchedule: TipoDimensional[] = [
    'OD_POLEGADA',
    'OD_POLEGADA_X_ESPESSURA',
    'OD_POLEGADA_X_ROSCA',
    'OD_MM',
    'DN_MM',
    'DN_MM_REDUCAO',
    'BITOLA_POLEGADA',
    'OD_MM_REDUCAO',
    'OD_MM_X_ROSCA',
    'OD_MM_X_ESPESSURA',
    'OD_MM_X_ESPESSURA_X_COMPRIMENTO',
    'CHAPA_MM',
    'CHAPA_FURO_MM',
    'BARRA_CHATA_MM',
    'METALON_MM',
    'PERFIL_RETANGULAR_MM',
    'CANTONEIRA_MM',
    'DIMENSIONAL_LIVRE_CONTROLADO',
  ];
  if (odOuMmSemSchedule.includes(t)) {
    r.usa_schedule = false;
  }

  if (t === 'NPS_SCHEDULE') {
    r.usa_schedule = true;
    r.usa_polegada_principal = true;
  }
  if (t === 'REDUCAO_NPS') {
    r.usa_schedule = true;
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = true;
  }
  if (t === 'NPS_X_ROSCA' || t === 'ROSCA_X_ROSCA') {
    r.usa_rosca_conexao = true;
    r.usa_polegada_principal = true;
    r.usa_schedule = false;
  }
  if (t === 'ROSCA_X_ROSCA') {
    r.usa_polegada_secundaria = true;
  }
  if (familiaEhEspigaoFlangeNps(t, tipoRegra)) {
    r.usa_rosca_conexao = false;
    r.usa_schedule = false;
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = true;
  }
  if (t === 'OD_POLEGADA') {
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = false;
  }
  if (t === 'OD_POLEGADA_X_ESPESSURA') {
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = false;
    r.usa_schedule = false;
  }
  if (t === 'OD_POLEGADA_X_ROSCA') {
    r.usa_rosca_conexao = true;
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = true;
  }

  const mmSemPolegadaSchedule: TipoDimensional[] = [
    'OD_MM',
    'DN_MM',
    'DN_MM_REDUCAO',
    'OD_MM_REDUCAO',
    'OD_MM_X_ESPESSURA',
    'OD_MM_X_ESPESSURA_X_COMPRIMENTO',
    'CHAPA_MM',
    'CHAPA_FURO_MM',
    'BARRA_CHATA_MM',
    'METALON_MM',
    'PERFIL_RETANGULAR_MM',
    'CANTONEIRA_MM',
    'DIMENSIONAL_LIVRE_CONTROLADO',
  ];
  if (mmSemPolegadaSchedule.includes(t)) {
    r.usa_polegada_principal = false;
    r.usa_polegada_secundaria = false;
    r.usa_rosca_conexao = false;
    r.usa_schedule = false;
  }
  if (t === 'BITOLA_POLEGADA') {
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = false;
    r.usa_rosca_conexao = false;
    r.usa_schedule = false;
  }
  if (t === 'OD_MM_X_ROSCA') {
    r.usa_rosca_conexao = true;
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = false;
    r.usa_schedule = false;
  }
  if (t === 'CANTONEIRA_POLEGADA') {
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = true;
    r.usa_rosca_conexao = false;
    r.usa_schedule = false;
  }
  return r;
}

export function tipoMedidaPrincipalPorDimensional(td: TipoDimensional | undefined | null): 'NPS' | 'OD' | undefined {
  if (!td) return undefined;
  if (td === 'OD_POLEGADA' || td === 'OD_POLEGADA_X_ESPESSURA' || td === 'OD_POLEGADA_X_ROSCA') return 'OD';
  if (
    td === 'NPS' ||
    td === 'NPS_SCHEDULE' ||
    td === 'REDUCAO_NPS' ||
    td === 'NPS_X_ROSCA' ||
    td === 'FLANGE' ||
    td === 'ESPIGAO_X_FLANGE' ||
    td === 'VALVULA' ||
    td === 'ROSCA' ||
    td === 'ROSCA_X_ROSCA'
  )
    return 'NPS';
  return undefined;
}

export function tipoMedidaSecundariaPorDimensional(td: TipoDimensional | undefined | null): 'NPS' | 'OD' | undefined {
  if (!td) return undefined;
  if (
    td === 'OD_POLEGADA_X_ROSCA' ||
    td === 'REDUCAO_NPS' ||
    td === 'NPS' ||
    td === 'NPS_SCHEDULE' ||
    td === 'NPS_X_ROSCA' ||
    td === 'ROSCA_X_ROSCA' ||
    td === 'ESPIGAO_X_FLANGE'
  )
    return 'NPS';
  return undefined;
}

/** Exemplo de código dimensional para prévia no modal de família. */
export function exemploCodigoDimensionalFamilia(
  td: TipoDimensional | undefined | null,
  codigoFigura: string | undefined | null,
): string | null {
  const fig = (codigoFigura || 'FIG').trim();
  if (td === 'OD_POLEGADA_X_ESPESSURA') return `${fig}OD.040150 (OD 1/2" + 1,50 mm)`;
  if (td === 'NPS_SCHEDULE') return `${fig}.20.XX`;
  return null;
}

/** Exemplo de descrição dimensional para prévia no modal de família. */
export function exemploDescricaoDimensionalFamilia(td: TipoDimensional | undefined | null): string | null {
  if (td === 'OD_POLEGADA_X_ESPESSURA') return 'OD 1/2" x 1,50 mm';
  return null;
}
