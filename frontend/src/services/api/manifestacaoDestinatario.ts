import api from './config';
import { buildListParams, type ListQueryParams, type PaginatedResponse } from '@/lib/apiList';

const base = 'fiscal/manifestacao-destinatario/';

export type StatusManifestacao =
  | 'PENDENTE'
  | 'CIENTE'
  | 'CONFIRMADA'
  | 'DESCONHECIDA'
  | 'NAO_REALIZADA'
  | 'ERRO';

export type StatusXmlDestinada = 'RESUMO' | 'DISPONIVEL' | 'BAIXADO' | 'PENDENTE' | 'ERRO';

export type EventoManifestacaoDestinatario =
  | 'CIENCIA_EMISSAO'
  | 'CONFIRMACAO_OPERACAO'
  | 'DESCONHECIMENTO'
  | 'OPERACAO_NAO_REALIZADA';

export type NFeDestinadaDocumento = {
  id: number;
  empresa_id: number;
  empresa_nome: string;
  chave_acesso: string;
  chave_resumida: string;
  nsu: string;
  cnpj_emitente: string;
  razao_social_emitente: string;
  dh_emissao: string | null;
  valor_nf: string;
  status_manifestacao: StatusManifestacao;
  status_manifestacao_label: string;
  status_xml: StatusXmlDestinada;
  status_xml_label: string;
  ambiente: string;
  ambiente_label: string;
  classificacao_dfe: string;
  ultimo_cstat: string;
  ultimo_xmotivo: string;
  nf_entrada_historica_id: number | null;
  manifestado_em: string | null;
  xml_baixado_em: string | null;
  consultado_em: string;
};

export type NFeDestinadaEvento = {
  id: number;
  tipo_acao: string;
  codigo_evento: string;
  descricao: string;
  usuario_nome: string;
  ambiente: string;
  resultado_resumido: string;
  cstat: string;
  xmotivo: string;
  criado_em: string;
  dados_json?: Record<string, unknown> | null;
};

export type NFeDestinadaDetalhe = NFeDestinadaDocumento & {
  ie_emitente: string;
  resumo_json: Record<string, unknown>;
  criado_em: string;
  eventos: NFeDestinadaEvento[];
};

export type FechamentoManifestacaoPreview = {
  empresa_id: number | null;
  data_inicio: string;
  data_fim: string;
  total_documentos: number;
  xml_baixados: number;
  xml_pendentes: number;
  sem_manifestacao: number;
  erros: number;
  nfe_xml_armazenados?: number;
  cte_xml_armazenados?: number;
  nfe_xml_pendentes_manifestacao?: number;
  cte_xml_pendentes?: number;
  erros_armazenamento?: number;
};

export type ConsultaManifestacaoResponse = {
  sucesso: boolean;
  novos: number;
  resumos_processados: number;
  xml_disponivel: number;
  mensagens?: string[];
  erros?: string[];
};

export type IniciarPorChaveResponse = {
  criado: boolean;
  documento: NFeDestinadaDetalhe;
};

export type ManifestarDestinatarioResponse = {
  documento_id: number;
  evento: EventoManifestacaoDestinatario;
  status_manifestacao: StatusManifestacao;
  status_manifestacao_label?: string;
  cstat: string;
  cstat_lote?: string;
  cstat_evento?: string;
  xmotivo: string;
  protocolo: string;
  evento_id: number | null;
  duplicidade?: boolean;
  documento: NFeDestinadaDetalhe;
};

export const manifestacaoDestinatarioService = {
  async listPaginated(params?: ListQueryParams): Promise<PaginatedResponse<NFeDestinadaDocumento>> {
    const { data } = await api.get<PaginatedResponse<NFeDestinadaDocumento>>(base, {
      params: buildListParams(params),
    });
    return data;
  },

  async get(id: number): Promise<NFeDestinadaDetalhe> {
    const { data } = await api.get<NFeDestinadaDetalhe>(`${base}${id}/`);
    return data;
  },

  async consultarResumosDestinados(payload: {
    empresa_id: number;
    limite_lotes?: number;
  }): Promise<ConsultaManifestacaoResponse> {
    /** Apenas consulta dist NSU / resumos destinados. Não envia evento fiscal de manifestação. */
    const { data } = await api.post<ConsultaManifestacaoResponse>(`${base}consultar/`, payload);
    return data;
  },

  /** @deprecated Use consultarResumosDestinados — nome antigo; não confundir com manifestar. */
  async consultar(payload: { empresa_id: number; limite_lotes?: number }): Promise<ConsultaManifestacaoResponse> {
    return manifestacaoDestinatarioService.consultarResumosDestinados(payload);
  },

  /** Prepara registro por chave — somente ação manual; não envia evento fiscal nem baixa XML. */
  async iniciarPorChave(payload: {
    empresa_id: number;
    chave_acesso: string;
    nf_entrada_historica_id?: number;
  }): Promise<IniciarPorChaveResponse> {
    const { data } = await api.post<IniciarPorChaveResponse>(`${base}iniciar-por-chave/`, payload);
    return data;
  },

  /** Envia evento fiscal SEFAZ — somente ação manual explícita do usuário. */
  async manifestar(
    id: number,
    payload: {
      evento: EventoManifestacaoDestinatario;
      justificativa?: string;
      confirmacao_explicita: boolean;
    },
  ): Promise<ManifestarDestinatarioResponse> {
    const { data } = await api.post<ManifestarDestinatarioResponse>(`${base}${id}/manifestar/`, payload);
    return data;
  },

  /** Download XML completo — somente ação manual explícita do usuário. */
  async baixarXml(id: number, confirmacao_explicita: boolean) {
    const { data } = await api.post(`${base}${id}/baixar-xml/`, { confirmacao_explicita });
    return data;
  },

  async fechamentoPreview(params: {
    empresa_id?: number;
    data_inicio: string;
    data_fim: string;
  }): Promise<FechamentoManifestacaoPreview> {
    const { data } = await api.get<FechamentoManifestacaoPreview>(`${base}fechamento-preview/`, { params });
    return data;
  },
};

export const LABEL_EVENTO_MANIFESTACAO: Record<EventoManifestacaoDestinatario, string> = {
  CIENCIA_EMISSAO: 'Ciência da Emissão',
  CONFIRMACAO_OPERACAO: 'Confirmação da Operação',
  DESCONHECIMENTO: 'Desconhecimento da Operação',
  OPERACAO_NAO_REALIZADA: 'Operação não Realizada',
};

export const DESCRICAO_EVENTO_MANIFESTACAO: Record<EventoManifestacaoDestinatario, string> = {
  CIENCIA_EMISSAO:
    'Registra conhecimento da NF-e. Não confirma recebimento da mercadoria.',
  CONFIRMACAO_OPERACAO:
    'Confirma participação na operação e recebimento conforme NF-e.',
  DESCONHECIMENTO: 'Informa desconhecimento da operação descrita na NF-e.',
  OPERACAO_NAO_REALIZADA:
    'Informa que a operação não foi realizada. Exige justificativa.',
};
