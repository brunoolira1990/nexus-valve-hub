/** UX / labels — tela SEFAZ status serviço NF-e 3.6.1 */

export type SefazConsultaResumo = {
  ok?: boolean;
  sucesso?: boolean;
  servico_operacional?: boolean;
  c_stat?: string;
  cstat?: string;
  x_motivo?: string;
  motivo?: string;
  erro_tecnico?: string;
  tipo_erro?: string;
};

export function consultaOk(c: SefazConsultaResumo): boolean {
  if (typeof c.ok === 'boolean') return c.ok;
  if (typeof c.sucesso === 'boolean') return c.sucesso;
  return Boolean(c.servico_operacional);
}

export function cStatExibicao(c: SefazConsultaResumo): string {
  const v = (c.c_stat || c.cstat || '').trim();
  if (v) return v;
  if (!consultaOk(c)) return '';
  return '—';
}

export function motivoExibicao(c: SefazConsultaResumo): string {
  const m = (c.motivo || c.x_motivo || '').trim();
  if (m) return m;
  const e = (c.erro_tecnico || '').trim();
  if (e) return e;
  if (!consultaOk(c)) return 'Falha sem retorno SEFAZ';
  return '—';
}

export function consultaFalhou(c: SefazConsultaResumo): boolean {
  return !consultaOk(c);
}

export function tituloUltimoRetorno(c: SefazConsultaResumo): string {
  if (consultaOk(c)) return 'Último retorno SEFAZ';
  return 'Consulta não concluída';
}

export function resultadoHistoricoLabel(c: SefazConsultaResumo): string {
  if (consultaOk(c)) return 'OK';
  if (c.tipo_erro) return c.tipo_erro;
  return 'Falha';
}

export function erroHistoricoResumo(c: SefazConsultaResumo): string {
  if (consultaOk(c)) return '';
  const e = (c.erro_tecnico || '').trim();
  if (e.length > 60) return `${e.slice(0, 57)}…`;
  return e || motivoExibicao(c);
}
