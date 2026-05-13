import type { FamiliaProduto, RequisitosProdutoDimensionais, TipoDimensional, TipoRegraCodigo } from '@/types';

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
    r.push(td === 'ESPIGAO_X_FLANGE' ? 'Medida do espigão (NPS)' : 'Polegada principal (ID)');
  }
  if (flags.usa_polegada_secundaria) {
    r.push(td === 'ESPIGAO_X_FLANGE' ? 'Medida da flange (NPS)' : 'Polegada secundária (ID)');
  }
  if (r.length === 0) r.push('Nenhum (código manual no produto)');
  return r;
}

/** Texto curto explicando o tipo dimensional (UI família/produto). */
export function hintTipoDimensional(td: TipoDimensional | undefined | null): string {
  switch (td) {
    case 'NPS_SCHEDULE':
    case 'REDUCAO_NPS':
      return 'NPS/SCH — usa Schedule + polegada(s) nominal(is). OD não é NPS/SCH.';
    case 'OD_POLEGADA':
      return 'OD em polegada — medida OD no cadastro mestre de polegadas; sem schedule.';
    case 'OD_POLEGADA_X_ROSCA':
      return 'OD x Rosca — medida OD + tipo de rosca + medida da rosca; sem schedule.';
    case 'OD_MM':
    case 'OD_MM_X_ESPESSURA':
    case 'OD_MM_X_ESPESSURA_X_COMPRIMENTO':
      return 'OD em mm — valores numéricos (mm); use regra 11 no código; sem NPS/SCH.';
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
  if (td === 'OD_POLEGADA' || td === 'OD_POLEGADA_X_ROSCA') return 'Medida OD (cadastro mestre)';
  if (td === 'CANTONEIRA_POLEGADA') return 'Aba em polegada';
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
  if (req.usa_rosca_conexao) r.push('Tipo de rosca / conexão');
  if (req.usa_polegada_principal) r.push(labelPolegadaPrincipal(td));
  if (req.usa_polegada_secundaria) r.push(labelPolegadaSecundaria(td));
  if (req.exige_od_mm) r.push('OD externo (mm)');
  if (req.exige_espessura_mm) r.push('Espessura (mm)');
  if (req.exige_comprimento_mm) r.push('Comprimento (mm ou padrão da família)');
  if (r.length === 0) r.push('Nenhum campo automático (ver modo manual)');
  return r;
}

/** Espigão × flange (E…F…): mesma regra do backend `familia_espigao_x_flange_nps`. */
export function familiaEhEspigaoFlangeNps(td: TipoDimensional | undefined | null, tipoRegra: string | undefined | null): boolean {
  const n = normalizarTipoRegra(tipoRegra);
  return td === 'ESPIGAO_X_FLANGE' || n === 'BASE_ESPIGAO_FLANGE_NPS';
}

/**
 * Combina regra de código + tipo dimensional como o backend em `requisitos_efetivos_produto`
 * (apenas flags usados na UI de “medidas permitidas” da família).
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

  const odOuMmSemSchedule: TipoDimensional[] = [
    'OD_POLEGADA',
    'OD_POLEGADA_X_ROSCA',
    'OD_MM',
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
  if (t === 'NPS_X_ROSCA') {
    r.usa_rosca_conexao = true;
    r.usa_polegada_principal = true;
    r.usa_schedule = false;
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
  if (t === 'OD_POLEGADA_X_ROSCA') {
    r.usa_rosca_conexao = true;
    r.usa_polegada_principal = true;
    r.usa_polegada_secundaria = true;
  }

  const mmSemPolegadaSchedule: TipoDimensional[] = [
    'OD_MM',
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
  if (td === 'OD_POLEGADA' || td === 'OD_POLEGADA_X_ROSCA') return 'OD';
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
