import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Download, FileDown, MoreVertical, Pencil, Trash2 } from 'lucide-react';
import PedidoVendaWorkspace from './PedidosVendaWorkspace';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { pedidosVendaService } from '@/services/api/comercial';
import { PageHeader } from '@/components/PageHeader';

import { clientesService } from '@/services/api/clientes';
import { empresasService } from '@/services/api/empresas';
import { produtosService } from '@/services/api/produtos';
import { buildDueDates } from '@/lib/paymentTerms';
import { previewCondicaoPagamento } from '@/lib/condicaoPagamento';
import { formatDateBr } from '@/lib/dateBr';
import {
  clienteStubForDisplay,
  colaboradorStubForDisplay,
  produtoStubForDisplay,
  vendedorStubForDisplay,
} from '@/lib/comercialAutocomplete';
import { colaboradoresService } from '@/services/api/colaboradores';
import { vendedoresService } from '@/services/api/vendedores';
import { apiErrorMessage } from '@/services/api/config';
import { toast } from 'sonner';
import type { PedidoVenda, ItemPedido, Cliente, Empresa, Produto, Vendedor, Colaborador } from '@/types';
import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';
import {
  buildItemPayload,
  computePedidoTotal,
  normalizeItemPedidoForForm,
} from '@/lib/pedidosVendaItems';
import {
  CONDICAO_PAGAMENTO_PADRAO,
  STATUS_PEDIDO_VENDA_INICIAL,
  dataHojeIso,
} from '@/lib/comercialFormDefaults';
import { MSG_PDF_PEDIDO_SEM_ID, resolvePedidoVendaId } from '@/lib/pedidoVendaId';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { FilterBar } from '@/components/list/FilterBar';
import { EmptyState, ErrorState, LoadingState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { AtendimentoOperacionalInline } from '@/components/comercial/AtendimentoOperacionalInline';
import {formatMoneyBRL} from '@/lib/numberFields';
type PedidosVendaProps = {
  dedicated?: boolean;
  pedido?: PedidoVenda | null;
};

const PedidosVenda = ({ dedicated = false, pedido = null }: PedidosVendaProps) => {
   const [searchParams] = useSearchParams();
   const navigate = useNavigate();
   const statusUrl = searchParams.get('status') || '';
  const {
    items,
    count,
    page,
    pageSize,
    totalPages,
    search,
    setSearch,
    setPage,
    setPageSize,
    filters,
    setFilter,
    loading: loadingList,
    error: loadError,
    reload: load,
} = usePaginatedList<PedidoVenda>({
     fetchPage: pedidosVendaService.listPaginated,
     enabled: !dedicated,
     initialFilters: statusUrl ? { status: statusUrl } : {},
   });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<PedidoVenda | null>(null);
  const [selectedCliente, setSelectedCliente] = useState<Cliente | null>(null);
  const [selectedVendedor, setSelectedVendedor] = useState<Vendedor | null>(null);
  const [selectedColaboradorVendedor, setSelectedColaboradorVendedor] = useState<Colaborador | null>(null);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [produtoCache, setProdutoCache] = useState<Map<number, Produto>>(() => new Map());
  const [form, setForm] = useState({
    numero: '',
    empresa_emitente_id: null as number | null,
    cliente_id: null as number | null,
    data: '',
    status: 'Pendente',
    proposta_id: undefined as number | undefined,
    vendedor_id: null as number | null,
    condicao_pagamento_texto: CONDICAO_PAGAMENTO_PADRAO,
    prazo_entrega_texto: '',
    observacoes_comerciais: '',
    observacoes_internas: '',
  });
  const [itens, setItens] = useState<ItemPedido[]>([]);
  const [referenciaFrete, setReferenciaFrete] = useState<{
    periodo_utilizado: Record<string, string | undefined>;
    referencia_historica: {
      frete_medio_observado: number | null;
      peso_frete_sobre_faturamento: number | null;
      quantidade_ctes_validos: number;
      transportadora_referencia: { transportadora_id: number; transportadora_nome: string } | null;
    };
    mensagem: string;
    tem_base_historica: boolean;
  } | null>(null);
  const [referenciaCustoCompra, setReferenciaCustoCompra] = useState<{
    periodo_utilizado: Record<string, string | undefined>;
    referencia_historica: {
      custo_medio_observado: number | null;
      ultimo_custo_observado: number | null;
      quantidade_notas_base: number;
      quantidade_itens_base: number;
      fornecedor_referencia: string | null;
    };
    mensagem: string;
    tem_base_historica: boolean;
  } | null>(null);

  const [faturamentoRefreshKey, setFaturamentoRefreshKey] = useState(0);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (statusUrl) setFilter('status', statusUrl);
  }, [statusUrl, setFilter]);

  useEffect(() => {
    empresasService.getAll().then(setEmpresas).catch(() => setEmpresas([]));
  }, []);

  const pedidoDeepLink = searchParams.get('pedido');

  const hydrateVendedor = (vendedorId: number | null, nomeFallback?: string) => {
    if (!vendedorId) {
      setSelectedVendedor(null);
      setSelectedColaboradorVendedor(null);
      return;
    }
    void Promise.all([
      vendedoresService.getById(vendedorId).catch(() => null),
      colaboradoresService.getAll({ funcao: 'vendedor', limit: 200 }).catch(() => []),
    ]).then(([vendedor, colaboradores]) => {
      const colab = colaboradores.find((c) => c.vendedor_id === vendedorId);
      if (colab) {
        setSelectedColaboradorVendedor(colab);
        setSelectedVendedor(
          vendedor ?? vendedorStubForDisplay(vendedorId, colab.nome, colab.codigo),
        );
        return;
      }
      const nome = vendedor?.nome || nomeFallback || '—';
      const codigo = vendedor?.codigo || '';
      setSelectedVendedor(vendedor ?? vendedorStubForDisplay(vendedorId, nome, codigo));
      setSelectedColaboradorVendedor(null);
    });
  };

  const hydrateCliente = (clienteId: number | null, nomeFallback?: string) => {
    if (!clienteId) {
      setSelectedCliente(null);
      return;
    }
    void clientesService
      .getById(clienteId)
      .then(setSelectedCliente)
      .catch(() => setSelectedCliente(clienteStubForDisplay(clienteId, nomeFallback || '—')));
  };

  const mergeProdutoCache = (p: Produto) => {
    setProdutoCache((prev) => new Map(prev).set(p.id, p));
  };

  const hydrateProdutosItens = (lista: ItemPedido[] | undefined) => {
    const stubs = new Map<number, Produto>();
    for (const it of lista ?? []) {
      if (!it.produto_id) continue;
      stubs.set(it.produto_id, produtoStubForDisplay(it.produto_id, '', it.produto_nome || ''));
    }
    setProdutoCache(stubs);
    for (const it of lista ?? []) {
      if (!it.produto_id) continue;
      void produtosService.getById(it.produto_id).then(mergeProdutoCache).catch(() => undefined);
    }
  };



  useEffect(() => {
    if (!modalOpen || empresas.length !== 1) return;
    setForm((f) => ({ ...f, empresa_emitente_id: empresas[0].id }));
  }, [modalOpen, empresas]);

  useEffect(() => {
    if (!modalOpen) return;
    const qs = new URLSearchParams();
    if (form.data) {
      const ym = form.data.slice(0, 7);
      if (ym.length === 7) qs.set('mes', ym);
    }
    if (form.empresa_emitente_id) qs.set('empresa_id', String(form.empresa_emitente_id));
    void pedidosVendaService
      .referenciaComercialFrete(qs)
      .then(setReferenciaFrete)
      .catch(() => setReferenciaFrete(null));
    const itemRef = itens.find((i) => i.produto_id);
    if (itemRef?.produto_id) qs.set('produto_id', String(itemRef.produto_id));
    void pedidosVendaService
      .referenciaComercialCustoCompra(qs)
      .then(setReferenciaCustoCompra)
      .catch(() => setReferenciaCustoCompra(null));
  }, [modalOpen, form.data, form.empresa_emitente_id, itens]);

  const addItem = () =>
    setItens((p) => [
      ...p,
      {
        id: Date.now(),
        produto_id: 0,
        produto_nome: '',
        quantidade: 1,
        quantidade_negociada: 1,
        unidade_negociada: 'PC',
        valor_unitario: 0,
        preco_por_unidade_negociada: 0,
        corrida_id: undefined,
        corrida_numero: '',
      },
    ]);
  const removeItem = (id: number) => setItens((p) => p.filter((i) => i.id !== id));
  const total = computePedidoTotal(itens);

  const updateItem = (idx: number, patch: Partial<ItemPedido>) => {
    setItens((prev) => {
      const next = [...prev];
      const merged: ItemPedido = { ...next[idx], ...patch };
      if (Object.prototype.hasOwnProperty.call(patch, 'quantidade_negociada')) {
        merged.quantidade = Number(merged.quantidade_negociada ?? merged.quantidade ?? 0);
      }
      if (Object.prototype.hasOwnProperty.call(patch, 'preco_por_unidade_negociada')) {
        const preco = Number(merged.preco_por_unidade_negociada ?? merged.valor_unitario ?? 0);
        merged.preco_por_unidade_negociada = preco;
        // Espelho legado (2 casas) — a precisão comercial fica em preco_por_unidade_negociada.
        merged.valor_unitario = Math.round((preco + Number.EPSILON) * 100) / 100;
      }
      next[idx] = merged;
      return next;
    });
  };

  const aplicarConversao = async (idx: number, patch?: Partial<ItemPedido>) => {
    const row = { ...itens[idx], ...patch };
    if (!row?.produto_id) return;
    const produto = produtoCache.get(row.produto_id);
    if (!produto) return;
    const unidadeNegociada = (row.unidade_negociada || produto.unidade_venda_efetiva || produto.unidade || 'PC').toUpperCase();
    const quantidadeNegociada = Number(row.quantidade_negociada ?? row.quantidade ?? 0);
    const unidadeEstoque = (produto.unidade_estoque_efetiva || produto.unidade_estoque || produto.unidade || unidadeNegociada).toUpperCase();
    if (!produto.usa_conversao_dimensional_efetivo || unidadeNegociada === unidadeEstoque) {
      updateItem(idx, {
        unidade_negociada: unidadeNegociada,
        quantidade_negociada: quantidadeNegociada,
        unidade_estoque_calculada: unidadeEstoque,
        quantidade_estoque_calculada: quantidadeNegociada,
        fator_conversao: 1,
      });
      return;
    }
    try {
      const conv = await produtosService.converterMedida({
        produto_id: row.produto_id,
        quantidade: quantidadeNegociada,
        unidade_origem: unidadeNegociada,
        unidade_destino: unidadeEstoque,
      });
      const qtdOrig = Number(conv.quantidade_origem || quantidadeNegociada);
      const qtdDest = Number(conv.quantidade_destino || quantidadeNegociada);
      updateItem(idx, {
        unidade_negociada: unidadeNegociada,
        quantidade_negociada: qtdOrig,
        quantidade: qtdOrig,
        unidade_estoque_calculada: conv.unidade_estoque || unidadeEstoque,
        quantidade_estoque_calculada: qtdDest,
        peso_total_kg: Number(conv.peso_kg || 0),
        metros_total: Number(conv.metros || 0),
        barras_total: Number(conv.barras || 0),
        fator_conversao: qtdOrig ? qtdDest / qtdOrig : 0,
      });
    } catch {
      // Sem bloqueio do fluxo principal do pedido.
    }
  };

  const openNew = () => {
    setEditing(null);
    setSelectedCliente(null);
    setSelectedVendedor(null);
    setSelectedColaboradorVendedor(null);
    setProdutoCache(new Map());
    setForm({
      numero: '',
      empresa_emitente_id: empresas.length === 1 ? empresas[0]?.id ?? null : null,
      cliente_id: null,
      data: dataHojeIso(),
      status: STATUS_PEDIDO_VENDA_INICIAL,
      proposta_id: undefined,
      vendedor_id: null,
      condicao_pagamento_texto: CONDICAO_PAGAMENTO_PADRAO,
      prazo_entrega_texto: '',
      observacoes_comerciais: '',
      observacoes_internas: '',
    });
    setItens([]);
    setSaveError(null);
    setModalOpen(true);
  };
  const openEdit = (e: PedidoVenda) => {
    void pedidosVendaService.getById(e.id).then((p) => {
      setEditing(p);
      hydrateCliente(p.cliente_id, p.cliente_nome);
      hydrateVendedor(p.vendedor_id ?? null, p.vendedor_nome || p.vendedor);
      hydrateProdutosItens(p.itens);
      setForm({
        numero: p.numero ?? '',
        empresa_emitente_id: p.empresa_emitente_id ?? (empresas.length === 1 ? empresas[0]?.id ?? null : null),
        cliente_id: p.cliente_id ?? null,
        data: p.data ?? '',
        status: p.status || STATUS_PEDIDO_VENDA_INICIAL,
        proposta_id: p.proposta_id,
        vendedor_id: p.vendedor_id ?? null,
        condicao_pagamento_texto: p.condicao_pagamento_texto ?? CONDICAO_PAGAMENTO_PADRAO,
        prazo_entrega_texto: p.prazo_entrega_texto ?? '',
        observacoes_comerciais: p.observacoes_comerciais ?? '',
        observacoes_internas: p.observacoes_internas ?? '',
      });
      setItens((p.itens ?? []).map(normalizeItemPedidoForForm));
      setSaveError(null);
      setModalOpen(true);
    });
  };
  const handleVisualizarPdf = async (pedido: PedidoVenda) => {
    const id = resolvePedidoVendaId(pedido);
    if (id == null) {
      console.error('[PedidosVenda] Visualizar PDF: id ausente na linha da listagem', pedido);
      toast.error(MSG_PDF_PEDIDO_SEM_ID);
      return;
    }
    const previewTab = window.open('about:blank', '_blank');
    if (!previewTab) {
      toast.error('Não foi possível abrir uma nova aba (pop-up bloqueado).');
      return;
    }
    try {
      await pedidosVendaService.visualizarPdf(
        id,
        pedido.numero || String(id),
        previewTab,
        MSG_PDF_PEDIDO_SEM_ID,
      );
    } catch (e) {
      previewTab.close();
      toast.error(e instanceof Error ? e.message : 'Não foi possível visualizar o PDF do pedido de venda.');
    }
  };

  const handleBaixarPdf = async (pedido: PedidoVenda) => {
    const id = resolvePedidoVendaId(pedido);
    if (id == null) {
      toast.error(MSG_PDF_PEDIDO_SEM_ID);
      return;
    }
    try {
      await pedidosVendaService.baixarPdf(
        id,
        pedido.numero || String(id),
        MSG_PDF_PEDIDO_SEM_ID,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Não foi possível baixar o PDF do pedido de venda.');
    }
  };

  const handleDelete = async (pedido: PedidoVenda) => {
    const id = resolvePedidoVendaId(pedido);
    if (id == null) {
      toast.error('Não foi possível identificar o pedido para excluir. Recarregue a lista.');
      return;
    }
    const propostaRef = pedido.proposta_numero
      ? ` ${pedido.proposta_numero}`
      : pedido.proposta_id
        ? ` #${pedido.proposta_id}`
        : '';
    const msg = pedido.proposta_id
      ? `Excluir o pedido de venda ${pedido.numero}? Os itens vinculados na proposta${propostaRef} voltarão para pendente, se não houver faturamento ou outros efeitos operacionais.`
      : 'Excluir este pedido de venda?';
    if (!confirm(msg)) return;
    try {
      await pedidosVendaService.delete(id);
      load();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível excluir o pedido de venda.' }));
    }
  };
  const buildItensPayload = (): Array<Record<string, unknown>> =>
    itens.map((it, idx) => buildItemPayload(it, idx));

  const handleSave = async () => {
    setSaveError(null);
    if (!form.cliente_id) {
      const msg = 'Selecione um cliente.';
      setSaveError(msg);
      toast.error(msg);
      return;
    }
    if (empresas.length > 1 && !form.empresa_emitente_id) {
      const msg = 'Selecione a empresa emitente (matriz ou filial).';
      setSaveError(msg);
      toast.error(msg);
      return;
    }
    try {
      const condPreview = previewCondicaoPagamento(form.condicao_pagamento_texto, form.data);
      if (condPreview.erro) {
        setSaveError(condPreview.erro);
        toast.error(condPreview.erro);
        return;
      }
      const dias = condPreview.prazos ?? [];
      const vencimentos = buildDueDates(form.data, dias);
      const { proposta_id: _propostaId, ...formSemProposta } = form;
      const itensPayload = buildItensPayload();
      const data = { ...formSemProposta, itens: itensPayload, valor_total: total };
      const payload = { ...data, dias_parcelas: dias, quantidade_parcelas: dias.length, vencimentos_previstos: vencimentos };
      if (!form.numero?.trim()) {
        delete (payload as { numero?: string }).numero;
      }
      if (editing) await pedidosVendaService.update(editing.id, payload);
      else await pedidosVendaService.create(payload as Omit<PedidoVenda, 'id'>);
      setModalOpen(false);
      toast.success('Pedido salvo com sucesso.');
      load();
    } catch (err) {
      const msg = apiErrorMessage(err, {
        fallback: 'Não foi possível salvar o pedido. Verifique os itens informados.',
      });
      setSaveError(msg);
      toast.error(msg);
    }
  };

  const statusLegadoPedido =
    editing && ['Pendente', 'Em separação', 'Faturado'].includes(editing.status);
  const statusOpcoesPedido = [
    { value: 'ABERTO', label: 'Aberto' },
    { value: 'APROVADO', label: 'Aprovado' },
    { value: 'EM_FATURAMENTO', label: 'Em faturamento' },
    { value: 'PARCIALMENTE_FATURADO', label: 'Parcialmente faturado' },
    { value: 'FATURADO', label: 'Faturado' },
    { value: 'CANCELADO', label: 'Cancelado' },
  ];
  if (statusLegadoPedido) {
    if (editing?.status === 'Pendente') statusOpcoesPedido.push({ value: 'Pendente', label: 'Pendente (legado)' });
    if (editing?.status === 'Em separação') statusOpcoesPedido.push({ value: 'Em separação', label: 'Em separação (legado)' });
    if (editing?.status === 'Faturado') statusOpcoesPedido.push({ value: 'Faturado', label: 'Faturado (legado)' });
  }

  const onAtendimentoResumoAtualizado = useCallback((resumo: ResumoAtendimentoOperacional | null) => {
    setEditing((prev) => (prev ? { ...prev, resumo_atendimento_operacional: resumo } : prev));
  }, []);

  const onFaturamentoAtualizado = useCallback(async () => {
    const id = editing?.id;
    if (!id) return;
    try {
      setFaturamentoRefreshKey((k) => k + 1);
      await load();
      const p = await pedidosVendaService.getById(id);
      setEditing(p);
      setForm((f) => ({
        ...f,
        status: p.status || f.status,
        observacoes_comerciais: p.observacoes_comerciais ?? f.observacoes_comerciais,
        observacoes_internas: p.observacoes_internas ?? f.observacoes_internas,
      }));
      setItens((p.itens ?? []).map(normalizeItemPedidoForForm));
    } catch {
      // Evita rejeição não tratada quando o navegador satura conexões (loop interrompido).
    }
  }, [editing?.id, load]);

   // NEW: Initialization functions for dedicated mode
   const initializeNew = () => {
     openNew();
   };

   const initializeEdit = (pedidoToEdit: PedidoVenda) => {
     setEditing(pedidoToEdit);
     hydrateCliente(pedidoToEdit.cliente_id, pedidoToEdit.cliente_nome);
     hydrateVendedor(pedidoToEdit.vendedor_id ?? null, pedidoToEdit.vendedor_nome || pedidoToEdit.vendedor);
     hydrateProdutosItens(pedidoToEdit.itens ?? []);
     setForm({
       numero: pedidoToEdit.numero ?? '',
       empresa_emitente_id: pedidoToEdit.empresa_emitente_id ?? (empresas.length === 1 ? empresas[0]?.id ?? null : null),
       cliente_id: pedidoToEdit.cliente_id ?? null,
       data: pedidoToEdit.data ?? '',
       status: pedidoToEdit.status || STATUS_PEDIDO_VENDA_INICIAL,
       proposta_id: pedidoToEdit.proposta_id,
       vendedor_id: pedidoToEdit.vendedor_id ?? null,
       condicao_pagamento_texto: pedidoToEdit.condicao_pagamento_texto ?? CONDICAO_PAGAMENTO_PADRAO,
       prazo_entrega_texto: pedidoToEdit.prazo_entrega_texto ?? '',
       observacoes_comerciais: pedidoToEdit.observacoes_comerciais ?? '',
       observacoes_internas: pedidoToEdit.observacoes_internas ?? '',
     });
     setItens((pedidoToEdit.itens ?? []).map(normalizeItemPedidoForForm));
     setSaveError(null);
     setModalOpen(true);
   };

   const initializeRef = useRef({ initializeNew, initializeEdit });
   initializeRef.current = { initializeNew, initializeEdit };

   useEffect(() => {
     if (!dedicated) return;
     if (pedido) {
       initializeRef.current.initializeEdit(pedido);
     } else {
       initializeRef.current.initializeNew();
     }
   }, [dedicated, pedido]);

   const handleModalClose = () => {
     if (dedicated) {
       navigate('/pedidos-venda');
     } else {
       setModalOpen(false);
     }
   };

return (
     <div>
       {!dedicated ? (
         <>
<PageHeader
              title="Pedidos de Venda"
              description="Gestão de pedidos comerciais, status e faturamento."
              onAdd={() => navigate('/pedidos-venda/novo')}
              addLabel="Novo Pedido"
              searchValue={search}
              onSearch={setSearch}
              searchPlaceholder="Digite parte do número do pedido, como 0006 ou 20260714."
            />
           <FilterBar
             filters={[
               {
                 key: 'status',
                 label: 'Status',
                 value: filters.status || '',
                 options: [
                   { value: 'aberto', label: 'Aberto' },
                   { value: 'PARCIAL', label: 'Parcialmente faturado' },
                   { value: 'FATURADO', label: 'Faturado' },
                   { value: 'CANCEL', label: 'Cancelado' },
                 ],
               },
             ]}
             onChange={setFilter}
           />
           {loadError ? <ErrorState message={loadError} onRetry={() => void load()} /> : null}
           <DataTableShell>
             {loadingList ? <LoadingState message="Carregando pedidos de venda…" /> : null}
             {!loadingList && !loadError ? (
               <DataTable mobileMode="cards">
                 <thead>
                   <tr>
                     <th>Número</th>
                     <th>Cliente</th>
                     <th>Data</th>
                     <th>Status</th>
                     <th>Atendimento</th>
                     <th>Valor Total</th>
                     <th className="w-36 text-right">Ações</th>
                   </tr>
                 </thead>
                 <tbody>
                   {items.length === 0 ? (
                     <tr>
                       <td colSpan={7}>
                         <EmptyState message="Nenhum pedido de venda encontrado." actionLabel="Novo pedido" onAction={() => navigate('/pedidos-venda/novo')} />
                       </td>
                     </tr>
                   ) : null}
                   {!loadingList &&
                     items.map((e) => (
                       <tr key={resolvePedidoVendaId(e) ?? e.numero}>
                         <td data-label="Número" className="font-medium">{e.numero || '—'}</td>
                         <td data-label="Cliente">{e.cliente_nome || '—'}</td>
                         <td data-label="Data">{formatDateBr(e.data)}</td>
                         <td data-label="Status">
                           <StatusBadge status={e.status} />
                         </td>
<td data-label="Atendimento">
                            <AtendimentoOperacionalInline
                              resumo={e.resumo_atendimento_operacional}
                              apenasComAlocacao={false}
                              maxBadges={2} />
                         </td>
                         <td data-label="Valor total">{formatMoneyBRL(e.valor_total ?? 0)}</td>
                         <td data-label="Ações" className="text-right">
                           <DropdownMenu>
                             <DropdownMenuTrigger asChild>
                               <button type="button" className="erp-btn-ghost erp-btn-sm" aria-label="Ações do pedido">
                                 <MoreVertical className="h-4 w-4" />
                               </button>
                             </DropdownMenuTrigger>
                             <DropdownMenuContent align="end" className="w-52" onOpenAutoFocus={(ev) => ev.preventDefault()}>
                               <DropdownMenuItem className="cursor-pointer" onSelect={() => navigate(`/pedidos-venda/${resolvePedidoVendaId(e)}`)}>
                                 <span className="flex items-center gap-2">
                                   <Pencil className="h-4 w-4" />
                                   Editar
                                 </span>
                               </DropdownMenuItem>
                               <DropdownMenuItem className="cursor-pointer" onSelect={() => void handleVisualizarPdf(e)}>
                                 <span className="flex items-center gap-2">
                                   <FileDown className="h-4 w-4" />
                                   Visualizar PDF
                                 </span>
                               </DropdownMenuItem>
                               <DropdownMenuItem className="cursor-pointer" onSelect={() => void handleBaixarPdf(e)}>
                                 <span className="flex items-center gap-2">
                                   <Download className="h-4 w-4" />
                                   Baixar PDF
                                 </span>
                               </DropdownMenuItem>
                               <DropdownMenuSeparator />
                               <DropdownMenuItem
                                 className="cursor-pointer text-destructive focus:text-destructive"
                                 onSelect={() => void handleDelete(e)}
                               >
                                 <span className="flex items-center gap-2">
                                   <Trash2 className="h-4 w-4" />
                                   Excluir
                                 </span>
                               </DropdownMenuItem>
                             </DropdownMenuContent>
                           </DropdownMenu>
                         </td>
                       </tr>
                     ))}
                 </tbody>
               </DataTable>
               ) : null}
               {!loadingList && !loadError && count > 0 ? (
                 <PaginationControls
                   page={page}
                   pageSize={pageSize}
                   count={count}
                   totalPages={totalPages}
                   onPageChange={setPage}
                   onPageSizeChange={setPageSize}
                 />
               ) : null}
             </DataTableShell>

         </>
       ) : (
         <PedidoVendaWorkspace pedido={editing} onClose={handleModalClose} />
       )}
     </div>
   );
};

export default PedidosVenda;
