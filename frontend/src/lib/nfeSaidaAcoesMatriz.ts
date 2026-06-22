/**
 * Matriz de ações NF-e Saída por status e ambiente (ERP 4.0.15.x — pós-autorização).
 * Define visibilidade/habilitação de ações sem alterar fluxos fiscais sensíveis.
 */

import { ACTION_LABELS } from '@/lib/operationalUi';
import { formatAmbienteNfe } from '@/lib/nfeSaidaApresentacaoFormat';
import { isAutorizadaHomologacao, type ResumoEmissaoSefazNfe } from '@/lib/nfeSaidaUi';

export const GRUPO_ACAO_LABELS = {
  fiscal: 'Ações fiscais',
  documentos: 'Documentos',
  financeiras: 'Ações financeiras',
  futuras: 'Ações futuras',
} as const;

export type NFeSaidaGrupoAcao = keyof typeof GRUPO_ACAO_LABELS;

export const AVISO_HOMOLOG_SEM_VALOR_FISCAL =
  'NF-e de homologação não possui valor fiscal e não vira produção. Para produção, gere/emita uma NF-e real.';

export const AVISO_PRODUCAO_POS_AUTORIZACAO =
  'NF-e autorizada em produção. Cancelamento SEFAZ será disponibilizado em fase futura.';

export const AVISO_CANCELADA_CONSULTA =
  'NF-e cancelada na SEFAZ. Consulta e visualização de documentos locais apenas — sem validade fiscal para circulação.';

export type NFeSaidaCenarioAcao =
  | 'rascunho_conferencia'
  | 'homolog_autorizada'
  | 'producao_autorizada'
  | 'rejeitada_erro'
  | 'cancelada'
  | 'outro';

export type NFeSaidaAcaoId =
  | 'validar'
  | 'abrir_nfe'
  | 'danfe_previa'
  | 'danfe_autorizado'
  | 'xml_previo'
  | 'xml_autorizado'
  | 'historico'
  | 'copiar_chave'
  | 'emitir_homolog'
  | 'emitir_producao'
  | 'descartar_rascunho'
  | 'consulta_sefaz'
  | 'carta_correcao'
  | 'cancelamento'
  | 'enviar_danfe_xml'
  | 'gerar_contas_receber';

export type NFeSaidaAcaoConfig = {
  id: NFeSaidaAcaoId;
  grupo: NFeSaidaGrupoAcao;
  visivel: boolean;
  habilitada: boolean;
  futura?: boolean;
  label: string;
  title?: string;
};

export type NFeSaidaContextoAcao = {
  cenario: NFeSaidaCenarioAcao;
  ambienteLabel: string;
  ambienteRaw: string;
  isAmbienteProducao: boolean;
  autorizadaHomolog: boolean;
  autorizadaProducao: boolean;
  cancelada: boolean;
  temXmlAutorizado: boolean;
  chaveAcesso: string;
  avisoAmbiente: string | null;
  exibirAcoesFuturas: boolean;
  exibirPainelEmissaoProducao: boolean;
};

export type NFeSaidaEntradaContexto = {
  status?: string | null;
  status_emissao_sefaz?: string | null;
  resumo_emissao_sefaz?: ResumoEmissaoSefazNfe | null;
  ambiente_emissao?: string | null;
  chave_acesso?: string | null;
  tem_xml_autorizado?: boolean;
  autorizada_producao?: boolean;
};

export function isAutorizadaProducao(
  entrada: NFeSaidaEntradaContexto,
  emissaoSefaz?: ResumoEmissaoSefazNfe | null,
): boolean {
  if (entrada.autorizada_producao) return true;
  const st = (
    emissaoSefaz?.status_emissao_sefaz ??
    entrada.status_emissao_sefaz ??
    entrada.resumo_emissao_sefaz?.status_emissao_sefaz ??
    ''
  )
    .trim()
    .toUpperCase();
  if (st === 'AUTORIZADA_PRODUCAO' || st === 'AUTORIZADA') return true;
  const nfeSt = (entrada.status || '').trim().toUpperCase();
  return nfeSt === 'AUTORIZADA' || nfeSt === 'EMITIDA' || nfeSt === 'EMITIDO';
}

export function isRejeitadaOuErro(
  entrada: NFeSaidaEntradaContexto,
  emissaoSefaz?: ResumoEmissaoSefazNfe | null,
): boolean {
  const st = (
    emissaoSefaz?.status_emissao_sefaz ??
    entrada.status_emissao_sefaz ??
    entrada.resumo_emissao_sefaz?.status_emissao_sefaz ??
    ''
  )
    .trim()
    .toUpperCase();
  if (st === 'REJEITADA_HOMOLOGACAO' || st === 'REJEITADA' || st === 'ERRO_TRANSMISSAO') return true;
  const nfeSt = (entrada.status || '').trim().toUpperCase();
  return nfeSt.includes('REJEIT');
}

