import { useCallback, useReducer } from 'react';

import { aplicarStatusAutomaticoItem } from '@/lib/conferenciaNfeStatus';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import { pedidosCompraService } from '@/services/api/comercial';
import { produtosService } from '@/services/api/produtos';
import type {
  ItemConferenciaNFeEntrada,
  NFeEntradaConferencia,
  PedidoCompra,
  Produto,
} from '@/types';

/**
 * Store de estado de DOMÍNIO da conferência de NF-e de entrada (PR 8a da Fase 2).
 *
 * Hook puro, sem Provider/useContext: o painel é o único consumidor e o rail /
 * os blocos extraídos (reabertura PR 6, devolução PR 7) não leem este estado.
 *
 * Arquitetura (contrato do PR 5, S3):
 * - reducer PURA: só transforma estado, zero IO;
 * - thunks FORA do reducer: `load` e `hydrateProdutoCache` consultam a API e
 *   depois dispatcham;
 * - ambiente NÃO entra no store: `nfId` é argumento de `load(nfId)`; `embedded`,
 *   `onUpdated` e `onClose` continuam props do painel.
 *
 * `pedidos` e `avisoPedido` entram no estado porque `load` os escreve no mesmo
 * instante que `dados` (disco: setDados + setPedidos + setAvisoPedido('') dentro
 * de load); mantê-los como useState do painel criaria dualidade de fonte.
 */
export type ConferenciaEstado = {
  dados: NFeEntradaConferencia | null;
  pedidos: PedidoCompra[];
  produtoCache: Map<number, Produto>;
  erro: string;
  avisoPedido: string;
  busy: boolean;
};

type SetorPayload<T> = T | ((prev: T) => T);

export type ConferenciaAction =
  | { type: 'SET_DADOS'; dados: SetorPayload<NFeEntradaConferencia | null> }
  | { type: 'PATCH_DADOS'; patch: Partial<NFeEntradaConferencia> }
  | { type: 'SET_PEDIDOS'; pedidos: PedidoCompra[] }
  | { type: 'SET_PRODUTO_CACHE'; produtoCache: SetorPayload<Map<number, Produto>> }
  | { type: 'UPSERT_PRODUTO_CACHE'; produto: Produto; apenasSeAusente?: boolean }
  | { type: 'SET_ERRO'; erro: SetorPayload<string> }
  | { type: 'SET_AVISO_PEDIDO'; avisoPedido: SetorPayload<string> }
  | { type: 'SET_BUSY'; busy: boolean }
  | { type: 'UPDATE_ITEM'; itemId: number; patch: Partial<ItemConferenciaNFeEntrada> };

const resolve = <T,>(atual: T, proximo: SetorPayload<T>): T =>
  typeof proximo === 'function' ? (proximo as (prev: T) => T)(atual) : proximo;

/** Reducer PURA — nenhuma chamada de API acontece aqui. */
export function conferenciaReducer(estado: ConferenciaEstado, action: ConferenciaAction): ConferenciaEstado {
  switch (action.type) {
    case 'SET_DADOS':
      return { ...estado, dados: resolve(estado.dados, action.dados) };
    case 'PATCH_DADOS':
      // Equivalente do setDados funcional do cabeçalho (disco :571): só patchia se houver dados.
      return estado.dados ? { ...estado, dados: { ...estado.dados, ...action.patch } } : estado;
    case 'SET_PEDIDOS':
      return { ...estado, pedidos: action.pedidos };
    case 'SET_PRODUTO_CACHE':
      return { ...estado, produtoCache: resolve(estado.produtoCache, action.produtoCache) };
    case 'UPSERT_PRODUTO_CACHE': {
      if (action.apenasSeAusente && estado.produtoCache.has(action.produto.id)) return estado;
      const next = new Map(estado.produtoCache);
      next.set(action.produto.id, action.produto);
      return { ...estado, produtoCache: next };
    }
    case 'SET_ERRO':
      return { ...estado, erro: resolve(estado.erro, action.erro) };
    case 'SET_AVISO_PEDIDO':
      return { ...estado, avisoPedido: resolve(estado.avisoPedido, action.avisoPedido) };
    case 'SET_BUSY':
      return { ...estado, busy: action.busy };
    case 'UPDATE_ITEM': {
      // Corpo do updateItem extraído token-a-token do painel (disco :238-254):
      // sem dados, nenhuma linha é tocada.
      if (!estado.dados) return estado;
      return {
        ...estado,
        dados: {
          ...estado.dados,
          itens: estado.dados.itens.map((it) => {
            if (it.id !== action.itemId) return it;
            const merged = { ...it, ...action.patch };
            if (action.patch.status === 'IGNORADO') return merged;
            if (Object.prototype.hasOwnProperty.call(action.patch, 'status')) return merged;
            return aplicarStatusAutomaticoItem(merged);
          }),
        },
      };
    }
    default:
      return estado;
  }
}

