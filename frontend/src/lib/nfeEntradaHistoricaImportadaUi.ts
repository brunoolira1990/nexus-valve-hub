import type { NFeEntradaHistoricaList } from '@/services/api/nfeHistoricaEntradaImportada';

/** Chave operacional da listagem — apenas UI; não altera valores da API. */
export type StatusOperacionalNfeEntradaHistorica =
  | 'aguardando_conferencia'
  | 'conferencia_em_andamento'
  | 'aguardando_estoque'
  | 'entrada_realizada';

export const LABEL_STATUS_OPERACIONAL_NFE_ENTRADA_HISTORICA: Record<
  StatusOperacionalNfeEntradaHistorica,
  string
> = {
  aguardando_conferencia: 'Aguardando conferência',
  conferencia_em_andamento: 'Conferência em andamento',
  aguardando_estoque: 'Aguardando estoque',
  entrada_realizada: 'Entrada realizada',
};

export const STATUS_CONFERENCIA_FILTRO_OPCOES = [
  { value: '', label: 'Status conferência (todos)' },
  { value: 'sem_conferencia', label: LABEL_STATUS_OPERACIONAL_NFE_ENTRADA_HISTORICA.aguardando_conferencia },
  { value: 'pendente', label: LABEL_STATUS_OPERACIONAL_NFE_ENTRADA_HISTORICA.conferencia_em_andamento },
  { value: 'finalizada', label: LABEL_STATUS_OPERACIONAL_NFE_ENTRADA_HISTORICA.aguardando_estoque },
  { value: 'estoque_aplicado', label: LABEL_STATUS_OPERACIONAL_NFE_ENTRADA_HISTORICA.entrada_realizada },
] as const;

const STATUS_BADGE_TOKEN: Record<StatusOperacionalNfeEntradaHistorica, string> = {
  aguardando_conferencia: 'importada',
  conferencia_em_andamento: 'em_conferencia',
  aguardando_estoque: 'preparada_entrada',
  entrada_realizada: 'concluido',
};

const LABEL_BOTAO_PRINCIPAL: Record<StatusOperacionalNfeEntradaHistorica, string> = {
  aguardando_conferencia: 'Conferir entrada',
  conferencia_em_andamento: 'Continuar conferência',
  aguardando_estoque: 'Aplicar estoque',
  entrada_realizada: 'Ver conferência',
};

export function resolverStatusOperacionalNfeEntradaHistorica(
  row: Pick<
    NFeEntradaHistoricaList,
    'conferencia_status' | 'conferencia_preparado_em' | 'conferencia_estoque_aplicado_em'
  >,
): StatusOperacionalNfeEntradaHistorica {
  if (row.conferencia_estoque_aplicado_em) {
    return 'entrada_realizada';
  }

  const status = (row.conferencia_status || '').trim().toUpperCase();
  if (status === 'PREPARADA' || row.conferencia_preparado_em) {
    return 'aguardando_estoque';
  }
  if (status === 'PENDENTE' || status === 'CONFERIDA' || status === 'CANCELADA') {
    return 'conferencia_em_andamento';
  }

  return 'aguardando_conferencia';
}

export function labelStatusOperacionalNfeEntradaHistorica(
  row: Pick<
    NFeEntradaHistoricaList,
    'conferencia_status' | 'conferencia_preparado_em' | 'conferencia_estoque_aplicado_em'
  >,
): string {
  const operacional = resolverStatusOperacionalNfeEntradaHistorica(row);
  return LABEL_STATUS_OPERACIONAL_NFE_ENTRADA_HISTORICA[operacional];
}

export function statusBadgeTokenNfeEntradaHistorica(
  row: Pick<
    NFeEntradaHistoricaList,
    'conferencia_status' | 'conferencia_preparado_em' | 'conferencia_estoque_aplicado_em'
  >,
): string {
  return STATUS_BADGE_TOKEN[resolverStatusOperacionalNfeEntradaHistorica(row)];
}

export function labelBotaoPrincipalConferenciaNfeEntradaHistorica(
  row: Pick<
    NFeEntradaHistoricaList,
    'conferencia_status' | 'conferencia_preparado_em' | 'conferencia_estoque_aplicado_em'
  >,
): string {
  return LABEL_BOTAO_PRINCIPAL[resolverStatusOperacionalNfeEntradaHistorica(row)];
}

/** Rota da conferência — mesma página; hash opcional para foco na aplicação de estoque. */
export function rotaConferenciaNfeEntradaHistorica(
  nfId: number,
  row: Pick<
    NFeEntradaHistoricaList,
    'conferencia_status' | 'conferencia_preparado_em' | 'conferencia_estoque_aplicado_em'
  >,
): string {
  const base = `/nfe-entrada/${nfId}/conferencia`;
  if (resolverStatusOperacionalNfeEntradaHistorica(row) === 'aguardando_estoque') {
    return `${base}#aplicar-estoque-fisico`;
  }
  return base;
}