export function isCanceladaNfe(status?: string | null): boolean {
  const st = (status || '').trim().toUpperCase();
  return (
    st === 'CANCELADA' ||
    st === 'CANCELADA_INTERNA' ||
    st === 'CANCELADA_HOMOLOGACAO' ||
    st === 'CANCELADA_PRODUCAO' ||
    st === 'CANCELADO'
  );
}

export function resolverCenarioNfeSaida(
  entrada: NFeSaidaEntradaContexto,
  emissaoSefaz?: ResumoEmissaoSefazNfe | null,
): NFeSaidaCenarioAcao {
  if (isCanceladaNfe(entrada.status)) return 'cancelada';
  if (isAutorizadaProducao(entrada, emissaoSefaz)) return 'producao_autorizada';
  if (isAutorizadaHomologacao(entrada, emissaoSefaz)) return 'homolog_autorizada';
  if (isRejeitadaOuErro(entrada, emissaoSefaz)) return 'rejeitada_erro';
  const st = (entrada.status || '').trim().toUpperCase();
  if (st === 'RASCUNHO' || !st || st === 'PRONTA_PARA_EMISSAO') return 'rascunho_conferencia';
  return 'outro';
}

export function resolverContextoNfeSaida(
  entrada: NFeSaidaEntradaContexto,
  emissaoSefaz?: ResumoEmissaoSefazNfe | null,
): NFeSaidaContextoAcao {
  const cenario = resolverCenarioNfeSaida(entrada, emissaoSefaz);
  const autorizadaHomolog = cenario === 'homolog_autorizada';
  const autorizadaProducao = cenario === 'producao_autorizada';
  const ambienteRaw =
    entrada.ambiente_emissao ??
    emissaoSefaz?.ambiente_emissao ??
    entrada.resumo_emissao_sefaz?.ambiente_emissao ??
    (autorizadaHomolog ? 'homologacao' : autorizadaProducao ? 'producao' : '');
  const ambienteLabel = formatAmbienteNfe(ambienteRaw);
  const isAmbienteProducao = (ambienteRaw || '').trim().toLowerCase() === 'producao';
  const chave =
    (entrada.chave_acesso ?? '').trim() ||
    (emissaoSefaz as { chave_acesso?: string } | undefined)?.chave_acesso?.trim() ||
    '';

  let avisoAmbiente: string | null = null;
  if (cenario === 'cancelada') avisoAmbiente = AVISO_CANCELADA_CONSULTA;
  else if (autorizadaHomolog) avisoAmbiente = AVISO_HOMOLOG_SEM_VALOR_FISCAL;
  else if (autorizadaProducao) avisoAmbiente = AVISO_PRODUCAO_POS_AUTORIZACAO;
  else if (isAmbienteProducao && cenario === 'rascunho_conferencia') {
    avisoAmbiente =
      'Documento fiscal real — use o checklist e a emissão Produção SEFAZ abaixo. Homologação não se aplica a esta NF-e.';
  }

  return {
    cenario,
    ambienteLabel,
    ambienteRaw,
    isAmbienteProducao,
    autorizadaHomolog,
    autorizadaProducao,
    cancelada: cenario === 'cancelada',
    temXmlAutorizado: Boolean(
      entrada.tem_xml_autorizado ??
        (emissaoSefaz as { tem_xml_autorizado?: boolean } | undefined)?.tem_xml_autorizado,
    ),
    chaveAcesso: chave,
    avisoAmbiente,
    exibirAcoesFuturas: autorizadaHomolog || autorizadaProducao,
    exibirPainelEmissaoProducao:
      isAmbienteProducao && !autorizadaHomolog && cenario !== 'producao_autorizada' && cenario !== 'cancelada',
  };
}

export function podeConsultarSituacaoSefaz(ctx: NFeSaidaContextoAcao): boolean {
  return Boolean(ctx.chaveAcesso) && (ctx.autorizadaHomolog || ctx.autorizadaProducao);
}

export function podeEmitirCartaCorrecao(ctx: NFeSaidaContextoAcao): boolean {
  if (ctx.cenario === 'cancelada') return false;
  return podeConsultarSituacaoSefaz(ctx);
}

