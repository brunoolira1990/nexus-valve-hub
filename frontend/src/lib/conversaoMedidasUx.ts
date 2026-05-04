import type { TipoControleUnidade, TipoFisicoProduto } from '@/types';

/** Unidades comerciais iniciais (UI). */
export const UNIDADES_CATALOGO = ['PC', 'KG', 'TON', 'M', 'BR', 'CH', 'UN', 'CJ'] as const;
export type CodigoUnidade = (typeof UNIDADES_CATALOGO)[number];

export const TIPO_FISICO_OPTIONS: { value: TipoFisicoProduto; label: string }[] = [
  { value: 'PECA', label: 'Peça' },
  { value: 'TUBO', label: 'Tubo' },
  { value: 'BARRA_REDONDA', label: 'Barra redonda' },
  { value: 'BARRA_CHATA', label: 'Barra chata' },
  { value: 'BARRA_SEXTAVADA', label: 'Barra sextavada' },
  { value: 'CHAPA', label: 'Chapa' },
  { value: 'DISCO', label: 'Disco' },
  { value: 'PERFIL', label: 'Perfil' },
  { value: 'CANTONEIRA', label: 'Cantoneira' },
  { value: 'OUTRO', label: 'Outro' },
];

export const TIPO_CONTROLE_OPTIONS: { value: TipoControleUnidade; label: string }[] = [
  { value: 'PECA', label: 'Peça' },
  { value: 'DIMENSIONAL', label: 'Dimensional' },
  { value: 'PESO', label: 'Peso' },
  { value: 'LINEAR', label: 'Linear' },
  { value: 'LINEAR_PESO', label: 'Linear + peso' },
  { value: 'CHAPA', label: 'Chapa' },
  { value: 'TUBO', label: 'Tubo' },
  { value: 'BARRA', label: 'Barra' },
  { value: 'PERFIL', label: 'Perfil' },
];

