/** Helpers de período (emissão/competência) no estilo Inbox Fiscal. */

export function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

export function ultimoDiaMes(ano: number, mes: number): number {
  return new Date(ano, mes, 0).getDate();
}

export function intervaloMes(ano: number, mes: number): { inicio: string; fim: string } {
  const fim = ultimoDiaMes(ano, mes);
  return {
    inicio: `${ano}-${pad2(mes)}-01`,
    fim: `${ano}-${pad2(mes)}-${pad2(fim)}`,
  };
}

export function intervaloMesAtual(): { inicio: string; fim: string } {
  const hoje = new Date();
  return intervaloMes(hoje.getFullYear(), hoje.getMonth() + 1);
}

export function intervaloMesAnterior(): { inicio: string; fim: string } {
  const hoje = new Date();
  const mes = hoje.getMonth();
  const ano = mes === 0 ? hoje.getFullYear() - 1 : hoje.getFullYear();
  const mesRef = mes === 0 ? 12 : mes;
  return intervaloMes(ano, mesRef);
}

/** Aceita `mm/aaaa` ou `mmaaaa` e devolve intervalo ISO do mês. */
export function aplicarCompetenciaMmAaaa(valor: string): { inicio: string; fim: string } | null {
  const limpo = valor.replace(/\D/g, '');
  if (limpo.length !== 6) return null;
  const mes = Number(limpo.slice(0, 2));
  const ano = Number(limpo.slice(2));
  if (mes < 1 || mes > 12) return null;
  return intervaloMes(ano, mes);
}

export function labelPeriodoFiltro(opts: {
  dataInicio?: string;
  dataFim?: string;
  competencia?: string;
}): string {
  const di = (opts.dataInicio || '').trim();
  const df = (opts.dataFim || '').trim();
  if (di && df) return `${di} → ${df}`;
  if (di) return `a partir de ${di}`;
  if (df) return `até ${df}`;
  const comp = (opts.competencia || '').trim();
  if (comp) return `competência ${comp}`;
  return 'sem período (todas as datas)';
}

/** Atalho operacional alinhado ao Inbox Fiscal (lote Jun/2026). */
export const PERIODO_ATALHO_JUN_2026 = { inicio: '2026-06-01', fim: '2026-06-30' } as const;
