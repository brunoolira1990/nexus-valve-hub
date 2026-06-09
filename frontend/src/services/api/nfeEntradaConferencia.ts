import api from './config';
import type { NFeEntradaConferencia, ResultadoAplicacaoEstoque } from '@/types';

const base = 'nf-entradas-historicas-importadas/';

export const nfeEntradaConferenciaService = {
  get: async (nfeHistoricaId: number) =>
    (await api.get<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/conferencia/`)).data,
  salvar: async (nfeHistoricaId: number, payload: Partial<NFeEntradaConferencia>) =>
    (await api.post<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/conferencia/`, payload)).data,
  prepararEstoque: async (nfeHistoricaId: number) =>
    (await api.post<NFeEntradaConferencia>(`${base}${nfeHistoricaId}/preparar-estoque/`, {})).data,
  previewAplicarEstoque: async (nfeHistoricaId: number, confirmarAlertas = false) =>
    (
      await api.get<ResultadoAplicacaoEstoque>(
        `${base}${nfeHistoricaId}/conferencia/aplicar-estoque/`,
        { params: { confirmar_alertas: confirmarAlertas } },
      )
    ).data,
  aplicarEstoque: async (
    nfeHistoricaId: number,
    payload: { confirmar_alertas?: boolean; observacao?: string },
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
};
