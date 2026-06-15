/** Ambiente de emissão NF-e Saída — resolução na conferência. */

import { formatAmbienteNfe } from '@/lib/nfeSaidaApresentacaoFormat';
import { isNfeAmbienteProducao } from '@/lib/empresaNfeAmbiente';
import type { NFeSaidaConferenciaPayload } from '@/services/api/fiscal';

export const MSG_AMBIENTE_NAO_DEFINIDO =
  'Ambiente de emissão da NF-e não definido. Revise o ambiente fiscal antes de preparar emissão.';

export type NumeracaoCadastroNfe = {
  modelo_documento?: string;
  serie?: string;
  proximo_numero?: number;
};

export function ambienteEmissaoNfeDefinido(ambiente?: string | null): boolean {
  const raw = (ambiente || '').trim().toLowerCase();
  return raw === 'producao' || raw === 'homologacao';
}

export function resolverAmbienteEmissaoNfeConferencia(
  conf: Pick<NFeSaidaConferenciaPayload, 'apresentacao' | 'emissao_sefaz' | 'emissao_producao' | 'permissoes'>,
): string {
  return (
    conf.apresentacao?.ambiente_emissao ??
    conf.emissao_sefaz?.ambiente_emissao ??
    conf.emissao_producao?.ambiente_emissao_nfe ??
    ''
  )
    .trim()
    .toLowerCase();
}

export function labelAmbienteEmissaoNfeConferencia(
  conf: Pick<NFeSaidaConferenciaPayload, 'apresentacao' | 'emissao_sefaz' | 'emissao_producao' | 'permissoes'>,
): string {
  const raw = resolverAmbienteEmissaoNfeConferencia(conf);
  if (!ambienteEmissaoNfeDefinido(raw)) return '—';
  return formatAmbienteNfe(raw);
}

export function resolverNumeracaoCadastroConferencia(
  conf: Pick<NFeSaidaConferenciaPayload, 'emissao_sefaz' | 'emissao_producao'>,
  ambienteRaw: string,
): NumeracaoCadastroNfe | null {
  if (isNfeAmbienteProducao(ambienteRaw)) {
    return conf.emissao_sefaz?.numeracao_producao ?? conf.emissao_producao?.numeracao_producao ?? null;
  }
  if ((ambienteRaw || '').trim().toLowerCase() === 'homologacao') {
    return conf.emissao_sefaz?.numeracao_homologacao ?? null;
  }
  return null;
}

export function labelProximaNumeracaoCadastro(ambienteRaw: string): string {
  if (isNfeAmbienteProducao(ambienteRaw)) {
    return 'Próxima numeração produção (cadastro)';
  }
  return 'Próxima numeração homologação (cadastro)';
}
