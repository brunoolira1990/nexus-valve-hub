import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import type { NFeDestinadaDocumento } from '@/services/api/manifestacaoDestinatario';
import type { StatusTone } from '@/design-system/tokens';

/** Estados consolidados expostos pela API (Inbox Fiscal). */
export const ESTADOS_INBOX_FILTRO: { value: string; label: string }[] = [
  { value: 'RECEBIDO', label: 'Recebido' },
  { value: 'PRECISA_MANIFESTAR', label: 'Precisa manifestar' },
  { value: 'XML_DISPONIVEL', label: 'XML disponível' },
  { value: 'EM_CONFERENCIA', label: 'Em conferência' },
  { value: 'CONFERIDO', label: 'Conferido' },
  { value: 'ESTOQUE_APLICADO', label: 'Estoque aplicado' },
  { value: 'CONCLUIDO', label: 'Concluído' },
  { value: 'DIVERGENTE', label: 'Divergente' },
  { value: 'BLOQUEADO', label: 'Bloqueado' },
];

export type EstadoConsolidadoExibicao = {
  estado: string;
  label: string;
  motivo?: string;
  detalhes?: Record<string, unknown>;
};

const TONE_PENDENCIA: StatusTone = 'warning';
const TONE_EXCECAO: StatusTone = 'danger';
const TONE_CONCLUIDO: StatusTone = 'success';
const TONE_INTERMEDIARIO: StatusTone = 'info';

/** Mapeia estado consolidado → tom visual do badge. */
export function tomBadgeEstadoConsolidado(estado: string): StatusTone {
  const st = (estado || '').toUpperCase();
  if (st === 'CONCLUIDO') return TONE_CONCLUIDO;
  if (st === 'DIVERGENTE' || st === 'BLOQUEADO') return TONE_EXCECAO;
  if (st === 'CONFERIDO' || st === 'ESTOQUE_APLICADO') return TONE_INTERMEDIARIO;
  if (
    st === 'RECEBIDO' ||
    st === 'PRECISA_MANIFESTAR' ||
    st === 'XML_DISPONIVEL' ||
    st === 'EM_CONFERENCIA'
  ) {
    return TONE_PENDENCIA;
  }
  return 'neutral';
}

function fallbackEstadoManifestacao(m: NFeDestinadaDocumento): EstadoConsolidadoExibicao | null {
  const st = (m.status_manifestacao || '').toUpperCase();
  if (st === 'PENDENTE') {
    return { estado: 'PRECISA_MANIFESTAR', label: 'Precisa manifestar' };
  }
  if (st === 'DESCONHECIDA' || st === 'NAO_REALIZADA') {
    return { estado: 'CONCLUIDO', label: 'Concluído' };
  }
  if (['CIENTE', 'CONFIRMADA'].includes(st)) {
    return { estado: 'XML_DISPONIVEL', label: 'XML disponível' };
  }
  return { estado: 'RECEBIDO', label: 'Recebido' };
}

/** Resolve estado/label para exibição — prioriza API, fallback para resumo local. */
export function resolverEstadoConsolidadoExibicao(
  row: CentralDfeDocumento,
  manifestacao?: NFeDestinadaDocumento | null,
): EstadoConsolidadoExibicao {
  if (row.estado_consolidado) {
    return {
      estado: row.estado_consolidado,
      label: row.estado_consolidado_label || row.estado_consolidado,
      motivo: row.estado_consolidado_motivo,
      detalhes: row.estado_consolidado_detalhes,
    };
  }
  if (manifestacao && row.tipo_documento === 'NFE_ENTRADA') {
    const fb = fallbackEstadoManifestacao(manifestacao);
    if (fb) return fb;
  }
  return { estado: 'RECEBIDO', label: 'Recebido' };
}

/** Textos visíveis de alerta fiscal (motivo + observação dos detalhes). */
export function textosAlertaEstadoConsolidado(exibicao: EstadoConsolidadoExibicao): string[] {
  const linhas: string[] = [];
  const motivo = (exibicao.motivo || '').trim();
  if (motivo) linhas.push(motivo);

  const det = exibicao.detalhes || {};
  const obs = typeof det.observacao === 'string' ? det.observacao.trim() : '';
  if (obs && obs !== motivo) linhas.push(obs);

  if (det.chave_em_nfe_entrada_operacional === true) {
    const msg =
      'Atenção: a mesma chave também existe em Entrada Própria operacional. ' +
      'Verifique se conferência e estoque da base importada foram concluídos.';
    if (!linhas.some((l) => l.includes('Entrada Própria operacional'))) {
      linhas.push(msg);
    }
  }

  return linhas;
}

export function badgeStatusEstadoConsolidado(estado: string): string {
  const tom = tomBadgeEstadoConsolidado(estado);
  const map: Record<StatusTone, string> = {
    neutral: 'pendente',
    info: 'em_analise',
    primary: 'preparada_entrada',
    success: 'concluido',
    warning: 'pendente',
    danger: 'divergente_qualidade',
    preparation: 'pendente',
  };
  return map[tom] || 'pendente';
}