export function podeCancelarNfeSefaz(ctx: NFeSaidaContextoAcao): boolean {
  if (ctx.cenario === 'cancelada') return false;
  return podeConsultarSituacaoSefaz(ctx);
}

export function podeEnviarDanfeXml(ctx: NFeSaidaContextoAcao): boolean {
  if (ctx.cenario === 'cancelada') return false;
  return (ctx.autorizadaHomolog || ctx.autorizadaProducao) && ctx.temXmlAutorizado;
}

const FUTURAS_BASE: Omit<NFeSaidaAcaoConfig, 'visivel' | 'habilitada'>[] = [];

function acao(
  partial: Omit<NFeSaidaAcaoConfig, 'visivel' | 'habilitada'> & { visivel?: boolean; habilitada?: boolean },
): NFeSaidaAcaoConfig {
  return {
    visivel: partial.visivel ?? true,
    habilitada: partial.habilitada ?? true,
    ...partial,
  };
}

/** Retorna lista plana de ações visíveis agrupadas por grupo. */
export function obterMatrizAcoesNfeSaida(
  ctx: NFeSaidaContextoAcao,
  opts?: {
    podeDescartar?: boolean;
    podeEmitirHomolog?: boolean;
    podeEmitirProducao?: boolean;
    podeValidar?: boolean;
  },
): NFeSaidaAcaoConfig[] {
  const { cenario } = ctx;
  const acoes: NFeSaidaAcaoConfig[] = [];

  if (cenario === 'homolog_autorizada') {
    acoes.push(
      acao({ id: 'abrir_nfe', grupo: 'documentos', label: 'Abrir NF-e' }),
      acao({ id: 'danfe_autorizado', grupo: 'documentos', label: 'DANFE (homologação)' }),
      acao({
        id: 'xml_autorizado',
        grupo: 'documentos',
        label: 'XML autorizado',
        habilitada: ctx.temXmlAutorizado,
        title: ctx.temXmlAutorizado ? undefined : 'XML autorizado indisponível',
      }),
      acao({ id: 'historico', grupo: 'documentos', label: 'Ver histórico' }),
      acao({
        id: 'enviar_danfe_xml',
        grupo: 'documentos',
        label: ACTION_LABELS.enviarDanfeXml,
        habilitada: podeEnviarDanfeXml(ctx),
        title: podeEnviarDanfeXml(ctx) ? undefined : 'XML autorizado ou DANFE indisponível',
      }),
    );
    if (podeConsultarSituacaoSefaz(ctx)) {
      acoes.push(acao({ id: 'consulta_sefaz', grupo: 'fiscal', label: 'Consulta SEFAZ' }));
    }
    if (podeEmitirCartaCorrecao(ctx)) {
      acoes.push(acao({ id: 'carta_correcao', grupo: 'fiscal', label: ACTION_LABELS.cartaCorrecao }));
    }
    if (podeCancelarNfeSefaz(ctx)) {
      acoes.push(acao({ id: 'cancelamento', grupo: 'fiscal', label: ACTION_LABELS.cancelarNfe }));
    }
  } else if (cenario === 'producao_autorizada') {
    acoes.push(
      acao({ id: 'abrir_nfe', grupo: 'documentos', label: 'Abrir NF-e' }),
      acao({ id: 'danfe_autorizado', grupo: 'documentos', label: 'DANFE autorizado' }),
      acao({
        id: 'xml_autorizado',
        grupo: 'documentos',
        label: 'XML autorizado',
        habilitada: ctx.temXmlAutorizado,
      }),
      acao({
        id: 'copiar_chave',
        grupo: 'documentos',
        label: 'Copiar chave',
        habilitada: Boolean(ctx.chaveAcesso),
        title: ctx.chaveAcesso ? undefined : 'Chave de acesso indisponível',
      }),
      acao({ id: 'historico', grupo: 'documentos', label: 'Ver histórico' }),
      acao({
        id: 'enviar_danfe_xml',
        grupo: 'documentos',
        label: ACTION_LABELS.enviarDanfeXml,
        habilitada: podeEnviarDanfeXml(ctx),
        title: podeEnviarDanfeXml(ctx) ? undefined : 'XML autorizado ou DANFE indisponível',
      }),
    );
    if (podeConsultarSituacaoSefaz(ctx)) {
      acoes.push(acao({ id: 'consulta_sefaz', grupo: 'fiscal', label: 'Consulta SEFAZ' }));
    }
    if (podeEmitirCartaCorrecao(ctx)) {
      acoes.push(acao({ id: 'carta_correcao', grupo: 'fiscal', label: ACTION_LABELS.cartaCorrecao }));
    }
    if (podeCancelarNfeSefaz(ctx)) {
      acoes.push(acao({ id: 'cancelamento', grupo: 'fiscal', label: ACTION_LABELS.cancelarNfe }));
    }
  } else if (cenario === 'cancelada') {
    acoes.push(
      acao({ id: 'abrir_nfe', grupo: 'documentos', label: 'Abrir NF-e' }),
      acao({
        id: 'danfe_autorizado',
        grupo: 'documentos',
        label: 'DANFE cancelado',
        habilitada: ctx.temXmlAutorizado,
        title: ctx.temXmlAutorizado
          ? 'Documento cancelado — sem validade fiscal para circulação.'
          : 'XML autorizado local indisponível.',
      }),
      acao({
        id: 'xml_autorizado',
        grupo: 'documentos',
        label: 'XML autorizado',
        habilitada: ctx.temXmlAutorizado,
        title: ctx.temXmlAutorizado ? undefined : 'XML autorizado local indisponível.',
      }),
      acao({
        id: 'copiar_chave',
        grupo: 'documentos',
        label: 'Copiar chave',
        habilitada: Boolean(ctx.chaveAcesso),
        title: ctx.chaveAcesso ? undefined : 'Chave de acesso indisponível',
      }),
      acao({ id: 'historico', grupo: 'documentos', label: 'Ver histórico' }),
    );
  } else if (cenario === 'rascunho_conferencia' || cenario === 'rejeitada_erro') {
    if (opts?.podeValidar !== false) {
      acoes.push(acao({ id: 'validar', grupo: 'fiscal', label: 'Validar' }));
    }
    const homologAtiva = !ctx.isAmbienteProducao;
    if (homologAtiva && cenario === 'rejeitada_erro' && opts?.podeEmitirHomolog) {
      acoes.push(acao({ id: 'emitir_homolog', grupo: 'fiscal', label: ACTION_LABELS.reenviarNfe }));
    } else if (homologAtiva && cenario === 'rascunho_conferencia' && opts?.podeEmitirHomolog) {
      acoes.push(acao({ id: 'emitir_homolog', grupo: 'fiscal', label: ACTION_LABELS.emitirNfe }));
    }
    // Emissão produção/homologação: botões dedicados no painel/modal — não duplicar na matriz.
    acoes.push(
      acao({ id: 'abrir_nfe', grupo: 'documentos', label: 'Abrir NF-e' }),
      acao({ id: 'danfe_previa', grupo: 'documentos', label: 'DANFE prévia' }),
      acao({ id: 'xml_previo', grupo: 'documentos', label: 'XML prévio' }),
    );
    if (opts?.podeDescartar) {
      acoes.push(acao({ id: 'descartar_rascunho', grupo: 'fiscal', label: ACTION_LABELS.descartarRascunho }));
    }
  } else {
    acoes.push(
      acao({ id: 'abrir_nfe', grupo: 'documentos', label: 'Abrir NF-e' }),
      acao({ id: 'danfe_previa', grupo: 'documentos', label: 'DANFE' }),
      acao({ id: 'xml_previo', grupo: 'documentos', label: 'XML' }),
    );
  }

  acoes.push(
    acao({
      id: 'gerar_contas_receber',
      grupo: 'financeiras',
      label: 'Gerar contas a receber',
      visivel: cenario === 'producao_autorizada' || cenario === 'rascunho_conferencia',
      habilitada: false,
      title: 'Gerenciado pelo bloco financeiro abaixo',
    }),
  );

  if (ctx.exibirAcoesFuturas && FUTURAS_BASE.length) {
    for (const f of FUTURAS_BASE) {
      acoes.push(acao({ ...f, visivel: true, habilitada: false }));
    }
  } else if (cenario === 'rascunho_conferencia' || cenario === 'rejeitada_erro') {
    if (FUTURAS_BASE[0]) {
      acoes.push(acao({ ...FUTURAS_BASE[0], visivel: true, habilitada: false }));
    }
  }

  return acoes.filter((a) => a.visivel);
}

export function agruparAcoesPorGrupo(acoes: NFeSaidaAcaoConfig[]): Record<NFeSaidaGrupoAcao, NFeSaidaAcaoConfig[]> {
  const grupos: Record<NFeSaidaGrupoAcao, NFeSaidaAcaoConfig[]> = {
    fiscal: [],
    documentos: [],
    financeiras: [],
    futuras: [],
  };
  for (const a of acoes) {
    if (a.grupo === 'financeiras' && a.id === 'gerar_contas_receber') continue;
    grupos[a.grupo].push(a);
  }
  return grupos;
}
