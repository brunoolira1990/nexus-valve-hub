import api from './config';
import type { CTeEntrada, ItemNFe, NFeEntrada, NFeSaida } from '@/types';

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
  getAll: async () => (await api.get<NFeEntrada[]>(nfEnt)).data,
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
  checklist: ValidacaoNFeSaidaResponse;
  prontidao: NFeSaidaProntidaoPayload;
  permissoes: {
    origem_comercial_travada: boolean;
    itens_comerciais_editaveis: boolean;
    dados_complementares_editaveis: boolean;
    fiscal_editavel: boolean;
    pode_atualizar_impostos?: boolean;
    pode_validar_conferencia?: boolean;
    pode_marcar_pronta?: boolean;
  };
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
  getAll: async () => (await api.get<NFeSaida[]>(nfSai)).data,
  getById: async (id: number) => (await api.get<NFeSaida>(`${nfSai}${id}/`)).data,
  conferencia: async (id: number) =>
    (await api.get<NFeSaidaConferenciaPayload>(`${nfSai}${id}/conferencia/`)).data,
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
  previewDanfeBlob: async (id: number) =>
    (
      await api.get<Blob>(`${nfSai}${id}/preview-danfe/`, {
        responseType: 'blob',
        params: { t: Date.now() },
        headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
      })
    ).data,
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
};

export const cteEntradasService = {
  getAll: async () => (await api.get<CTeEntrada[]>(cte)).data,
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
