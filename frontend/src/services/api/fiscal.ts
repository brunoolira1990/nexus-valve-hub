import axios from 'axios';
import api, { clearAuthSession, SESSION_EXPIRED_MESSAGE } from './config';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';
import type {
  CTeEntrada,
  ItemNFe,
  NFeEntrada,
  NFeEntradaPropriaImportResultado,
  NFeSaida,
  NFeSaidaListItem,
} from '@/types';
import type { DiagnosticoFiscalPreview, EnderecoFiscalResumo } from '@/lib/enderecoFiscal';
import {
  downloadBlobFile,
  parseContentDispositionFilename,
  readBlobErrorMessage,
  visualizarPdfEmNovaAba,
} from '@/lib/downloadBlobFile';
import type { AxiosResponse } from 'axios';

/** Remove campos só de UI; em PATCH mantém `id` (obrigatório em NF-e de faturamento). */
export function stripNfItens(itens: Array<ItemNFe | Record<string, unknown>>, opts?: { keepId?: boolean }) {
  return itens.map((raw) => {
    const item = raw as ItemNFe & Record<string, unknown>;
    const { id, produto_nome: _p, corrida_numero: _c, ...rest } = item;
    const row: Record<string, unknown> = { ...rest };
    if (opts?.keepId && id != null && id !== '') {
      row.id = id;
    }
    return row;
  });
}

const nfEnt = 'nf-entradas/';
const nfSai = 'nf-saidas/';

async function resolveBlobDownload(
  res: AxiosResponse<Blob>,
  fallbackFilename: string,
  errorFallback: string,
): Promise<{ blob: Blob; filename: string }> {
  const contentType = String(res.headers['content-type'] || '');
  const isJson =
    contentType.includes('application/json') ||
    (res.data instanceof Blob && res.data.type.includes('json'));
  if (res.status >= 400 || isJson) {
    const msg = await readBlobErrorMessage(res.data, errorFallback);
    throw Object.assign(new Error(msg), { response: res });
  }
  if (!(res.data instanceof Blob) || !res.data.size) {
    throw new Error('O arquivo retornado está vazio.');
  }
  const filename =
    parseContentDispositionFilename(res.headers['content-disposition']) || fallbackFilename;
  return { blob: res.data, filename };
}
const cte = 'cte-entradas/';

