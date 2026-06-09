import api from './config';
import { buildListParams, type ListQueryParams, type PaginatedResponse } from '@/lib/apiList';
import type {
  AlocacaoAtendimento,
  AlocacaoAtendimentoPayload,
  AlocacoesAtendimentoListResponse,
} from '@/types/alocacaoAtendimento';
import type {
  OpcaoCteConferido,
  OpcaoFornecedor,
  OpcaoNfeEntradaImportada,
  OpcaoNfeEntradaImportadaItem,
  OpcaoPedidoCompra,
  OpcaoPedidoCompraItem,
} from '@/types/alocacaoAtendimentoOpcoes';

const base = 'alocacoes-atendimento/';

type OpcoesParams = Record<string, string | number | boolean | undefined>;

function opcoesParams(extra?: OpcoesParams) {
  const out: Record<string, string | number> = { limit: 20 };
  if (!extra) return out;
  for (const [k, v] of Object.entries(extra)) {
    if (v !== undefined && v !== null && v !== '') out[k] = v as string | number;
  }
  return out;
}

export const alocacaoAtendimentoService = {
  list: async (params?: ListQueryParams & Record<string, string | number>) => {
    const response = await api.get<PaginatedResponse<AlocacaoAtendimento>>(base, {
      params: buildListParams(params),
    });
    return response.data;
  },
  get: async (id: number) => (await api.get<AlocacaoAtendimento>(`${base}${id}/`)).data,
  create: async (payload: AlocacaoAtendimentoPayload) =>
    (await api.post<AlocacaoAtendimento>(base, payload)).data,
  update: async (id: number, payload: Partial<AlocacaoAtendimentoPayload>) =>
    (await api.patch<AlocacaoAtendimento>(`${base}${id}/`, payload)).data,
  remove: async (id: number) => {
    await api.delete(`${base}${id}/`);
  },
  listByPedidoVenda: async (pedidoId: number, faturamentoId?: number) => {
    const response = await api.get<AlocacoesAtendimentoListResponse>(
      `pedidos-venda/${pedidoId}/alocacoes-atendimento/`,
      { params: faturamentoId ? { faturamento_id: faturamentoId } : undefined },
    );
    return response.data;
  },
  listByNFeSaida: async (nfeId: number) =>
    (await api.get<AlocacoesAtendimentoListResponse>(`nf-saidas/${nfeId}/alocacoes-atendimento/`)).data,

  opcoesFornecedores: async (search: string, extra?: OpcoesParams) =>
    (await api.get<OpcaoFornecedor[]>(`${base}opcoes/fornecedores/`, { params: opcoesParams({ search, ...extra }) }))
      .data,

  opcoesPedidosCompra: async (search: string, extra?: OpcoesParams) =>
    (await api.get<OpcaoPedidoCompra[]>(`${base}opcoes/pedidos-compra/`, { params: opcoesParams({ search, ...extra }) }))
      .data,

  opcoesPedidosCompraItens: async (search: string, extra?: OpcoesParams) =>
    (
      await api.get<OpcaoPedidoCompraItem[]>(`${base}opcoes/pedidos-compra-itens/`, {
        params: opcoesParams({ search, ...extra }),
      })
    ).data,

  opcoesNfeEntradaImportada: async (search: string, extra?: OpcoesParams) =>
    (
      await api.get<OpcaoNfeEntradaImportada[]>(`${base}opcoes/nfe-entrada-importada/`, {
        params: opcoesParams({ search, somente_conferidas: true, ...extra }),
      })
    ).data,

  opcoesNfeEntradaImportadaItens: async (search: string, extra?: OpcoesParams) =>
    (
      await api.get<OpcaoNfeEntradaImportadaItem[]>(`${base}opcoes/nfe-entrada-importada-itens/`, {
        params: opcoesParams({ search, ...extra }),
      })
    ).data,

  opcoesCteConferido: async (search: string, extra?: OpcoesParams) =>
    (
      await api.get<OpcaoCteConferido[]>(`${base}opcoes/cte-importado-conferido/`, {
        params: opcoesParams({ search, ...extra }),
      })
    ).data,
};
