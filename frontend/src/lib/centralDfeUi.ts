import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import type { StatusXmlDestinada } from '@/services/api/manifestacaoDestinatario';
import {
  LABEL_MANIFESTACAO_NAO_APLICAVEL,
  LABEL_XML_DISPONIVEL,
  LABEL_XML_ERRO,
  LABEL_XML_NAO_APLICAVEL,
  LABEL_XML_PENDENTE,
  LABEL_XML_ARMAZENADO,
  badgeXml,
  isNfeFornecedorAplicavel,
} from '@/lib/manifestacaoDestinatarioUi';

export const LABEL_ABRIR_BASE_NFE = 'Abrir NF-e';
export const LABEL_ABRIR_BASE_CTE = 'Abrir CT-e';
export const LABEL_ARMAZENAR_XML_CTE = 'Armazenar XML CT-e';
export const LABEL_VER_CTE = 'Ver CT-e';
export const LABEL_CONFERIR_CTE = 'Conferir CT-e';
export const TOOLTIP_ABRIR_BASE_NFE = 'Abrir na Base NF-e Entrada Importada';
export const TOOLTIP_ABRIR_BASE_CTE = 'Abrir na Base CT-e Importada';
export const TOOLTIP_VER_CTE = 'Ver detalhes do CT-e na Central DF-e';
export const TOOLTIP_CONFERIR_CTE = 'Conferir, marcar divergente ou ignorar CT-e';
export const TOOLTIP_ARMAZENAR_XML_NFE =
  'Baixar/armazenar XML na Base NF-e Entrada Importada (ação manual com confirmação)';
export const TOOLTIP_ARMAZENAR_XML_CTE =
  'Armazenar XML CT-e na Base CT-e Importada (ação manual com confirmação)';

export function labelStatusXmlManifestacao(status: StatusXmlDestinada | string): string {
  const map: Record<string, string> = {
    BAIXADO: LABEL_XML_ARMAZENADO,
    DISPONIVEL: LABEL_XML_DISPONIVEL,
    RESUMO: LABEL_XML_PENDENTE,
    PENDENTE: LABEL_XML_PENDENTE,
    ERRO: LABEL_XML_ERRO,
  };
  return map[status] || LABEL_XML_PENDENTE;
}

export function statusXmlCteExibicao(row: CentralDfeDocumento): { label: string; badge: string } {
  if (row.tipo_documento !== 'CTE') {
    return { label: LABEL_XML_NAO_APLICAVEL, badge: 'pendente' };
  }
  if (row.xml_status === 'ERRO') {
    return { label: LABEL_XML_ERRO, badge: 'erro' };
  }
  if (row.xml_armazenado || row.xml_status === 'ARMAZENADO') {
    return { label: LABEL_XML_ARMAZENADO, badge: 'conferida' };
  }
  return { label: LABEL_XML_PENDENTE, badge: 'pendente' };
}

export function statusManifestacaoCteExibicao(): { label: string; badge: string } {
  return { label: LABEL_MANIFESTACAO_NAO_APLICAVEL, badge: 'inativo' };
}

export function podeArmazenarXmlCte(row: CentralDfeDocumento): boolean {
  return row.tipo_documento === 'CTE' && !row.xml_armazenado && row.xml_status !== 'ARMAZENADO';
}

export function podeAbrirBaseImportada(row: CentralDfeDocumento): boolean {
  return Boolean(row.xml_armazenado || row.xml_status === 'ARMAZENADO');
}

/** @deprecated use podeAbrirBaseImportada */
export const podeVerXmlArmazenado = podeAbrirBaseImportada;

export function rotaAbrirBaseImportada(row: CentralDfeDocumento): string {
  if (row.tipo_documento === 'NFE_ENTRADA') {
    return row.detalhe_rota || `/nfe-entrada-historica-importada?id=${row.id}`;
  }
  if (row.tipo_documento === 'CTE') {
    return row.detalhe_rota || `/cte-historico-importado?id=${row.id}`;
  }
  return row.detalhe_rota || '';
}

/** @deprecated use rotaAbrirBaseImportada */
export const rotaVerXml = rotaAbrirBaseImportada;

export function labelAbrirBaseImportada(row: CentralDfeDocumento): string {
  return row.tipo_documento === 'CTE' ? LABEL_ABRIR_BASE_CTE : LABEL_ABRIR_BASE_NFE;
}

export function tooltipAbrirBaseImportada(row: CentralDfeDocumento): string {
  return row.tipo_documento === 'CTE' ? TOOLTIP_ABRIR_BASE_CTE : TOOLTIP_ABRIR_BASE_NFE;
}

export function xmlBadgeFromManifestacaoStatus(status: StatusXmlDestinada | string): string {
  if (status === 'BAIXADO' || status === 'ARMAZENADO') return 'conferida';
  if (status === 'ERRO') return 'erro';
  if (status === 'DISPONIVEL') return 'processando';
  return badgeXml(status);
}

export function isCteTransportadora(row: Pick<CentralDfeDocumento, 'tipo_documento'>): boolean {
  return row.tipo_documento === 'CTE';
}

export function isNfeFornecedor(row: Pick<CentralDfeDocumento, 'tipo_documento'>): boolean {
  return isNfeFornecedorAplicavel(row);
}
