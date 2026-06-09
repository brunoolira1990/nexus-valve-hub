import api from './config';
import {
  buildListParams,
  type ListQueryParams,
  type PaginatedResponse,
  unwrapListResults,
} from '@/lib/apiList';
import type { CTeEntrada, ItemNFe, NFeEntrada, NFeSaida, NFeSaidaListItem } from '@/types';
import type { DiagnosticoFiscalPreview, EnderecoFiscalResumo } from '@/lib/enderecoFiscal';

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
    pode_emitir_homologacao?: boolean;
    pode_tentar_emitir_homologacao?: boolean;
    motivo_emitir_homologacao_bloqueado?: string;
  };
  apresentacao?: import('@/lib/nfeSaidaUi').NFeSaidaApresentacao;
  emissao_sefaz?: {
    ambiente_emissao?: string;
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
};

export type NFeNumeracaoConfig = {
  id: number;
  empresa_id: number;
  modelo_documento: string;
  ambiente: 'homologacao' | 'producao';
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
  downloadXmlAssinadoUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-assinado/`,
  downloadXmlNfeUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-nfe/`,
  downloadXmlLoteEnviadoUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-lote-enviado/`,
  downloadXmlRetornoSefazUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-retorno-sefaz/`,
  downloadXmlAutorizadoUrl: (id: number) => `${api.defaults.baseURL}${nfSai}${id}/xml-autorizado/`,
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
  contas_receber_vinculadas: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
};

export type NFeContasReceberVinculadasResponse = {
  financeiro_gerado: boolean;
  pode_gerar_contas_receber: boolean;
  motivo_bloqueio_financeiro: string;
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