const estadoInicial: ConferenciaEstado = {
  dados: null,
  pedidos: [],
  produtoCache: new Map<number, Produto>(),
  erro: '',
  avisoPedido: '',
  busy: false,
};

export type ConferenciaAcoes = {
  /** THUNK: busca conferência + pedidos, popula cache de produtos. O chamador trata o reject (como hoje). */
  load: (nfId: number) => Promise<void>;
  /** THUNK: deriva o cache de produtos dos itens/sugestões da conferência recebida. */
  hydrateProdutoCache: (conf: NFeEntradaConferencia) => Promise<void>;
  /** Redutor puro UPDATE_ITEM — patch local, sem IO (como no disco). */
  updateItem: (itemId: number, patch: Partial<ItemConferenciaNFeEntrada>) => void;
  setDados: (dados: SetorPayload<NFeEntradaConferencia | null>) => void;
  patchDados: (patch: Partial<NFeEntradaConferencia>) => void;
  setProdutoCache: (produtoCache: SetorPayload<Map<number, Produto>>) => void;
  upsertProdutoCache: (produto: Produto, opcoes?: { apenasSeAusente?: boolean }) => void;
  setErro: (erro: SetorPayload<string>) => void;
  setAvisoPedido: (avisoPedido: SetorPayload<string>) => void;
  setBusy: (busy: boolean) => void;
};

export function useConferenciaStore(): { estado: ConferenciaEstado; acoes: ConferenciaAcoes } {
  const [estado, dispatch] = useReducer(conferenciaReducer, estadoInicial);

  const hydrateProdutoCache = useCallback(async (conf: NFeEntradaConferencia) => {
    const cache = new Map<number, Produto>();
    const ids = [...new Set(conf.itens.map((it) => it.produto_id).filter((id): id is number => Boolean(id)))];
    const loaded = await Promise.all(ids.map((id) => produtosService.getById(id).catch(() => null)));
    loaded.forEach((p) => {
      if (p) cache.set(p.id, p);
    });
    conf.itens.forEach((it) => {
      (it.sugestoes_produto || []).forEach((s) => {
        if (!cache.has(s.id)) {
          cache.set(s.id, {
            id: s.id,
            codigo_completo: s.codigo,
            descricao: s.descricao,
          } as Produto);
        }
      });
    });
    dispatch({ type: 'SET_PRODUTO_CACHE', produtoCache: cache });
  }, []);

  const load = useCallback(
    async (nfId: number) => {
      if (!nfId) return;
      dispatch({ type: 'SET_ERRO', erro: '' });
      dispatch({ type: 'SET_AVISO_PEDIDO', avisoPedido: '' });
      const [conf, pcs] = await Promise.all([
        nfeEntradaConferenciaService.get(nfId),
        pedidosCompraService.getAll(),
      ]);
      dispatch({ type: 'SET_DADOS', dados: conf });
      dispatch({ type: 'SET_PEDIDOS', pedidos: pcs });
      await hydrateProdutoCache(conf);
    },
    [hydrateProdutoCache],
  );

  const acoes: ConferenciaAcoes = {
    load,
    hydrateProdutoCache,
    updateItem: useCallback(
      (itemId: number, patch: Partial<ItemConferenciaNFeEntrada>) =>
        dispatch({ type: 'UPDATE_ITEM', itemId, patch }),
      [],
    ),
    setDados: useCallback((dados: SetorPayload<NFeEntradaConferencia | null>) => dispatch({ type: 'SET_DADOS', dados }), []),
    patchDados: useCallback((patch: Partial<NFeEntradaConferencia>) => dispatch({ type: 'PATCH_DADOS', patch }), []),
    setProdutoCache: useCallback(
      (produtoCache: SetorPayload<Map<number, Produto>>) => dispatch({ type: 'SET_PRODUTO_CACHE', produtoCache }),
      [],
    ),
    upsertProdutoCache: useCallback(
      (produto: Produto, opcoes?: { apenasSeAusente?: boolean }) =>
        dispatch({ type: 'UPSERT_PRODUTO_CACHE', produto, apenasSeAusente: opcoes?.apenasSeAusente }),
      [],
    ),
    setErro: useCallback((erro: SetorPayload<string>) => dispatch({ type: 'SET_ERRO', erro }), []),
    setAvisoPedido: useCallback(
      (avisoPedido: SetorPayload<string>) => dispatch({ type: 'SET_AVISO_PEDIDO', avisoPedido }),
      [],
    ),
    setBusy: useCallback((busy: boolean) => dispatch({ type: 'SET_BUSY', busy }), []),
  };

  return { estado, acoes };
}
