import api from './config';
import type {
  NFeEntradaConferencia,
  PreviewReaberturaEntradaFornecedor,
  ResultadoAplicacaoEstoque,
  ResultadoReaberturaEntradaFornecedor,
} from '@/types';

const base = 'nf-entradas-historicas-importadas/';

export const nfeEntradaConferenciaService = {
  get: async (nfeHistoricaId: number) =>
    (await api.get<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/conferencia/`)).data,
  salvar: async (nfeHistoricaId: number, payload: Partial<NFeEntradaConferencia>) =>
    (await api.post<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/conferencia/`, payload)).data,
  prepararEstoque: async (nfeHistoricaId: number, payload?: { data_entrada?: string | null }) =>
    (await api.post<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/preparar-estoque/`, payload ?? {})).data,
  previewReabertura: async (nfeHistoricaId: number) =>
    (
      await api.get<PreviewReaberturaEntradaFornecedor>(
        `${base}${nfeHistoricaId}/conferencia/reabrir/`,
      )
    ).data,
  reabrir: async (nfeHistoricaId: number, motivo: string) =>
    (
      await api.post<ResultadoReaberturaEntradaFornecedor>(
        `${base}${nfeHistoricaId}/conferencia/reabrir/`,
        { motivo },
      )
    ).data,
  previewAplicarEstoque: async (nfeHistoricaId: number, confirmarAlertas = false) =>
    (
      await api.get<ResultadoAplicacaoEstoque>(
        `${base}${nfeHistoricaId}/conferencia/aplicar-estoque/`,
        { params: { confirmar_alertas: confirmarAlertas } },
      )
    ).data,
  aplicarEstoque: async (
    nfeHistoricaId: number,
    payload: { confirmar_alertas?: boolean; observacao?: string; data_entrada?: string },
  ) =>
    (
      await api.post<ResultadoAplicacaoEstoque>(
        `${base}${nfeHistoricaId}/conferencia/aplicar-estoque/`,
        payload,
      )
    ).data,
  confirmarEquivalencia: async (
    nfeHistoricaId: number,
    payload: {
      produto_interno_id: number;
      item_pedido_compra_id?: number | null;
      itens_nfe_conferencia_ids: number[];
      tipo_agrupamento?: string;
      quantidade_equivalente?: string;
      confianca?: number;
      motivo_confirmacao?: string;
      salvar_regra_fornecedor?: boolean;
    },
  ) =>
    (
      await api.post<{ conferencia: NFeEntradaConferencia; mensagem: string }>(
        `${base}${nfeHistoricaId}/conferencia/confirmar-equivalencia/`,
        payload,
      )
    ).data,
  rejeitarEquivalencia: async (
    nfeHistoricaId: number,
    payload: { produto_interno_id: number; itens_nfe_conferencia_ids: number[]; motivo?: string },
  ) =>
    (
      await api.post<{ conferencia: NFeEntradaConferencia }>(
        `${base}${nfeHistoricaId}/conferencia/rejeitar-equivalencia/`,
        payload,
      )
    ).data,
  vincularFornecedor: async (nfeHistoricaId: number, fornecedorId: number) =>
    (
      await api.post<{ conferencia: NFeEntradaConferencia }>(
        `${base}${nfeHistoricaId}/fornecedor/vincular/`,
        { fornecedor_id: fornecedorId },
      )
    ).data,
  cadastrarVincularFornecedor: async (nfeHistoricaId: number, payload: Record<string, unknown>) =>
    (
      await api.post<{ conferencia: NFeEntradaConferencia }>(
        `${base}${nfeHistoricaId}/fornecedor/cadastrar-vincular/`,
        payload,
      )
    ).data,
};
