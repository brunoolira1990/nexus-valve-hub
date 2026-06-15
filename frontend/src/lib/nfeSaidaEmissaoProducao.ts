/** Helpers UI — emissão NF-e Saída produção SEFAZ (Fase 3C). */

import { isNfeAmbienteProducao } from '@/lib/empresaNfeAmbiente';
import { extrairErrosXsd, formatNfeErrosLista, type NFeRespostaValidacaoXsd } from '@/lib/nfeXsdErros';

export const TEXTO_CONFIRMACAO_PRODUCAO = 'PRODUCAO SEFAZ';
export const CONFIRMACAO_AMBIENTE_PRODUCAO = 'PRODUCAO_SEFAZ';

export type NFeEmissaoProducaoConferencia = {
  habilitada?: boolean;
  usuario_pode_emitir?: boolean;
  pode_emitir?: boolean;
  pode_tentar_emitir?: boolean;
  motivo_bloqueio?: string;
  motivos_bloqueio?: string[];
  ambiente_label?: string;
  ambiente_emissao_nfe?: string;
  status_producao_label?: string;
  pronta?: boolean;
  pendencias?: Array<{ codigo?: string; mensagem?: string; severidade?: string }>;
  alertas?: Array<{ codigo?: string; mensagem?: string; severidade?: string }>;
  emitente?: { id?: number | null; nome?: string };
  destinatario?: { id?: number | null; nome?: string };
  valor_total?: number;
  serie_nfe?: string;
  numero_nfe?: string;
  numeracao_producao?: { serie?: string; proximo_numero?: number } | null;
  status_emissao_sefaz?: string;
  autorizada_producao?: boolean;
  protocolo_autorizacao?: string;
  cstat_autorizacao?: string;
  motivo_autorizacao?: string;
  chave_acesso?: string;
  tem_xml_autorizado?: boolean;
};

export type NFeEmissaoProducaoPermissoes = {
  producao_habilitada?: boolean;
  usuario_pode_emitir_producao?: boolean;
  pode_emitir_producao?: boolean;
  pode_tentar_emitir_producao?: boolean;
  motivo_emitir_producao_bloqueado?: string;
  motivos_bloqueio_producao?: string[];
};

export function exibirBlocoProducaoSefaz(
  emissao?: NFeEmissaoProducaoConferencia | null,
  permissoes?: NFeEmissaoProducaoPermissoes | null,
): boolean {
  if (emissao?.autorizada_producao) return true;
  if (!isNfeAmbienteProducao(emissao?.ambiente_emissao_nfe)) return false;
  if (permissoes?.producao_habilitada) return true;
  if (emissao?.habilitada) return true;
  return Boolean(emissao?.status_emissao_sefaz?.includes('PRODUCAO'));
}

export function podeExibirBotaoEmitirProducao(
  emissao?: NFeEmissaoProducaoConferencia | null,
  permissoes?: NFeEmissaoProducaoPermissoes | null,
): boolean {
  return Boolean(
    permissoes?.producao_habilitada
    && permissoes?.usuario_pode_emitir_producao
    && permissoes?.pode_tentar_emitir_producao
    && !emissao?.autorizada_producao,
  );
}

export function botaoEmitirProducaoHabilitado(
  emissao?: NFeEmissaoProducaoConferencia | null,
  permissoes?: NFeEmissaoProducaoPermissoes | null,
  checklistApi?: { pronta?: boolean } | null,
): boolean {
  const prontaChecklist = checklistApi?.pronta ?? emissao?.pronta;
  return Boolean(
    permissoes?.pode_emitir_producao
    && prontaChecklist
    && !emissao?.autorizada_producao,
  );
}

export function confirmacaoProducaoValida(
  checkboxMarcado: boolean,
  textoDigitado: string,
): boolean {
  return checkboxMarcado && textoDigitado.trim().toUpperCase() === TEXTO_CONFIRMACAO_PRODUCAO;
}

export function montarPayloadEmitirProducao() {
  return {
    confirmar_emissao_producao: true,
    confirmar_ambiente: CONFIRMACAO_AMBIENTE_PRODUCAO,
  };
}

export function mensagemEmissaoProducaoResposta(res: {
  ok?: boolean;
  autorizado?: boolean;
  cstat?: string;
  cStat?: string;
  xmotivo?: string;
  xMotivo?: string;
  mensagem?: string;
  erros?: unknown[];
  erros_xsd?: NFeRespostaValidacaoXsd['erros_xsd'];
  validacao_xsd?: NFeRespostaValidacaoXsd['validacao_xsd'];
  etapa?: string;
  protocolo?: string;
  protocolo_autorizacao?: string;
  nfe?: { cstat?: string; xmotivo?: string; protocolo?: string };
  lote?: { cstat?: string; xmotivo?: string };
}): { tipo: 'sucesso' | 'rejeicao' | 'tecnico' | 'lote_sem_prot'; texto: string } {
  const cstatNfe = res.nfe?.cstat ?? res.cstat ?? res.cStat ?? '';
  const cstatLote = res.lote?.cstat ?? '';
  const xmotivoNfe = res.nfe?.xmotivo ?? res.xmotivo ?? res.xMotivo ?? '';
  const errosXsd = extrairErrosXsd(res);
  const errosTxt = errosXsd.length
    ? formatNfeErrosLista(errosXsd)
    : formatNfeErrosLista(res.erros);
  const msgBase = res.mensagem || xmotivoNfe || errosTxt || 'Emissão produção não concluída.';
  if (res.ok || res.autorizado) {
    const proto = res.protocolo || res.protocolo_autorizacao || res.nfe?.protocolo || '';
    const linha = cstatNfe
      ? `cStat ${cstatNfe}: ${xmotivoNfe || msgBase}${proto ? ` · Protocolo ${proto}` : ''}`
      : msgBase;
    return { tipo: 'sucesso', texto: linha };
  }
  if (cstatNfe && cstatNfe !== 'ERRO' && cstatNfe !== cstatLote) {
    return { tipo: 'rejeicao', texto: `cStat ${cstatNfe}: ${xmotivoNfe || msgBase}`.trim() };
  }
  if (cstatLote === '104' && !cstatNfe) {
    return { tipo: 'lote_sem_prot', texto: `Lote processado (cStat 104) sem protocolo NF-e. ${msgBase}`.trim() };
  }
  const etapaTxt = res.etapa ? `Etapa: ${res.etapa}. ` : '';
  const detalheXsd = errosTxt && !msgBase.includes(errosTxt) ? ` (${errosTxt})` : errosTxt && msgBase.includes(errosTxt) ? '' : '';
  return { tipo: 'tecnico', texto: `${etapaTxt}${msgBase}${detalheXsd}`.trim() };
}

export function avisoProducaoDesabilitada(
  permissoes?: NFeEmissaoProducaoPermissoes | null,
  emissao?: NFeEmissaoProducaoConferencia | null,
): string {
  if (permissoes?.producao_habilitada === false || emissao?.habilitada === false) {
    return 'Emissão produção SEFAZ desabilitada neste ambiente.';
  }
  if (permissoes?.producao_habilitada && !permissoes?.usuario_pode_emitir_producao) {
    return permissoes.motivo_emitir_producao_bloqueado
      || 'Seu perfil não possui permissão para emitir NF-e em produção SEFAZ.';
  }
  return permissoes?.motivo_emitir_producao_bloqueado || emissao?.motivo_bloqueio || '';
}
