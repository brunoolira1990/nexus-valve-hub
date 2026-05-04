import type { TipoRegraCodigo } from '@/types';

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

export function labelsCamposObrigatorios(flags: FlagsFamilia): string[] {
  const r: string[] = [];
  if (flags.usa_rosca_conexao) r.push('Rosca / conexão');
  if (flags.usa_schedule) r.push('Schedule / espessura');
  if (flags.usa_polegada_principal) r.push('Polegada principal (ID)');
  if (flags.usa_polegada_secundaria) r.push('Polegada secundária (ID)');
  if (r.length === 0) r.push('Nenhum (código manual no produto)');
  return r;
}