export function fmtPt(val: number, dec = 3): string {
  if (!Number.isFinite(val)) return '—';
  return val.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export type VisibilidadeMedidas = {
  showBarraMetro: boolean;
  showPesoMetro: boolean;
  showPesoChapa: boolean;
  showPesoPeca: boolean;
  showDensidadeOpcional: boolean;
  showSugestaoUnidadesLinear: boolean;
  showSugestaoUnidadesChapa: boolean;
  avisoTipoPecaMetro: string | null;
};

export function visibilidadePorTipoFisico(tipoFisico: string, usaConversao: boolean): VisibilidadeMedidas {
  const t = (tipoFisico || 'PECA').toUpperCase();
  const linear = new Set(['TUBO', 'BARRA_REDONDA', 'BARRA_CHATA', 'BARRA_SEXTAVADA', 'PERFIL', 'CANTONEIRA']);
  const chapa = t === 'CHAPA' || t === 'DISCO';

  if (t === 'PECA') {
    return {
      showBarraMetro: false,
      showPesoMetro: false,
      showPesoChapa: false,
      showPesoPeca: true,
      showDensidadeOpcional: false,
      showSugestaoUnidadesLinear: false,
      showSugestaoUnidadesChapa: false,
      avisoTipoPecaMetro:
        usaConversao ? 'Produto tipo PEÇA não usa conversão por metro; use peso por peça se precisar converter para KG.' : null,
    };
  }

  if (chapa) {
    return {
      showBarraMetro: false,
      showPesoMetro: false,
      showPesoChapa: true,
      showPesoPeca: false,
      showDensidadeOpcional: true,
      showSugestaoUnidadesLinear: false,
      showSugestaoUnidadesChapa: true,
      avisoTipoPecaMetro: null,
    };
  }

  if (linear.has(t) || t === 'OUTRO') {
    return {
      showBarraMetro: t !== 'OUTRO' || usaConversao,
      showPesoMetro: true,
      showPesoChapa: t === 'OUTRO',
      showPesoPeca: t === 'OUTRO',
      showDensidadeOpcional: true,
      showSugestaoUnidadesLinear: true,
      showSugestaoUnidadesChapa: false,
      avisoTipoPecaMetro: null,
    };
  }

  return {
    showBarraMetro: false,
    showPesoMetro: false,
    showPesoChapa: false,
    showPesoPeca: false,
    showDensidadeOpcional: false,
    showSugestaoUnidadesLinear: false,
    showSugestaoUnidadesChapa: false,
    avisoTipoPecaMetro: null,
  };
}

export function mensagensFatoresFaltando(opts: {
  tipoFisico: string;
  usaConversao: boolean;
  comprimentoBarra: number | null | undefined;
  pesoMetro: number | null | undefined;
  pesoChapa: number | null | undefined;
  pesoPeca: number | null | undefined;
}): string[] {
  const v = visibilidadePorTipoFisico(opts.tipoFisico, opts.usaConversao);
  const msg: string[] = [];
  if (!opts.usaConversao) return msg;
  if (v.showPesoMetro && (opts.pesoMetro == null || opts.pesoMetro <= 0)) {
    msg.push('Informe peso por metro para converter M ↔ KG.');
  }
  if (v.showBarraMetro && (opts.comprimentoBarra == null || opts.comprimentoBarra <= 0)) {
    msg.push('Informe comprimento padrão da barra para converter BR ↔ M.');
  }
  if (v.showBarraMetro && v.showPesoMetro) {
    const okBarra = opts.comprimentoBarra != null && opts.comprimentoBarra > 0;
    const okPm = opts.pesoMetro != null && opts.pesoMetro > 0;
    if (!okBarra || !okPm) {
      msg.push('Informe comprimento da barra e peso por metro para converter BR ↔ KG.');
    }
  }
  if (v.showPesoChapa && (opts.pesoChapa == null || opts.pesoChapa <= 0)) {
    msg.push('Informe peso por chapa para converter CH ↔ KG.');
  }
  if (v.showPesoPeca && opts.tipoFisico === 'PECA' && opts.usaConversao && (opts.pesoPeca == null || opts.pesoPeca <= 0)) {
    msg.push('Para PEÇA com conversão, informe peso por peça se precisar converter PC ↔ KG.');
  }
  if (v.avisoTipoPecaMetro) msg.push(v.avisoTipoPecaMetro);
  return [...new Set(msg)];
}

export function previewLinhasConversao(opts: {
  tipoFisico: string;
  usaConversao: boolean;
  comprimentoBarra: number | null | undefined;
  pesoMetro: number | null | undefined;
  pesoPeca: number | null | undefined;
  pesoChapa: number | null | undefined;
}): { linhas: string[]; avisos: string[] } {
  const avisos = mensagensFatoresFaltando(opts);
  const linhas: string[] = [];
  const v = visibilidadePorTipoFisico(opts.tipoFisico, opts.usaConversao);

  if (!opts.usaConversao) {
    if ((opts.tipoFisico || 'PECA') === 'PECA') {
      linhas.push('Conversão dimensional desativada. Use o campo Unidade (ex.: PC) para peças simples.');
    } else {
      linhas.push('Conversão dimensional desativada.');
    }
    return { linhas, avisos };
  }

  linhas.push(`1 TON = ${fmtPt(1000)} KG`);

  const L = opts.comprimentoBarra ?? null;
  const pm = opts.pesoMetro ?? null;
  const pp = opts.pesoPeca ?? null;
  const pch = opts.pesoChapa ?? null;

  if (v.showBarraMetro && v.showPesoMetro && L != null && L > 0 && pm != null && pm > 0) {
    const kgBarra = L * pm;
    linhas.push(`1 BR = ${fmtPt(L)} M = ${fmtPt(kgBarra)} KG`);
    linhas.push(`1 M = ${fmtPt(pm)} KG`);
  } else if (v.showPesoMetro && pm != null && pm > 0) {
    linhas.push(`1 M = ${fmtPt(pm)} KG`);
  }

  if (v.showPesoChapa && pch != null && pch > 0) {
    linhas.push(`1 CH = ${fmtPt(pch)} KG`);
  }

  if (v.showPesoPeca && pp != null && pp > 0) {
    linhas.push(`1 PC = ${fmtPt(pp)} KG`);
  }

  if (linhas.length === 1 && linhas[0].startsWith('1 TON')) {
    // só TON universal; ok
  }

  return { linhas, avisos };
}

export function toggleUnidadeLista(list: string[], codigo: string): string[] {
  const c = codigo.toUpperCase();
  const set = new Set((list || []).map((x) => x.toUpperCase()));
  if (set.has(c)) set.delete(c);
  else set.add(c);
  return UNIDADES_CATALOGO.filter((u) => set.has(u));
}

export function unidadesSugeridasLinear(): CodigoUnidade[] {
  return ['M', 'BR', 'KG', 'TON'];
}

export function unidadesSugeridasChapa(): CodigoUnidade[] {
  return ['CH', 'KG', 'TON', 'PC', 'UN', 'CJ'];
}
