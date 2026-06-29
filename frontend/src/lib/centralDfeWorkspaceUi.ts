import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import type { NFeDestinadaDocumento } from '@/services/api/manifestacaoDestinatario';
import { isCteTransportadora } from '@/lib/centralDfeUi';

/** Resolve id da NF-e histórica importada para conferência/estoque. */
export function resolverNfHistoricaId(
  row: CentralDfeDocumento,
  manifestacao?: NFeDestinadaDocumento | null,
): number | null {
  if (row.tipo_documento !== 'NFE_ENTRADA') return null;
  if (row.nf_entrada_historica_id) return row.nf_entrada_historica_id;
  if (manifestacao?.nf_entrada_historica_id) return manifestacao.nf_entrada_historica_id;
  if (row.xml_armazenado) return row.id;
  return null;
}

/** Id do CT-e histórico na base importada (central usa o mesmo id após armazenamento). */
export function resolverCteHistoricoId(row: CentralDfeDocumento): number | null {
  if (!isCteTransportadora(row)) return null;
  return row.id;
}

export type WorkspaceConteudo =
  | 'manifestacao'
  | 'xml_disponivel'
  | 'conferencia_nfe'
  | 'conferencia_cte'
  | 'resumo_final'
  | 'recebido';

/** Decide qual bloco renderizar no workspace conforme estado consolidado. */
export function resolverConteudoWorkspace(
  row: CentralDfeDocumento,
  estado: string,
  forcarConferencia = false,
): WorkspaceConteudo {
  const st = (estado || '').toUpperCase();

  if (isCteTransportadora(row)) {
    if (['EM_CONFERENCIA', 'CONFERIDO', 'DIVERGENTE', 'BLOQUEADO'].includes(st) || forcarConferencia) {
      return 'conferencia_cte';
    }
    if (st === 'XML_DISPONIVEL' || !row.xml_armazenado) return 'xml_disponivel';
    return 'resumo_final';
  }

  if (forcarConferencia) return 'conferencia_nfe';

  if (st === 'PRECISA_MANIFESTAR' || st === 'RECEBIDO') return 'manifestacao';
  if (st === 'XML_DISPONIVEL') return 'xml_disponivel';
  if (['EM_CONFERENCIA', 'CONFERIDO', 'DIVERGENTE', 'BLOQUEADO'].includes(st)) {
    return 'conferencia_nfe';
  }
  if (['ESTOQUE_APLICADO', 'CONCLUIDO'].includes(st)) return 'resumo_final';
  return 'recebido';
}

export function abaInicialCteWorkspace(estado: string): 'conferencia' | 'resumo' {
  const st = (estado || '').toUpperCase();
  if (['EM_CONFERENCIA', 'DIVERGENTE', 'BLOQUEADO'].includes(st)) return 'conferencia';
  if (st === 'CONFERIDO') return 'conferencia';
  return 'resumo';
}
