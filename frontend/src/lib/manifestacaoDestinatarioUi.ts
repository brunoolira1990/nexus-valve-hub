import type { StatusManifestacao, StatusXmlDestinada } from '@/services/api/manifestacaoDestinatario';
import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import { labelStatusXmlManifestacao, xmlBadgeFromManifestacaoStatus } from '@/lib/centralDfeUi';

export const EVENTOS_MANIFESTACAO = [
  'CIENCIA_EMISSAO',
  'CONFIRMACAO_OPERACAO',
  'DESCONHECIMENTO',
  'OPERACAO_NAO_REALIZADA',
] as const;

export const STATUS_MANIFESTACAO_FINAL = new Set<StatusManifestacao>([
  'CONFIRMADA',
  'DESCONHECIDA',
  'NAO_REALIZADA',
]);

/** Manifestação concluída que normalmente libera download do XML na SEFAZ. */
export const STATUS_MANIFESTACAO_LIBERA_IMPORTAR_XML = new Set<StatusManifestacao>([
  'CIENTE',
  'CONFIRMADA',
  'NAO_REALIZADA',
]);

export const LABEL_MANIFESTACAO_NAO_APLICAVEL = 'Não aplicável';
export const LABEL_MANIFESTACAO_PENDENTE = 'Pendente manifestação';
export const LABEL_XML_NAO_APLICAVEL = 'Não aplicável';
export const LABEL_XML_PENDENTE = 'XML pendente';
export const LABEL_XML_DISPONIVEL = 'XML disponível';
export const LABEL_XML_ARMAZENADO = 'XML armazenado';
/** @deprecated use LABEL_XML_ARMAZENADO */
export const LABEL_XML_BAIXADO = LABEL_XML_ARMAZENADO;
export const LABEL_XML_ERRO = 'Erro ao armazenar';

export function isNfeFornecedorAplicavel(row: Pick<CentralDfeDocumento, 'tipo_documento'>): boolean {
  return row.tipo_documento === 'NFE_ENTRADA';
}

export function badgeManifestacao(status: string): string {
  const map: Record<string, string> = {
    PENDENTE: 'pendente',
    CIENTE: 'processando',
    CONFIRMADA: 'conferida',
    DESCONHECIDA: 'divergente',
    NAO_REALIZADA: 'cancelada',
    ERRO: 'erro',
  };
  return map[status] || 'pendente';
}

export function badgeXml(status: string): string {
  const map: Record<string, string> = {
    RESUMO: 'pendente',
    DISPONIVEL: 'processando',
    BAIXADO: 'conferida',
    ARMAZENADO: 'conferida',
    PENDENTE: 'pendente',
    ERRO: 'erro',
  };
  return map[status] || 'pendente';
}

export function statusManifestacaoExibicao(
  manifestacao: { status_manifestacao: StatusManifestacao; status_manifestacao_label: string } | null,
  row: Pick<CentralDfeDocumento, 'tipo_documento'>,
): { label: string; badge: string } {
  if (!isNfeFornecedorAplicavel(row)) {
    return { label: LABEL_MANIFESTACAO_NAO_APLICAVEL, badge: 'pendente' };
  }
  if (manifestacao) {
    return {
      label: manifestacao.status_manifestacao_label,
      badge: badgeManifestacao(manifestacao.status_manifestacao),
    };
  }
  return { label: LABEL_MANIFESTACAO_PENDENTE, badge: 'pendente' };
}

export function statusXmlExibicao(
  manifestacao: { status_xml: StatusXmlDestinada; status_xml_label: string } | null,
  row: Pick<CentralDfeDocumento, 'tipo_documento' | 'status_entrada' | 'xml_armazenado' | 'xml_status' | 'xml_status_label'>,
): { label: string; badge: string } {
  if (!isNfeFornecedorAplicavel(row)) {
    return { label: LABEL_XML_NAO_APLICAVEL, badge: 'pendente' };
  }
  if (row.xml_armazenado || row.xml_status === 'ARMAZENADO') {
    return { label: row.xml_status_label || LABEL_XML_ARMAZENADO, badge: 'conferida' };
  }
  if (manifestacao) {
    return {
      label: labelStatusXmlManifestacao(manifestacao.status_xml),
      badge: xmlBadgeFromManifestacaoStatus(manifestacao.status_xml),
    };
  }
  return { label: LABEL_XML_PENDENTE, badge: 'pendente' };
}

export function podeManifestarNfe(
  manifestacao: { status_manifestacao: StatusManifestacao } | null,
  row: Pick<CentralDfeDocumento, 'tipo_documento'>,
): boolean {
  if (!isNfeFornecedorAplicavel(row)) return false;
  if (!manifestacao) return true;
  return !STATUS_MANIFESTACAO_FINAL.has(manifestacao.status_manifestacao);
}

export function statusXmlPendenteArmazenamento(status: StatusXmlDestinada | string | undefined): boolean {
  return Boolean(
    status
    && status !== 'BAIXADO'
    && status !== 'ARMAZENADO'
    && status !== 'ERRO',
  );
}

export function podeArmazenarXmlNfe(
  manifestacao: { status_xml: StatusXmlDestinada; status_manifestacao?: StatusManifestacao } | null,
  row: Pick<CentralDfeDocumento, 'tipo_documento' | 'xml_armazenado' | 'xml_status'>,
): boolean {
  if (!isNfeFornecedorAplicavel(row)) return false;
  if (row.xml_armazenado || row.xml_status === 'ARMAZENADO') return false;
  if (!manifestacao) return false;
  if (!statusXmlPendenteArmazenamento(manifestacao.status_xml)) return false;
  if (manifestacao.status_xml === 'RESUMO') {
    return STATUS_MANIFESTACAO_LIBERA_IMPORTAR_XML.has(manifestacao.status_manifestacao);
  }
  return true;
}

export function podeBaixarXmlLinha(
  manifestacao: { status_xml: StatusXmlDestinada } | null,
  row: Pick<CentralDfeDocumento, 'tipo_documento' | 'xml_armazenado' | 'xml_status'>,
): boolean {
  return podeArmazenarXmlNfe(manifestacao, row);
}

export function xmlJaArmazenado(
  manifestacao: { status_xml: StatusXmlDestinada } | null,
  row: Pick<CentralDfeDocumento, 'xml_armazenado' | 'xml_status'>,
): boolean {
  if (row.xml_armazenado || row.xml_status === 'ARMAZENADO') return true;
  return manifestacao?.status_xml === 'BAIXADO';
}