export const nfeEntradasService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<NFeEntrada>>(nfEnt, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<NFeEntrada[] | PaginatedResponse<NFeEntrada>>(nfEnt, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<NFeEntrada>(`${nfEnt}${id}/`)).data,
  create: async (data: Omit<NFeEntrada, 'id'>) => {
    const { fornecedor_nome: _fn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<NFeEntrada>(nfEnt, {
        ...rest,
        itens: stripNfItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<NFeEntrada>) => {
    const { fornecedor_nome: _fn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...rest };
    if (itens) payload.itens = stripNfItens(itens);
    return (await api.patch<NFeEntrada>(`${nfEnt}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${nfEnt}${id}/`);
  },
  importarEntradaPropriaEmitida: async (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append('arquivos', f));
    return (
      await api.post<NFeEntradaPropriaImportResultado>(`${nfEnt}importar-entrada-propria-emitida/`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    ).data;
  },
  criarEntradaPropriaEmitida: async (data: Omit<NFeEntrada, 'id' | 'fornecedor_nome'>) => {
    const { valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<NFeEntrada>(`${nfEnt}criar-entrada-propria-emitida/`, {
        ...rest,
        itens: stripNfItens(itens || []),
      })
    ).data;
  },
  validarEmissaoHomologacao: async (id: number) =>
    (
      await api.get<{
        ok: boolean;
        pronta: boolean;
        pendencias: Array<{ codigo?: string; mensagem?: string }>;
        alertas: Array<{ codigo?: string; mensagem?: string }>;
        mensagem?: string;
        ambiente?: string;
      }>(`${nfEnt}${id}/validar-emissao-homologacao/`, {
        validateStatus: (s) => s >= 200 && s < 500,
      })
    ).data,
  validarEmissaoProducao: async (id: number) =>
    (
      await api.get<{
        ok: boolean;
        pronta: boolean;
        pendencias: Array<{ codigo?: string; mensagem?: string }>;
        alertas: Array<{ codigo?: string; mensagem?: string }>;
        mensagem?: string;
        ambiente?: string;
      }>(`${nfEnt}${id}/validar-emissao-producao/`, {
        validateStatus: (s) => s >= 200 && s < 500,
      })
    ).data,
  reservarNumeracao: async (id: number) =>
    (
      await api.post<{
        ok: boolean;
        nf_entrada_id: number;
        serie_nfe: string;
        numero_nfe: string;
        chave_acesso: string;
        ambiente_emissao?: string;
        status_emissao_sefaz?: string;
      }>(`${nfEnt}${id}/reservar-numeracao/`)
    ).data,
  previewXmlOficial: async (id: number) =>
    (await api.get<{ ok?: boolean; bloqueado?: boolean; xml?: string; mensagem?: string }>(`${nfEnt}${id}/preview-xml-oficial/`, {
      validateStatus: (s) => s >= 200 && s < 500,
    })).data,
  gerarXmlOficial: async (id: number) =>
    (await api.post<{ ok?: boolean; bloqueado?: boolean; xml?: string; mensagem?: string }>(`${nfEnt}${id}/gerar-xml-oficial-emissao/`)).data,
  emitirHomologacao: async (id: number) => {
    const res = await api.post<NFeEmissaoHomologacaoResponse>(
      `${nfEnt}${id}/emitir-homologacao/`,
      {},
      { timeout: 120_000, validateStatus: (s) => s >= 200 && s < 500 },
    );
    return res.data;
  },
  emitirProducao: async (
    id: number,
    payload: { confirmar_emissao_producao: boolean; confirmar_ambiente: string },
  ) => {
    const res = await api.post<NFeEmissaoProducaoResponse>(
      `${nfEnt}${id}/emitir-producao/`,
      payload,
      { timeout: 120_000, validateStatus: (s) => s >= 200 && s < 500 },
    );
    return res.data;
  },
};

export type ValidacaoNFeSaidaItem = {
  tipo: 'PENDENCIA' | 'ALERTA' | 'INFO';
  codigo: string;
  grupo: string;
  mensagem: string;
  item_id?: number | null;
};

export type NFeChecklistHomologacaoItem = {
  codigo: string;
  label: string;
  status: 'ok' | 'alerta' | 'bloqueado' | 'nao_aplicavel';
  mensagem: string;
  secao: string;
};

export type NFeChecklistHomologacaoResponse = {
  apto: boolean;
  status: 'aprovado' | 'aprovado_com_alertas' | 'alerta' | 'bloqueado';
  bloqueios: string[];
  alertas: string[];
  itens: NFeChecklistHomologacaoItem[];
  aviso_fixo?: string;
  mensagem: string;
  pedido_venda_id?: number | null;
  faturamento_id?: number | null;
  nfe_saida_id?: number | null;
};

export type NFeSaidaPreviewXmlResponse = {
  nfe_saida_id: number;
  numero: string;
  status: string;
  preview: boolean;
  oficial?: boolean;
  bloqueado?: boolean;
  xml?: string;
  xml_format?: string;
  versao_layout?: string;
  id_preview?: string;
  status_prontidao?: string;
  pendencias?: ValidacaoNFeSaidaItem[];
  alertas?: ValidacaoNFeSaidaItem[];
  avisos?: string[];
  mensagens?: string[];
  recomendacoes_aplicadas?: string[];
  recomendacoes_nao_aplicadas?: string[];
  marcas_preview?: string[];
  preliminar?: boolean;
  sem_autorizacao?: boolean;
  chave_acesso_preliminar?: string;
  chave_acesso_formatada?: string;
  serie_fiscal_preliminar?: string;
  numero_fiscal_preliminar?: string;
  politica_numeracao?: string;
  mensagem?: string;
};

export type DanfePreviewMeta = {
  origem?: string;
  renderer?: string;
  rendererLabel?: string;
  rendererOficial?: string;
};

export type NFeSaidaEfeitosEvento = {
  id: number;
  tipo_evento: string;
  status_anterior: string;
  status_novo: string;
  observacao: string;
  resumo: Record<string, unknown> | null;
  criado_por_nome?: string;
  criado_em: string;
};

export type NFeSaidaEventosResponse = {
  nfe_saida_id: number;
  eventos: NFeSaidaEfeitosEvento[];
};

export type NFeSaidaEfeitosAcaoResponse = {
  nfe_saida_id: number;
  status: string;
  pedido_id?: number | null;
  faturamento_id?: number | null;
  mensagens: string[];
};

export type NFeSaidaEfeitosEmissaoResponse = {
  nfe_saida_id: number;
  numero?: string;
  status: string;
  pedido_id: number | null;
  faturamento_id: number | null;
  pode_aplicar_autorizacao: boolean;
  pode_cancelar: boolean;
  efeitos_autorizacao: string[];
  efeitos_cancelamento: string[];
  estoque: { aplicacao_real: boolean; mensagem: string };
  financeiro: { aplicacao_real: boolean; mensagem: string };
  alertas: string[];
  eventos?: NFeSaidaEfeitosEvento[];
};

export type AtualizarImpostosAlteracao = {
  campo: string;
  label: string;
  antes: string;
  depois: string;
};

export type AtualizarImpostosItemPreview = {
  item_id: number;
  produto_nome: string;
  ncm: string;
  regra_encontrada: boolean;
  regra_fiscal_saida_id: number | null;
  regra_fiscal_saida_nome: string;
  alteracoes: AtualizarImpostosAlteracao[];
  alertas: string[];
  contexto_fiscal?: Record<string, unknown>;
  diagnostico?: DiagnosticoFiscalPreview;
};

export type TextoFiscalAlteracao = {
  campo: string;
  label: string;
  antes: string;
  depois: string;
  origem?: string;
};

export type RecomendacaoFiscalPreview = {
  origem: string;
  tipo: string;
  codigo?: string;
  mensagem: string;
};

export type TextosFiscaisPreview = {
  alteracoes: TextoFiscalAlteracao[];
  recomendacoes: RecomendacaoFiscalPreview[];
  origens?: string[];
};

export type AtualizarImpostosPreviewResponse = {
  nfe_saida_id: number;
  pode_aplicar: boolean;
  reaplicar_fiscal_pos_emissao?: boolean;
  bloqueado?: boolean;
  mensagem?: string;
  resumo: {
    itens_total: number;
    itens_com_regra: number;
    itens_sem_regra: number;
    itens_com_alteracao: number;
    itens_sem_alteracao: number;
    reforma_configurada: number;
    textos_fiscais_sugeridos?: number;
    recomendacoes_sugeridas?: number;
  };
  itens: AtualizarImpostosItemPreview[];
  textos_fiscais?: TextosFiscaisPreview;
  alertas: string[];
  contexto_fiscal?: {
    uf_origem?: string;
    uf_destino?: string;
    cidade_destino?: string;
    cliente_razao_social?: string;
    endereco_fiscal?: EnderecoFiscalResumo;
  };
  diagnosticos?: DiagnosticoFiscalPreview[];
};

export type AtualizarImpostosAplicarResponse = {
  nfe_saida_id: number;
  aplicado: boolean;
  itens_atualizados: number;
  preview: AtualizarImpostosPreviewResponse;
  conferencia: NFeSaidaConferenciaPayload;
  mensagem: string;
};

export type NFeSaidaProntidaoPayload = {
  nfe_saida_id?: number;
  status?: string;
  status_conferencia: string;
  status_conferencia_display: string;
  pode_validar: boolean;
  pode_marcar_pronta: boolean;
  total_pendencias: number;
  total_alertas: number;
  mensagens?: string[];
  ultima_validacao_em?: string | null;
  marcada_pronta_em?: string | null;
  conferencia_ultima_mensagem?: string;
};

export type ValidarConferenciaResponse = {
  prontidao: NFeSaidaProntidaoPayload;
  validacao: ValidacaoNFeSaidaResponse;
  conferencia: NFeSaidaConferenciaPayload;
  mensagem: string;
};

export type NFeSaidaConferenciaPayload = {
  nfe: Record<string, unknown>;
  itens: Array<Record<string, unknown>>;
  totais_comerciais: Record<string, unknown>;
  fiscal_atual: { por_item: unknown[]; totais: Record<string, string> };
  reforma_tributaria: {
    resumo: Record<string, unknown>;
    totais: Record<string, string>;
    itens: Array<{ item_id: number; descricao: string; status: string; dados: Record<string, string> }>;
  };
  transporte: Record<string, unknown>;
  observacoes: Record<string, string>;
  checklist: ValidacaoNFeSaidaResponse | null;
  checklist_desatualizado?: boolean;
  modo_carregamento?: string;
  indicadores_fiscais?: {
    ind_final: string;
    ind_final_label?: string;
    ind_pres: string;
    ind_pres_label?: string;
    indicadores_fiscais_confirmados?: boolean;
    ind_pres_opcoes?: Array<{ valor: string; label: string }>;
  };
  higienizacao_xml?: {
    aprovado?: boolean;
    total_pendencias?: number;
    itens?: ValidacaoNFeSaidaItem[];
    chave_acesso?: string;
    tem_xml_transmissao?: boolean;
    indicadores_fiscais?: Record<string, unknown>;
  };
  prontidao: NFeSaidaProntidaoPayload;
  permissoes: {
    origem_comercial_travada: boolean;
    itens_comerciais_editaveis: boolean;
    dados_complementares_editaveis: boolean;
    fiscal_editavel: boolean;
    pode_atualizar_impostos?: boolean;
    pode_validar_conferencia?: boolean;
    pode_marcar_pronta?: boolean;
    motivo_marcar_pronta_bloqueado?: string;
    ambiente_emissao_definido?: boolean;
    pode_emitir_homologacao?: boolean;
    pode_tentar_emitir_homologacao?: boolean;
    motivo_emitir_homologacao_bloqueado?: string;
    producao_habilitada?: boolean;
    usuario_pode_emitir_producao?: boolean;
    pode_emitir_producao?: boolean;
    pode_tentar_emitir_producao?: boolean;
    motivo_emitir_producao_bloqueado?: string;
    motivos_bloqueio_producao?: string[];
  };
  emissao_producao?: {
    habilitada?: boolean;
    usuario_pode_emitir?: boolean;
    pode_emitir?: boolean;
    pode_tentar_emitir?: boolean;
    motivo_bloqueio?: string;
    motivos_bloqueio?: string[];
    ambiente_label?: string;
    ambiente_emissao_nfe?: string;
    status_conferencia?: string;
    status_conferencia_display?: string;
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
  apresentacao?: import('@/lib/nfeSaidaUi').NFeSaidaApresentacao;
  emissao_sefaz?: {
    ambiente_emissao?: string;
    status_conferencia?: string;
    serie_nfe?: string;
    numero_nfe?: string;
    chave_acesso?: string;
    status_emissao_sefaz?: string;
    emissao_iniciada_pendente?: boolean;
    mensagem_emissao_pendente?: string;
    protocolo_autorizacao?: string;
    cstat_autorizacao?: string;
    motivo_autorizacao?: string;
    autorizada_em?: string | null;
    tem_xml_assinado?: boolean;
    tem_xml_autorizado?: boolean;
    tem_xml_nfe_gerado?: boolean;
    tem_xml_envio_lote?: boolean;
    tem_xml_retorno?: boolean;
    numeracao_homologacao?: {
      modelo_documento?: string;
      serie?: string;
      proximo_numero?: number;
    } | null;
    numeracao_producao?: {
      modelo_documento?: string;
      serie?: string;
      proximo_numero?: number;
    } | null;
    lote?: {
      cstat?: string;
      xmotivo?: string;
      recibo?: string;
    };
    nfe?: {
      cstat?: string;
      xmotivo?: string;
      protocolo?: string;
      dh_recbto?: string;
    };
    etapa_falha?: string;
    mensagem_erro?: string;
    pode_corrigir_serie_homologacao?: boolean;
    motivo_corrigir_serie_bloqueado?: string;
    cstat_serie_invalida?: boolean;
    autorizada_homologacao?: boolean;
    mensagem_status_homologacao?: string;
  };
  financeiro?: {
    financeiro_gerado?: boolean;
    pode_gerar_contas_receber?: boolean;
    motivo_bloqueio_financeiro?: string;
    venda_integralmente_a_vista?: boolean;
    contas_receber_vinculadas?: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
    nfe_cancelada_com_financeiro?: boolean;
  };
};

export type NFeEmissaoHomologacaoResponse = {
  ok: boolean;
  nfe_saida_id?: number;
  autorizado: boolean;
  ambiente?: string;
  status?: string;
  cStat?: string;
  xMotivo?: string;
  cstat?: string;
  xmotivo?: string;
  protocolo?: string;
  protocolo_autorizacao?: string;
  chave_acesso?: string;
  serie_nfe?: string;
  numero_nfe?: string;
  status_emissao_sefaz?: string;
  sem_efeitos_erp?: boolean;
  mensagem?: string;
  erros?: string[];
  lote?: {
    cstat?: string;
    xmotivo?: string;
    recibo?: string;
  };
  nfe?: {
    cstat?: string;
    xmotivo?: string;
    protocolo?: string;
    dh_recbto?: string;
  };
  etapa?: string;
  erros_xsd?: Array<{
    linha?: number;
    coluna?: number;
    elemento?: string;
    mensagem?: string;
    contexto?: string;
  }>;
  validacao_xsd?: {
    ok?: boolean;
    tipo?: string;
    erros?: Array<{
      linha?: number;
      coluna?: number;
      elemento?: string;
      mensagem?: string;
      contexto?: string;
    }>;
  };
  sefaz_transmitida?: boolean;
};

export type NFeConsultaSituacaoSefazResponse = {
  ok: boolean;
  mensagem?: string;
  nfe_saida_id?: number;
  ambiente?: string;
  ambiente_label?: string;
  chave_acesso?: string;
  cstat?: string;
  cStat?: string;
  xmotivo?: string;
  xMotivo?: string;
  protocolo?: string;
  protocolo_autorizacao?: string;
  consultado_em?: string;
  status_emissao_sefaz?: string;
  status_local_atualizado?: boolean;
  sem_efeitos_fiscais?: boolean;
  etapa?: string;
  situacao_sefaz?: {
    cstat?: string;
    xmotivo?: string;
    protocolo?: string;
    dh_recbto?: string;
    autorizada?: boolean;
    cancelada?: boolean;
    denegada?: boolean;
  };
};

export type NFeCartaCorrecaoAnterior = {
  evento_id: number;
  sequencia: number;
  cstat: string;
  xmotivo: string;
  protocolo: string;
  id_evento?: string;
  emitido_em: string;
  texto_correcao: string;
  texto_resumo: string;
  usuario_nome?: string;
  ambiente?: string;
  tem_comprovante?: boolean;
  vigente?: boolean;
};

export type NFeCartaCorrecaoDadosResponse = {
  ok: boolean;
  mensagem?: string;
  nfe_saida_id: number;
  ambiente: string;
  ambiente_label: string;
  homologacao: boolean;
  emitente: string;
  emitente_cnpj?: string;
  destinatario: string;
  chave_acesso: string;
  numero_nfe: string;
  serie_nfe: string;
  sequencia_prevista: number;
  total_cce_anteriores: number;
  mensagem_multiplas: string;
  mensagem_consolidar?: string;
  texto_consolidado_base?: string;
  cce_vigente?: NFeCartaCorrecaoAnterior | null;
  cce_anteriores: NFeCartaCorrecaoAnterior[];
  o_que_nao_pode_corrigir?: string;
};

export type NFeCartaCorrecaoPreviaResponse = NFeCartaCorrecaoDadosResponse & {
  texto_correcao: string;
  previa_em: string;
  somente_leitura: boolean;
  transmitido: boolean;
};

export type NFeCartaCorrecaoResponse = {
  ok: boolean;
  mensagem?: string;
  nfe_saida_id?: number;
  evento_id?: number;
  ambiente?: string;
  ambiente_label?: string;
  chave_acesso?: string;
  texto_correcao?: string;
  sequencia_evento?: number;
  cstat?: string;
  cStat?: string;
  xmotivo?: string;
  xMotivo?: string;
  protocolo?: string;
  protocolo_evento?: string;
  emitido_em?: string;
  status_emissao_sefaz?: string;
  etapa?: string;
  evento_sefaz?: {
    cstat?: string;
    xmotivo?: string;
    protocolo?: string;
    n_seq_evento?: string;
    tp_evento?: string;
    dh_reg_evento?: string;
    id_evento?: string;
  };
};

export type NFeCancelamentoDadosResponse = {
  ok: boolean;
  pode_cancelar: boolean;
  motivo_bloqueio?: string;
  ambiente: 'homologacao' | 'producao';
  ambiente_label: string;
  producao: boolean;
  exige_confirmacao_producao: boolean;
  texto_confirmacao_producao: string;
  alerta_producao?: string;
  alerta_financeiro?: string;
  financeiro_gerado?: boolean;
  nfe: {
    id: number;
    numero_nfe: string;
    serie_nfe: string;
    chave_acesso: string;
    protocolo_autorizacao: string;
    valor_total: number;
    cliente_nome: string;
    status: string;
    status_emissao_sefaz: string;
  };
  emitente: {
    nome: string;
    cnpj: string;
    uf: string;
  };
};

export type NFeCancelamentoResponse = {
  ok: boolean;
  mensagem?: string;
  nfe_saida_id?: number;
  evento_id?: number;
  ambiente?: string;
  ambiente_label?: string;
  chave_acesso?: string;
  justificativa?: string;
  cstat?: string;
  cStat?: string;
  xmotivo?: string;
  xMotivo?: string;
  protocolo?: string;
  protocolo_cancelamento?: string;
  emitido_em?: string;
  status?: string;
  status_emissao_sefaz?: string;
  etapa?: string;
  evento_sefaz?: {
    cstat?: string;
    xmotivo?: string;
    protocolo?: string;
    n_seq_evento?: string;
    tp_evento?: string;
    dh_reg_evento?: string;
    id_evento?: string;
  };
};

export type NFeInutilizacaoDadosResponse = {
  configuracao_id?: number | null;
  nfe_saida_id?: number;
  pode_inutilizar: boolean;
  motivo_bloqueio?: string;
  ambiente: string;
  ambiente_label: string;
  serie: string;
  proximo_numero?: number;
  numero_inicial_sugerido?: number | null;
  numero_final_sugerido?: number | null;
  exige_confirmacao_producao: boolean;
  alerta_producao?: string | null;
  empresa_id?: number;
  empresa_razao_social?: string;
  cnpj?: string;
  modelo_documento?: string;
  tipo_operacao?: string;
  nfe?: {
    id: number;
    numero_nfe: string;
    serie_nfe: string;
    status: string;
    status_emissao_sefaz: string;
    chave_acesso: string;
  };
  numeros_bloqueados?: Array<{ numero: number; motivo: string; nfe_saida_id?: number }>;
  nfs_na_faixa?: Array<{ nfe_saida_id: number; numero: number; status: string; status_emissao_sefaz: string }>;
};

export type NFeInutilizacaoResponse = {
  ok: boolean;
  mensagem?: string;
  configuracao_id?: number;
  inutilizacao_id?: number;
  nfs_afetadas?: number[];
  ambiente?: string;
  ambiente_label?: string;
  serie?: string;
  numero_inicial?: number;
  numero_final?: number;
  justificativa?: string;
  cstat?: string;
  cStat?: string;
  xmotivo?: string;
  xMotivo?: string;
  protocolo?: string;
  protocolo_inutilizacao?: string;
  emitido_em?: string;
  etapa?: string;
  sefaz?: Record<string, string>;
};

export type NFeEmissaoProducaoResponse = NFeEmissaoHomologacaoResponse & {
  ambiente?: 'producao';
  financeiro?: {
    tentado?: boolean;
    gerado?: boolean;
    ja_existente?: boolean;
    erro?: boolean;
    mensagem?: string;
    titulo_id?: number | null;
    titulo_numero?: string;
    financeiro_gerado?: boolean;
    pode_gerar_contas_receber?: boolean;
    motivo_bloqueio_financeiro?: string;
    venda_integralmente_a_vista?: boolean;
    contas_receber_vinculadas?: Array<{
      id: number;
      numero: string;
      status?: string;
      cancelado?: boolean;
    }>;
  };
};

export type NFeNumeracaoConfig = {
  id: number;
  empresa_id: number;
  modelo_documento: string;
  ambiente: 'homologacao' | 'producao';
  tipo_operacao?: 'saida' | 'entrada_propria';
  serie: string;
  proximo_numero: number;
  ultimo_numero_reservado?: number | null;
  ultimo_numero_autorizado?: number | null;
  ativo: boolean;
  observacoes?: string;
};

export type ValidacaoNFeSaidaResponse = {
  nfe_saida_id: number;
  numero: string;
  status: string;
  status_prontidao: 'PRONTA' | 'COM_PENDENCIAS' | 'COM_ALERTAS' | 'BLOQUEADA';
  pode_emitir: boolean;
  total_pendencias: number;
  total_alertas: number;
  grupos: Record<string, ValidacaoNFeSaidaItem[]>;
  mensagens: string[];
};

export const nfeSaidasService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<NFeSaidaListItem>>(nfSai, {
      params: buildListParams(params),
    });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<NFeSaida[] | PaginatedResponse<NFeSaida>>(nfSai, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<NFeSaida>(`${nfSai}${id}/`)).data,
  conferencia: async (id: number, params?: { modo?: string; incluir_checklist?: boolean }) =>
    (
      await api.get<NFeSaidaConferenciaPayload>(`${nfSai}${id}/conferencia/`, {
        params: {
          modo: params?.modo ?? 'abertura',
          ...(params?.incluir_checklist ? { incluir_checklist: '1' } : {}),
        },
      })
    ).data,
  salvarConferencia: async (id: number, data: Record<string, unknown>) =>
    (
      await api.post<{ conferencia: NFeSaidaConferenciaPayload; prontidao: NFeSaidaProntidaoPayload }>(
        `${nfSai}${id}/salvar-conferencia/`,
        data,
      )
    ).data,
  salvarEValidarConferencia: async (id: number, data: Record<string, unknown>) =>
    (await api.post<ValidarConferenciaResponse>(`${nfSai}${id}/salvar-e-validar-conferencia/`, data)).data,
  prontidao: async (id: number) =>
    (await api.get<NFeSaidaProntidaoPayload>(`${nfSai}${id}/prontidao/`)).data,
  validarConferencia: async (id: number) =>
    (await api.post<ValidarConferenciaResponse>(`${nfSai}${id}/validar-conferencia/`, {})).data,
  marcarPronta: async (id: number) =>
    (await api.post<ValidarConferenciaResponse>(`${nfSai}${id}/marcar-pronta/`, {})).data,
  atualizarImpostosPreview: async (id: number) =>
    (await api.get<AtualizarImpostosPreviewResponse>(`${nfSai}${id}/atualizar-impostos/preview/`)).data,
  aplicarAtualizarImpostos: async (id: number, payload?: { motivo?: string }) =>
    (
      await api.post<AtualizarImpostosAplicarResponse>(`${nfSai}${id}/atualizar-impostos/aplicar/`, {
        motivo: payload?.motivo ?? '',
      })
    ).data,
  validarEmissao: async (id: number) =>
    (await api.get<ValidacaoNFeSaidaResponse>(`${nfSai}${id}/validar-emissao/`)).data,
  previewXml: async (id: number) =>
    (await api.get<NFeSaidaPreviewXmlResponse>(`${nfSai}${id}/preview-xml/`)).data,
  previewXmlOficial: async (id: number) =>
    (await api.get<NFeSaidaPreviewXmlResponse>(`${nfSai}${id}/preview-xml-oficial/`)).data,
  previewXmlPreliminar: async (id: number) =>
    (await api.get<NFeSaidaPreviewXmlResponse>(`${nfSai}${id}/preview-xml-preliminar/`)).data,
  xmlTransmissaoHomologacao: async (id: number) =>
    (
      await api.post<{ xml: string; higienizacao: NFeSaidaConferenciaPayload['higienizacao_xml']; mensagem: string }>(
        `${nfSai}${id}/xml-transmissao-homologacao/`,
        {},
      )
    ).data,
  validarHigienizacaoXml: async (id: number, xml?: string) =>
    (
      await api.post<{ aprovado: boolean; total_pendencias: number; itens: ValidacaoNFeSaidaItem[] }>(
        `${nfSai}${id}/validar-higienizacao-xml/`,
        xml ? { xml } : {},
      )
    ).data,
  previewDanfeBlob: async (id: number) => {
    try {
      const res = await api.get<Blob>(`${nfSai}${id}/preview-danfe/`, {
        responseType: 'blob',
        params: { t: Date.now() },
        headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
      });
      const meta: DanfePreviewMeta = {
        origem: res.headers['x-danfe-origem'] as string | undefined,
        renderer: res.headers['x-danfe-renderer'] as string | undefined,
        rendererLabel: res.headers['x-danfe-renderer-label'] as string | undefined,
        rendererOficial: res.headers['x-danfe-renderer-oficial'] as string | undefined,
      };
      return { blob: res.data, meta };
    } catch (err) {
      const ax = err as import('axios').AxiosError<Blob>;
      const data = ax.response?.data;
      if (data instanceof Blob && ax.response?.status === 503) {
        try {
          const json = JSON.parse(await data.text()) as { detail?: string; mensagens?: string[] };
          const msg =
            json.detail ||
            (Array.isArray(json.mensagens) ? json.mensagens[0] : undefined) ||
            'Não foi possível gerar o DANFE pelo renderizador oficial BFR. O fallback HTML foi bloqueado para evitar layout divergente.';
          throw Object.assign(new Error(msg), { response: ax.response, isAxiosError: true });
        } catch (parseErr) {
          if (parseErr instanceof Error && !(parseErr instanceof SyntaxError)) throw parseErr;
        }
      }
      throw err;
    }
  },
  previewDados: async (id: number) =>
    (await api.get<Record<string, unknown>>(`${nfSai}${id}/preview-dados/`)).data,
  efeitosEmissao: async (id: number) =>
    (await api.get<NFeSaidaEfeitosEmissaoResponse>(`${nfSai}${id}/efeitos-emissao/`)).data,
  efeitosEmissaoNFeSaida: async (id: number) =>
    (await api.get<NFeSaidaEfeitosEmissaoResponse>(`${nfSai}${id}/efeitos-emissao/`)).data,
  eventosNFeSaida: async (id: number) =>
    (await api.get<NFeSaidaEventosResponse>(`${nfSai}${id}/eventos/`)).data,
  aplicarEfeitosAutorizacaoInterna: async (id: number, observacao?: string) =>
    (
      await api.post<NFeSaidaEfeitosAcaoResponse>(`${nfSai}${id}/aplicar-efeitos-autorizacao-interna/`, {
        observacao: observacao ?? '',
      })
    ).data,
  cancelarInternoNFeSaida: async (id: number, payload: { motivo: string }) =>
    (await api.post<NFeSaidaEfeitosAcaoResponse>(`${nfSai}${id}/cancelar-interno/`, payload)).data,
  cancelarInterno: async (id: number, motivo: string) =>
    nfeSaidasService.cancelarInternoNFeSaida(id, { motivo }),
  descartarRascunho: async (id: number, payload: { motivo: string }) =>
    (
      await api.post<{ mensagem?: string; mensagens?: string[]; status?: string }>(
        `${nfSai}${id}/descartar-rascunho/`,
        payload,
      )
    ).data,
  create: async (data: Omit<NFeSaida, 'id'>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    return (
      await api.post<NFeSaida>(nfSai, {
        ...rest,
        itens: stripNfItens(itens),
      })
    ).data;
  },
  update: async (id: number, data: Partial<NFeSaida>) => {
    const { cliente_nome: _cn, valor_total: _vt, itens, ...rest } = data;
    const payload: Record<string, unknown> = { ...rest };
    if (itens) payload.itens = stripNfItens(itens, { keepId: true });
    return (await api.patch<NFeSaida>(`${nfSai}${id}/`, payload)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${nfSai}${id}/`);
  },
  reservarNumeracao: async (id: number) =>
    (await api.post<Record<string, unknown>>(`${nfSai}${id}/reservar-numeracao/`, {})).data,
  corrigirSerieHomologacao: async (id: number) =>
    (
      await api.post<{
        ok?: boolean;
        mensagem?: string;
        serie_anterior?: string;
        serie_nova?: string;
        chave_anterior?: string;
        chave_nova?: string;
        numero_nfe?: string;
      }>(`${nfSai}${id}/corrigir-serie-homologacao/`, {}, { validateStatus: (s) => s >= 200 && s < 500 })
    ).data,
  checklistHomologacao: async (id: number) =>
    (await api.post<NFeChecklistHomologacaoResponse>(`${nfSai}${id}/checklist-homologacao/`, {})).data,
  checklistHomologacaoGeral: async (payload: {
    pedido_venda_id?: number;
    faturamento_id?: number;
    nfe_saida_id?: number;
  }) =>
    (await api.post<NFeChecklistHomologacaoResponse>(`${nfSai}checklist-homologacao/`, payload)).data,
  emitirHomologacao: async (id: number) => {
    const res = await api.post<NFeEmissaoHomologacaoResponse>(
      `${nfSai}${id}/emitir-homologacao/`,
      {},
      {
        timeout: 120_000,
        validateStatus: (s) => s >= 200 && s < 500,
      },
    );
    return res.data;
  },
  validarEmissaoProducao: async (id: number) =>
    (
      await api.get<{
        pronta: boolean;
        pendencias: Array<{ codigo?: string; mensagem?: string }>;
        alertas: Array<{ codigo?: string; mensagem?: string }>;
        producao_habilitada?: boolean;
      }>(`${nfSai}${id}/validar-emissao-producao/`)
    ).data,
  emitirProducao: async (
    id: number,
    payload: { confirmar_emissao_producao: boolean; confirmar_ambiente: string },
  ) => {
    const res = await api.post<NFeEmissaoProducaoResponse>(
      `${nfSai}${id}/emitir-producao/`,
      payload,
      {
        timeout: 120_000,
        validateStatus: (s) => s >= 200 && s < 500,
      },
    );
    return res.data;
  },
  consultarSituacaoSefaz: async (id: number) => {
    const res = await api.post<NFeConsultaSituacaoSefazResponse>(
      `${nfSai}${id}/consultar-situacao-sefaz/`,
      {},
      {
        timeout: 60_000,
        validateStatus: (s) => s >= 200 && s < 500,
      },
    );
    return res.data;
  },
  emitirCartaCorrecao: async (id: number, payload: { texto_correcao: string }) => {
    const res = await api.post<NFeCartaCorrecaoResponse>(
      `${nfSai}${id}/emitir-carta-correcao/`,
      payload,
      {
        timeout: 120_000,
        validateStatus: (s) => s >= 200 && s < 500,
      },
    );
    return res.data;
  },
  cartaCorrecaoDados: async (id: number) =>
    (await api.get<NFeCartaCorrecaoDadosResponse>(`${nfSai}${id}/carta-correcao/dados/`)).data,
  previaCartaCorrecao: async (id: number, payload: { texto_correcao: string }) => {
    const res = await api.post<NFeCartaCorrecaoPreviaResponse>(`${nfSai}${id}/previa-carta-correcao/`, payload, {
      validateStatus: (s) => s >= 200 && s < 500,
    });
    if (res.status === 401) {
      clearAuthSession();
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.assign('/login');
      }
      throw new axios.AxiosError(SESSION_EXPIRED_MESSAGE, 'ERR_BAD_REQUEST', res.config, res.request, res);
    }
    return res.data;
  },
  previaCartaCorrecaoPdfBlob: async (id: number, payload: { texto_correcao: string }) => {
    const res = await api.post<Blob>(`${nfSai}${id}/previa-carta-correcao/pdf/`, payload, {
      responseType: 'blob',
      headers: { Accept: 'application/pdf, application/json' },
      validateStatus: (s) => s >= 200 && s < 500,
    });
    return res.data;
  },
  comprovanteCartaCorrecaoPdfBlob: async (nfeId: number, eventoId: number) => {
    const res = await api.get<Blob>(`${nfSai}${nfeId}/comprovante-carta-correcao/${eventoId}/`, {
      responseType: 'blob',
      headers: { Accept: 'application/pdf, application/json' },
      params: { t: Date.now() },
    });
    return res.data;
  },
  downloadXmlAssinadoUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-assinado/`,
  downloadXmlNfeUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-nfe/`,
  downloadXmlLoteEnviadoUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-lote-enviado/`,
  downloadXmlRetornoSefazUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-retorno-sefaz/`,
  downloadXmlAutorizadoUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-autorizado/`,
  downloadXmlAutorizadoBlob: async (id: number) => {
    const res = await api.get<Blob>(`${nfSai}${id}/xml-autorizado/`, {
      responseType: 'blob',
      headers: { Accept: 'application/xml, text/xml, application/json' },
      validateStatus: (s) => s >= 200 && s < 500,
    });
    return resolveBlobDownload(res, `NFe_${id}_procNFe.xml`, 'XML autorizado indisponível.');
  },
  downloadXmlAutorizado: async (id: number) => {
    const { blob, filename } = await nfeSaidasService.downloadXmlAutorizadoBlob(id);
    downloadBlobFile(blob, filename);
  },
  validarXmlSchema: async (id: number) =>
    (
      await api.post<{ ok: boolean; tipo?: string; erros?: Array<Record<string, unknown>> }>(
        `${nfSai}${id}/validar-xml-schema/`,
        {},
        { validateStatus: (s) => s >= 200 && s < 500 },
      )
    ).data,
  danfeHomologacaoBlob: async (id: number) => {
    const res = await api.get<Blob>(`${nfSai}${id}/danfe-homologacao/`, { responseType: 'blob' });
    return res.data;
  },
  danfeAutorizadoBlob: async (id: number, opts?: { download?: boolean }) => {
    try {
      const params: Record<string, string | number> = { t: Date.now() };
      if (opts?.download) {
        params.download = 1;
      }
      const res = await api.get<Blob>(`${nfSai}${id}/danfe-autorizado/`, {
        responseType: 'blob',
        params,
        headers: {
          Accept: 'application/pdf, application/json',
          'Cache-Control': 'no-cache',
          Pragma: 'no-cache',
        },
        validateStatus: (s) => s >= 200 && s < 500,
      });
      return resolveBlobDownload(
        res,
        `DANFE_NFe_${id}.pdf`,
        'Não foi possível gerar o DANFE autorizado.',
      );
    } catch (err) {
      const ax = err as import('axios').AxiosError<Blob>;
      const data = ax.response?.data;
      if (data instanceof Blob && ax.response?.status === 503) {
        const msg = await readBlobErrorMessage(
          data,
          'Não foi possível gerar o DANFE autorizado.',
        );
        throw Object.assign(new Error(msg), { response: ax.response, isAxiosError: true });
      }
      throw err;
    }
  },
  visualizarDanfeAutorizado: async (id: number) => {
    await visualizarPdfEmNovaAba(async () => {
      const { blob } = await nfeSaidasService.danfeAutorizadoBlob(id);
      return blob;
    });
  },
  visualizarDanfePreview: async (id: number) => {
    await visualizarPdfEmNovaAba(async () => {
      const { blob } = await nfeSaidasService.previewDanfeBlob(id);
      return blob;
    });
  },
  baixarDanfeAutorizado: async (id: number) => {
    const { blob, filename } = await nfeSaidasService.danfeAutorizadoBlob(id, { download: true });
    downloadBlobFile(blob, filename);
  },
  baixarDanfePreview: async (id: number) => {
    const res = await api.get<Blob>(`${nfSai}${id}/preview-danfe/`, {
      responseType: 'blob',
      params: { t: Date.now() },
      headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
      validateStatus: (s) => s >= 200 && s < 500,
    });
    const { blob, filename } = await resolveBlobDownload(
      res,
      `danfe-nfe-${id}.pdf`,
      'Não foi possível gerar o DANFE de conferência.',
    );
    downloadBlobFile(blob, filename);
  },
  previewContasReceber: async (id: number) =>
    (await api.get<NFeGerarContasReceberPreview>(`${nfSai}${id}/financeiro/preview-contas-receber/`)).data,
  gerarContasReceber: async (
    id: number,
    payload: NFeGerarContasReceberPayload,
  ) =>
    (
      await api.post<NFeGerarContasReceberResponse>(
        `${nfSai}${id}/financeiro/gerar-contas-receber/`,
        payload,
      )
    ).data,
  contasReceberVinculadas: async (id: number) =>
    (await api.get<NFeContasReceberVinculadasResponse>(`${nfSai}${id}/financeiro/contas-receber/`)).data,
  cancelamentoDados: async (id: number) =>
    (await api.get<NFeCancelamentoDadosResponse>(`${nfSai}${id}/cancelamento/dados/`)).data,
  cancelarNfe: async (
    id: number,
    payload: {
      justificativa: string;
      confirmar_cancelamento_producao?: boolean;
      confirmar_texto?: string;
    },
  ) => {
    const res = await api.post<NFeCancelamentoResponse>(`${nfSai}${id}/cancelar/`, payload, {
      timeout: 120_000,
      validateStatus: (s) => s >= 200 && s < 500,
    });
    return res.data;
  },
  inutilizacaoDados: async (id: number) =>
    (await api.get<NFeInutilizacaoDadosResponse>(`${nfSai}${id}/inutilizacao/dados/`)).data,
  inutilizarNfe: async (
    id: number,
    payload: {
      justificativa: string;
      numero_inicial?: number;
      numero_final?: number;
      confirmar_inutilizacao_producao?: boolean;
      confirmar_texto?: string;
    },
  ) => {
    const res = await api.post<NFeInutilizacaoResponse>(`${nfSai}${id}/inutilizar/`, payload, {
      timeout: 120_000,
      validateStatus: (s) => s >= 200 && s < 500,
    });
    return res.data;
  },
  envioEmailDados: async (id: number) => {
    const { data } = await api.get<unknown>(`${nfSai}${id}/envio-email/dados/`);
    return data as NFeEnvioEmailDadosResponse;
  },
  envioEmailEnviar: async (
    id: number,
    payload: {
      destinatarios?: string[];
      para?: string;
      cc?: string;
      assunto: string;
      mensagem: string;
      confirmar_envio: boolean;
    },
  ) => {
    const res = await api.post<NFeEnvioEmailEnviarResponse>(`${nfSai}${id}/envio-email/enviar/`, payload, {
      timeout: 120_000,
      // 502 = falha SMTP total estruturada (não confundir com validação 400).
      validateStatus: (s) => (s >= 200 && s < 500) || s === 502,
    });
    return res.data;
  },
};

export type NFeEnvioEmailHistorico = {
  id: number;
  enviado_em: string;
  usuario_nome: string;
  destinatario: string;
  copias?: string;
  assunto?: string;
  status_envio: 'SUCESSO' | 'ERRO';
  mensagem_erro?: string;
  ambiente?: string;
  anexo_xml?: boolean;
  anexo_danfe_pdf?: boolean;
};

export type NFeEnvioDestinatarioSugerido = {
  email: string;
  nome: string;
  origem: 'contato' | 'email_nf' | 'email' | string;
  contato_id: number | null;
  selecionado: boolean;
};

export type NFeEnvioEmailResultadoItem = {
  email: string;
  status?: 'SUCESSO' | 'ERRO';
  mensagem?: string;
  /** Alias legado */
  status_envio?: 'SUCESSO' | 'ERRO';
  mensagem_erro?: string;
  envio_id?: number;
};

export type NFeEnvioEmailDadosResponse = {
  ok: boolean;
  pode_enviar: boolean;
  motivo_bloqueio?: string;
  ambiente: string;
  ambiente_label: string;
  homologacao: boolean;
  alerta_homologacao?: string;
  destinatario_sugerido: string;
  destinatarios_sugeridos?: NFeEnvioDestinatarioSugerido[];
  cliente_sem_email?: boolean;
  destinatario_origem?: 'email_nf' | 'email' | 'contato' | '';
  aviso_sem_email_cliente?: string;
  assunto_sugerido: string;
  mensagem_sugerida: string;
  anexos: {
    xml_autorizado: boolean;
    danfe_pdf: boolean;
  };
  nfe: {
    id: number;
    numero: string;
    serie: string;
    chave_acesso: string;
    status: string;
    status_emissao_sefaz: string;
    cliente_nome: string;
    protocolo_autorizacao: string;
  };
  ultimo_envio: NFeEnvioEmailHistorico | null;
  historico_recente?: NFeEnvioEmailHistorico[];
};

export type NFeEnvioEmailEnviarResponse = {
  ok: boolean;
  status_geral?: 'SUCESSO' | 'PARCIAL' | 'ERRO';
  mensagem?: string;
  total?: number;
  sucessos?: number;
  falhas?: number;
  sucesso?: number;
  erro?: number;
  resultados?: NFeEnvioEmailResultadoItem[];
  envio?: NFeEnvioEmailHistorico | null;
  envios?: NFeEnvioEmailHistorico[];
};

export type NFeGerarContasReceberParcela = {
  numero_parcela: number;
  vencimento: string;
  valor: string;
  observacoes?: string;
};

export type NFeGerarContasReceberPreview = {
  financeiro_gerado: boolean;
  pode_gerar_contas_receber: boolean;
  motivo_bloqueio_financeiro: string;
  venda_integralmente_a_vista?: boolean;
  contas_receber_vinculadas: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
  nfe_cancelada_com_financeiro?: boolean;
  cliente: { id: number; nome: string };
  origem: {
    tipo: string;
    id: number;
    numero: string;
    serie: string;
    chave_acesso: string;
    data_emissao: string | null;
    data_autorizacao: string | null;
    descricao: string;
    valor_total: string;
    pedido_venda_numero: string;
    faturamento_numero: string;
  };
  parcelas: NFeGerarContasReceberParcela[];
  quantidade_parcelas_sugeridas: number;
  categoria_sugerida_id: number | null;
};

export type NFeGerarContasReceberPayload = {
  parcelas: NFeGerarContasReceberParcela[];
  categoria?: number | null;
  centro_custo?: number | null;
  forma_pagamento_prevista_codigo?: string;
  conta_financeira_prevista?: number | null;
  observacoes?: string;
};

export type NFeGerarContasReceberResponse = {
  mensagem: string;
  titulo: import('@/services/api/financeiro').TituloFinanceiro;
  financeiro_gerado: boolean;
  pode_gerar_contas_receber: boolean;
  motivo_bloqueio_financeiro: string;
  venda_integralmente_a_vista?: boolean;
  contas_receber_vinculadas: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
};

export type NFeContasReceberVinculadasResponse = {
  financeiro_gerado: boolean;
  pode_gerar_contas_receber: boolean;
  motivo_bloqueio_financeiro: string;
  venda_integralmente_a_vista?: boolean;
  contas_receber_vinculadas: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
  contas_receber: import('@/services/api/financeiro').TituloFinanceiro[];
};

export const nfeNumeracoesService = {
  listByEmpresa: async (empresaId: number) =>
    (await api.get<NFeNumeracaoConfig[]>('nfe-numeracoes/', { params: { empresa_id: empresaId } })).data,
  update: async (id: number, data: Partial<NFeNumeracaoConfig> & { confirmar_alteracao_producao?: boolean }) =>
    (await api.patch<NFeNumeracaoConfig>(`nfe-numeracoes/${id}/`, data)).data,
  create: async (data: Omit<NFeNumeracaoConfig, 'id'>) =>
    (await api.post<NFeNumeracaoConfig>('nfe-numeracoes/', data)).data,
  inutilizacaoDados: async (id: number, params?: { numero_inicial?: number; numero_final?: number }) =>
    (await api.get<NFeInutilizacaoDadosResponse>(`nfe-numeracoes/${id}/inutilizacao/dados/`, { params })).data,
  inutilizar: async (
    id: number,
    payload: {
      numero_inicial: number;
      numero_final: number;
      justificativa: string;
      confirmar_inutilizacao_producao?: boolean;
      confirmar_texto?: string;
      ano?: number;
    },
  ) => {
    const res = await api.post<NFeInutilizacaoResponse>(`nfe-numeracoes/${id}/inutilizar/`, payload, {
      timeout: 120_000,
      validateStatus: (s) => s >= 200 && s < 500,
    });
    return res.data;
  },
};

export const cteEntradasService = {
  listPaginated: async (params?: ListQueryParams) => {
    const response = await api.get<PaginatedResponse<CTeEntrada>>(cte, { params: buildListParams(params) });
    return response.data;
  },
  getAll: async (params?: ListQueryParams) => {
    const response = await api.get<CTeEntrada[] | PaginatedResponse<CTeEntrada>>(cte, {
      params: buildListParams(params?.page ? params : { ...params, limit: params?.limit ?? 100 }),
    });
    return unwrapListResults(response.data);
  },
  getById: async (id: number) => (await api.get<CTeEntrada>(`${cte}${id}/`)).data,
  create: async (data: Omit<CTeEntrada, 'id'>) => {
    const { transportadora_nome: _tn, tomador_nome: _tm, ...rest } = data;
    return (await api.post<CTeEntrada>(cte, rest)).data;
  },
  update: async (id: number, data: Partial<CTeEntrada>) => {
    const { transportadora_nome: _tn, tomador_nome: _tm, ...rest } = data;
    return (await api.patch<CTeEntrada>(`${cte}${id}/`, rest)).data;
  },
  delete: async (id: number) => {
    await api.delete(`${cte}${id}/`);
  },
};
