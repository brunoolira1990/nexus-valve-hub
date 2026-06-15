import type { NFeSaidaEfeitosEvento } from '@/services/api/fiscal';
import type { NFeSaidaConferenciaPayload } from '@/services/api/fiscal';
import type { NFeSaidaApresentacao } from '@/lib/nfeSaidaUi';
import type { NFeSaida } from '@/types';

export type NFeCartaCorrecaoContexto = {
  homologacao: boolean;
  ambienteLabel: string;
  emitente: string;
  destinatario: string;
  chaveAcesso: string;
  numero: string;
  serie: string;
  sequenciaPrevista: number;
};

export const CSTAT_CCE_REGISTRADO = new Set(['135', '136']);

export const MSG_O_QUE_CCE_NAO_PODE_CORRIGIR =
  'A CC-e não pode corrigir: valores ou bases de impostos; alíquotas; quantidades ou preços que alterem o total; ' +
  'dados cadastrais que mudem emitente ou destinatário; data de emissão ou saída; numeração da NF-e.';

export const MSG_CONFIRMACAO_TRANSMISSAO_CCE =
  'Esta ação transmite uma Carta de Correção Eletrônica para a SEFAZ.';

export const MSG_PREVIA_SEM_TRANSMISSAO =
  'Esta é apenas uma pré-visualização. Nenhum evento foi transmitido, assinado ou registrado na SEFAZ.';

const CSTAT_OK = CSTAT_CCE_REGISTRADO;

export function calcularSequenciaPrevistaCce(eventos: NFeSaidaEfeitosEvento[]): number {
  const registradas = eventos.filter((ev) => {
    if (ev.tipo_evento !== 'CARTA_CORRECAO_EMITIDA') return false;
    const cstat = String(ev.resumo?.cStat ?? ev.resumo?.cstat ?? '').trim();
    return !cstat || CSTAT_OK.has(cstat);
  }).length;
  return registradas + 1;
}

function resolverHomologacao(
  ambiente?: string | null,
  homologacaoHint?: boolean,
): boolean {
  if (typeof homologacaoHint === 'boolean') return homologacaoHint;
  return (ambiente || '').trim().toLowerCase() === 'homologacao';
}

export function buildCartaCorrecaoContextoFromNfe(
  nfe: NFeSaida,
  opts?: { homologacao?: boolean; eventos?: NFeSaidaEfeitosEvento[] },
): NFeCartaCorrecaoContexto {
  const ap = nfe.apresentacao;
  const emissao = nfe.resumo_emissao_sefaz;
  const ambienteRaw = ap?.ambiente_emissao ?? emissao?.ambiente_emissao ?? '';
  const homologacao = resolverHomologacao(ambienteRaw, opts?.homologacao);
  const nfeExt = nfe as NFeSaida & { empresa_emitente_nome?: string; chave_acesso?: string; serie?: string };

  return {
    homologacao,
    ambienteLabel: homologacao ? 'Homologação' : 'Produção',
    emitente: (nfeExt.empresa_emitente_nome ?? '—').trim() || '—',
    destinatario: (nfe.cliente_nome || '—').trim() || '—',
    chaveAcesso: (ap?.chave_acesso ?? emissao?.chave_acesso ?? nfeExt.chave_acesso ?? '').trim(),
    numero: (ap?.numero_fiscal ?? String(nfe.numero ?? '')).trim() || '—',
    serie: (ap?.serie_fiscal ?? nfeExt.serie ?? '—').trim() || '—',
    sequenciaPrevista: calcularSequenciaPrevistaCce(opts?.eventos ?? []),
  };
}

export function buildCartaCorrecaoContextoFromConferencia(
  conf: NFeSaidaConferenciaPayload,
  homologacao: boolean,
  eventos: NFeSaidaEfeitosEvento[] = [],
): NFeCartaCorrecaoContexto {
  const ap = conf.apresentacao as NFeSaidaApresentacao | undefined;
  const em = conf.emissao_sefaz;
  const nfe = conf.nfe as Record<string, unknown>;

  return {
    homologacao,
    ambienteLabel: homologacao ? 'Homologação' : 'Produção',
    emitente: String(nfe.empresa_emitente_nome ?? em?.emitente?.nome ?? '—').trim() || '—',
    destinatario: String(nfe.cliente_nome ?? em?.destinatario?.nome ?? '—').trim() || '—',
    chaveAcesso: (ap?.chave_acesso ?? em?.chave_acesso ?? '').trim(),
    numero: (ap?.numero_fiscal ?? em?.numero_nfe ?? String(nfe.numero ?? '')).trim() || '—',
    serie: (ap?.serie_fiscal ?? em?.serie_nfe ?? '—').trim() || '—',
    sequenciaPrevista: calcularSequenciaPrevistaCce(eventos),
  };
}
