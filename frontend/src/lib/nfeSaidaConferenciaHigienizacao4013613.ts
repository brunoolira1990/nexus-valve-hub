/** ERP 4.0.13.6.13 — helpers de higienização XML / indicadores fiscais na conferência NF-e. */

export type HigienizacaoItem = {
  tipo?: string;
  codigo?: string;
  mensagem?: string;
};

export type HigienizacaoXmlResumo = {
  tem_xml_transmissao?: boolean;
  total_pendencias?: number;
  aprovado?: boolean;
  itens?: HigienizacaoItem[];
};

export type IndicadoresFiscaisConferencia = {
  ind_final?: string;
  ind_pres?: string;
  indicadores_fiscais_confirmados?: boolean;
};

export const SECAO_HIGIENIZACAO_XML = 'Higienização XML de transmissão';

export function isXmlTransmissaoPreview(xml: string | undefined | null): boolean {
  const u = (xml || '').toUpperCase();
  return u.includes('NFEPREVIEW') || u.includes('NÃO TRANSMITIR') || u.includes('NAO TRANSMITIR');
}

export function pendenciaIndicadoresNaoConfirmados(ind?: IndicadoresFiscaisConferencia | null): boolean {
  return !ind?.indicadores_fiscais_confirmados;
}

export function pendenciaHigienizacaoCritica(hig?: HigienizacaoXmlResumo | null): boolean {
  if (!hig) return true;
  if ((hig.total_pendencias ?? 0) > 0) return true;
  if (!hig.tem_xml_transmissao) return true;
  return !hig.aprovado;
}

export function badgeHigienizacaoXml(hig?: HigienizacaoXmlResumo | null): {
  label: string;
  className: string;
} {
  if (hig?.tem_xml_transmissao && hig.aprovado) {
    return { label: 'XML de transmissão validado', className: 'erp-badge-success' };
  }
  if ((hig?.total_pendencias ?? 0) > 0) {
    return {
      label: `${hig?.total_pendencias ?? 0} pendência(s)`,
      className: 'erp-badge-danger',
    };
  }
  return { label: 'Aguardando geração do XML de transmissão', className: 'erp-badge-warning' };
}

export function mapIndFinalParaPayload(consumidorFinal: boolean): string {
  return consumidorFinal ? '1' : '0';
}

export function mapIndPresParaPayload(codigo: string): string {
  const v = (codigo || '1').trim();
  return v || '1';
}

export function podeMarcarProntaComHigienizacao(
  podeMarcarProntaBase: boolean,
  ind?: IndicadoresFiscaisConferencia | null,
  hig?: HigienizacaoXmlResumo | null,
): boolean {
  if (!podeMarcarProntaBase) return false;
  if (pendenciaIndicadoresNaoConfirmados(ind)) return false;
  if (pendenciaHigienizacaoCritica(hig)) return false;
  return true;
}
