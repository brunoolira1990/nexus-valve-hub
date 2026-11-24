import api from './config';
import type {
  AjusteFiscalPayload,
  CandidatosPedidoConferencia,
  EstadoChegadaNFeEntrada,
  HistoricoAjustesFiscaisItem,
  IniciarConferenciaNFeEntradaPayload,
  NFeEntradaConferencia,
  PreviewFiscalItem,
  PreviewReaberturaEntradaFornecedor,
  ResultadoAjusteFiscal,
  ResultadoAplicacaoEstoque,
  ResultadoReaberturaEntradaFornecedor,
} from '@/types';

const base = 'nf-entradas-historicas-importadas/';
const fiscalBase = 'conferencia/items/';

export const nfeEntradaConferenciaService = {
  get: async (nfeHistoricaId: number) => {
    const { conferencia } = (await api.get<EstadoChegadaNFeEntrada>(`${base}${nfeHistoricaId}/conferencia/`)).data;
    if (!conferencia) throw new Error('Conferência ainda não iniciada.');
    return conferencia;
  },
  getEstado: async (nfeHistoricaId: number) =>
    (await api.get<EstadoChegadaNFeEntrada>(`${base}${nfeHistoricaId}/conferencia/`)).data,
  iniciar: async (nfeHistoricaId: number, payload: IniciarConferenciaNFeEntradaPayload = {}) =>
    (await api.post<EstadoChegadaNFeEntrada>(`${base}${nfeHistoricaId}/conferencia/iniciar/`, payload)).data,
  candidatosPedido: async (nfeHistoricaId: number) =>
    (await api.get<CandidatosPedidoConferencia>(`${base}${nfeHistoricaId}/conferencia/candidatos-pedido/`)).data,
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
  desvincularAlocacoesVenda: async (nfeHistoricaId: number, motivo?: string) =>
    (
      await api.post<{
        detail: string;
        alocacoes_removidas: number;
        preview: PreviewReaberturaEntradaFornecedor;
      }>(`${base}${nfeHistoricaId}/conferencia/desvincular-alocacoes-venda/`, {
        motivo: motivo || undefined,
      })
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
      await api.post<{ conferencia: NFeEntradaConferencia | null }>(
        `${base}${nfeHistoricaId}/fornecedor/vincular/`,
        { fornecedor_id: fornecedorId },
      )
    ).data,
  cadastrarVincularFornecedor: async (nfeHistoricaId: number, payload: Record<string, unknown>) =>
    (
      await api.post<{ conferencia: NFeEntradaConferencia | null }>(
        `${base}${nfeHistoricaId}/fornecedor/cadastrar-vincular/`,
        payload,
      )
    ).data,
  gerarSaidaDevolucaoCompra: async (
    nfeHistoricaId: number,
    payload: {
      itens?: Array<{ item_conferencia_id: number; quantidade: string }>;
      motivo: 'NAO_CONFORME' | 'DEFEITO' | 'ERRO_PEDIDO' | 'AVARIA_TRANSPORTE' | 'OUTRO';
      observacao?: string;
    },
  ) =>
    (
      await api.post<{
        ok: boolean;
        nf_saida_id: number;
        numero: string;
        valor_total: string;
        itens_criados: number;
        cfop: string;
        mensagem: string;
      }>(`${base}${nfeHistoricaId}/conferencia/gerar-saida-devolucao-compra/`, payload)
    ).data,
  previewFiscal: async (itemConferenciaId: number) =>
    (await api.get<PreviewFiscalItem>(`${fiscalBase}${itemConferenciaId}/fiscal-preview/`)).data,
  ajustarFiscal: async (itemConferenciaId: number, payload: AjusteFiscalPayload) =>
    (await api.patch<ResultadoAjusteFiscal>(`${fiscalBase}${itemConferenciaId}/fiscal-adjust/`, payload)).data,
  historicoFiscal: async (itemConferenciaId: number) =>
    (await api.get<HistoricoAjustesFiscaisItem>(`${fiscalBase}${itemConferenciaId}/fiscal-history/`)).data,
};
