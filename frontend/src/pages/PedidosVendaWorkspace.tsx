import { Fragment, useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight, Download, ExternalLink, FileDown, Plus, RotateCcw, X } from 'lucide-react';
import { toast } from 'sonner';
import { MSG_PDF_PEDIDO_SEM_ID, resolvePedidoVendaId } from '@/lib/pedidoVendaId';
import { MotivoAcaoDestrutivaModal } from '@/components/comercial/MotivoAcaoDestrutivaModal';
import { pedidosVendaService } from '@/services/api/comercial';
import { empresasService } from '@/services/api/empresas';
import { clientesService } from '@/services/api/clientes';
import { vendedoresService } from '@/services/api/vendedores';
import { colaboradoresService } from '@/services/api/colaboradores';
import { produtosService } from '@/services/api/produtos';
import { apiErrorMessage } from '@/services/api/config';
import { PedidoFaturamentoPanel } from '@/components/PedidoFaturamentoPanel';
import { AlocacaoAtendimentoGerenciarPanel } from '@/components/comercial/AlocacaoAtendimentoGerenciarPanel';
import { AtendimentoOperacionalResumo } from '@/components/comercial/AtendimentoOperacionalResumo';
import { DateBrInput } from '@/components/comercial/DateBrInput';
import { CondicaoPagamentoResumo } from '@/components/comercial/CondicaoPagamentoResumo';
import { ClienteComercialField } from '@/components/comercial/ClienteComercialField';
import { ProdutoComercialField } from '@/components/comercial/ProdutoComercialField';
import {
  DiscountInput,
  MoneyDisplay,
  QuantityDisplay,
  QuantityInput,
  ReadonlyCalculatedField,
  UnitPriceDisplay,
  UnitPriceInput,
  UnitSelect,
} from '@/components/comercial/fields';
import { VendedorComercialField } from '@/components/comercial/VendedorComercialField';
import { ItemComercialMetricasGrid } from '@/components/comercial/ItemComercialMetricasGrid';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatDateBr } from '@/lib/dateBr';
import { formatCurrencyBRL, formatQuantidadeBR } from '@/lib/formatBr';
import { formatPrecoUnitarioBRL } from '@/lib/pedidoVendaValorUnitario';
import {
  CONDICAO_PAGAMENTO_PADRAO,
  STATUS_PEDIDO_VENDA_INICIAL,
  dataHojeIso,
} from '@/lib/comercialFormDefaults';
import { computePedidoTotal } from '@/lib/pedidosVendaItems';
import { buildItemPayload, normalizeItemPedidoForForm } from '@/lib/pedidosVendaItems';
import { buildDueDates } from '@/lib/paymentTerms';
import {
  clienteStubForDisplay,
  vendedorStubForDisplay,
  produtoStubForDisplay,
} from '@/lib/comercialAutocomplete';
import {
  classificarNfeResumoPedido,
  getFaturamentoStatusLabel,
  getNFeFiscalBadgeTokens,
  getNfeEmissaoSefazLabel,
  getPedidoModalFooterActions,
  getStatusItemLabel,
  linhaFaturamentoNfeAmigavel,
  mensagemNfeFaturamentoInconsistencia,
  MSG_ALERTA_FATURAMENTO_SEM_ATENDIMENTO,
  MSG_PEDIDO_FATURADO_SEM_ATENDIMENTO,
  pedidoFaturadoSemAtendimento,
  pedidoFaturamentoPermiteEstorno,
  referenciaInternaNfe,
  tituloResumoNfePedido,
  tokenStatusComercialPedido,
} from '@/lib/pedidoVendaModalUi';
import { PedidoVendaFiscalNfeAcoes } from '@/components/comercial/PedidoVendaFiscalNfeAcoes';
import { PedidoVendaNfeHistoricoList } from '@/components/comercial/PedidoVendaNfeHistoricoList';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { previewCondicaoPagamento } from '@/lib/condicaoPagamento';
import {
  equivalentesPreco,
  labelPrecoPorUnidade,
  previewConversaoItem,
  todasUnidadesPadrao,
  unidadesNegociacaoProduto,
} from '@/lib/comercialDimensional';
import { labelStatusPedidoVenda } from '@/lib/comercialFormDefaults';
import { inputNumberValue } from '@/lib/numberFormat';
import {
  itemPedidoPodeExcluir,
  itemPedidoQuantidadeEditavel,
  itemPedidoReadOnly,
  MSG_PEDIDO_FATURADO_ITENS,
  pedidoItensBloqueados,
} from '@/lib/nfeSaidaUi';
import type {
  Cliente,
  Colaborador,
  Empresa,
  ItemPedido,
  PedidoVenda,
  Produto,
  ResumoFaturamentoPedido,
  Vendedor,
} from '@/types';
import { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';
import { PageHeader } from '@/components/PageHeader';

type PedidoForm = {
  numero: string;
  empresa_emitente_id: number | null;
  cliente_id: number | null;
  data: string;
  status: string;
  proposta_id?: number;
  vendedor_id: number | null;
  condicao_pagamento_texto: string;
  prazo_entrega_texto: string;
  observacoes_comerciais: string;
  observacoes_internas: string;
};

type RefFrete = {
  periodo_utilizado: Record<string, string | undefined>;
  referencia_historica: {
    frete_medio_observado: number | null;
    peso_frete_sobre_faturamento: number | null;
    quantidade_ctes_validos: number;
    transportadora_referencia: { transportadora_id: number; transportadora_nome: string } | null;
  };
  mensagem: string;
  tem_base_historica: boolean;
};

type RefCusto = {
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
};

function numSafe(v: unknown, fallback = 0): number {
  const n = Number(v ?? fallback);
  return Number.isFinite(n) ? n : fallback;
}

function itemDesconto(item: ItemPedido & { desconto?: number }): number {
  return numSafe(item.desconto ?? item.desconto_valor);
}

function itemTotalLinha(item: ItemPedido & { desconto?: number }): number {
  const qtd = numSafe(item.quantidade_negociada ?? item.quantidade);
  const preco = numSafe(item.preco_por_unidade_negociada ?? item.valor_unitario);
  return Math.max(0, qtd * preco - itemDesconto(item));
}

function labelFaturamentoResumo(status?: string): string {
  const s = (status || '').toUpperCase();
  if (s === 'FATURADO') return 'Faturado';
  if (s === 'PARCIALMENTE_FATURADO' || s === 'PARCIAL') return 'Parcial';
  if (s === 'EM_FATURAMENTO') return 'Em faturamento';
  return 'Pendente';
}

function statusItemBadge(status?: string): string {
  const s = (status || 'PENDENTE').toUpperCase();
  if (s === 'FATURADO') return 'erp-badge-success';
  if (s === 'PARCIAL') return 'erp-badge-warning';
  if (s === 'CANCELADO') return 'erp-badge-danger';
  return 'erp-badge-warning';
}

type PedidoVendaWorkspaceProps = {
  pedido: PedidoVenda | null;
  onClose: () => void;
};

export default function PedidoVendaWorkspace({ pedido, onClose }: PedidoVendaWorkspaceProps) {
  const navigate = useNavigate();
  const isNovo = pedido == null;
  const pedidoId = pedido?.id;

  const [modalTab, setModalTab] = useState('resumo');
  const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
  const [faturamentoResumo, setFaturamentoResumo] = useState<ResumoFaturamentoPedido | null>(null);
  const [faturamentoLoading, setFaturamentoLoading] = useState(false);
  const [estornoModal, setEstornoModal] = useState<{ faturamentoId: number; label: string } | null>(null);
  const [estornoLoading, setEstornoLoading] = useState(false);

  const [editing, setEditing] = useState<PedidoVenda | null>(pedido);
  const [form, setForm] = useState<PedidoForm>({
    numero: '',
    empresa_emitente_id: null,
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
  const [selectedCliente, setSelectedCliente] = useState<Cliente | null>(null);
  const [selectedVendedor, setSelectedVendedor] = useState<Vendedor | null>(null);
  const [selectedColaboradorVendedor, setSelectedColaboradorVendedor] = useState<Colaborador | null>(null);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [produtoCache, setProdutoCache] = useState<Map<number, Produto>>(() => new Map());
  const [itens, setItens] = useState<ItemPedido[]>([]);
  const [referenciaFrete, setReferenciaFrete] = useState<RefFrete | null>(null);
  const [referenciaCustoCompra, setReferenciaCustoCompra] = useState<RefCusto | null>(null);
  const [faturamentoRefreshKey, setFaturamentoRefreshKey] = useState(0);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (pedido) {
      setEditing(pedido);
      setForm({
        numero: pedido.numero ?? '',
        empresa_emitente_id: pedido.empresa_emitente_id ?? null,
        cliente_id: pedido.cliente_id ?? null,
        data: pedido.data ?? dataHojeIso(),
        status: pedido.status ?? STATUS_PEDIDO_VENDA_INICIAL,
        proposta_id: pedido.proposta_id,
        vendedor_id: pedido.vendedor_id ?? null,
        condicao_pagamento_texto: pedido.condicao_pagamento_texto ?? CONDICAO_PAGAMENTO_PADRAO,
        prazo_entrega_texto: pedido.prazo_entrega_texto ?? '',
        observacoes_comerciais: pedido.observacoes_comerciais ?? '',
        observacoes_internas: pedido.observacoes_internas ?? '',
      });
      setItens((pedido.itens ?? []).map(normalizeItemPedidoForForm));
    } else {
      setEditing(null);
      setForm((f) => ({
        ...f,
        data: f.data || dataHojeIso(),
        status: f.status || STATUS_PEDIDO_VENDA_INICIAL,
        condicao_pagamento_texto: f.condicao_pagamento_texto || CONDICAO_PAGAMENTO_PADRAO,
      }));
      setItens([]);
      setSelectedCliente(null);
      setSelectedVendedor(null);
      setSelectedColaboradorVendedor(null);
    }
  }, [pedido]);

  useEffect(() => {
    if (!form.cliente_id) {
      setSelectedCliente(null);
      return;
    }
    void clientesService
      .getById(form.cliente_id)
      .then(setSelectedCliente)
      .catch(() => setSelectedCliente(clienteStubForDisplay(form.cliente_id, '—')));
  }, [form.cliente_id]);

  useEffect(() => {
    if (!form.vendedor_id) {
      setSelectedVendedor(null);
      setSelectedColaboradorVendedor(null);
      return;
    }
    void Promise.all([
      vendedoresService.getById(form.vendedor_id).catch(() => null),
      colaboradoresService.getAll({ funcao: 'vendedor', limit: 200 }).catch(() => []),
    ]).then(([vendedor, colaboradores]) => {
      const colab = colaboradores.find((c) => c.vendedor_id === form.vendedor_id);
      if (colab) {
        setSelectedColaboradorVendedor(colab);
        setSelectedVendedor(
          vendedor ?? vendedorStubForDisplay(form.vendedor_id, colab.nome, colab.codigo),
        );
        return;
      }
      const nome = vendedor?.nome || '—';
      const codigo = vendedor?.codigo || '';
      setSelectedVendedor(vendedor ?? vendedorStubForDisplay(form.vendedor_id, nome, codigo));
      setSelectedColaboradorVendedor(null);
    });
  }, [form.vendedor_id]);

  useEffect(() => {
    empresasService.getAll().then(setEmpresas).catch(() => setEmpresas([]));
  }, []);

  useEffect(() => {
    if (empresas.length !== 1) return;
    if (form.empresa_emitente_id && empresas.some((e) => e.id === form.empresa_emitente_id)) return;
    setForm((f) => ({ ...f, empresa_emitente_id: empresas[0].id }));
  }, [empresas, form.empresa_emitente_id]);

  useEffect(() => {
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
  }, [form.data, form.empresa_emitente_id, itens]);

  useEffect(() => {
    const stubs = new Map<number, Produto>();
    for (const it of itens) {
      if (!it.produto_id) continue;
      stubs.set(it.produto_id, produtoStubForDisplay(it.produto_id, '', it.produto_nome || ''));
    }
    setProdutoCache(stubs);
    for (const it of itens) {
      if (!it.produto_id) continue;
      void produtosService.getById(it.produto_id).then(mergeProdutoCache).catch(() => undefined);
    }
  }, [itens]);

  const mergeProdutoCache = (p: Produto) => {
    setProdutoCache((prev) => new Map(prev).set(p.id, p));
  };

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

  const addItem = () =>
    setItens((p) => [
      ...p,
      {
        id: Date.now() + Math.floor(Math.random() * 1000),
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
      setSaving(true);
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
      setSaving(false);
      toast.success('Pedido salvo com sucesso.');
      onClose();
    } catch (err) {
      setSaving(false);
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

  const load = useCallback(async () => {
    setFaturamentoRefreshKey((k) => k + 1);
  }, []);

  const onFaturamentoAtualizado = useCallback(async () => {
    const id = editing?.id;
    if (!id) return;
    try {
      setFaturamentoLoading(true);
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
      setFaturamentoLoading(false);
    } catch {
      setFaturamentoLoading(false);
    }
  }, [editing?.id, load]);

  const condicaoPreview = previewCondicaoPagamento(form.condicao_pagamento_texto ?? '', form.data ?? '');
  const clienteNome = selectedCliente?.razao_social || editing?.cliente_nome || '—';
  const vendedorNome =
    selectedVendedor?.nome || editing?.vendedor_nome || editing?.vendedor || '—';
  const numeroExib = form.numero || editing?.numero || (editing ? '—' : 'Novo');
  const statusExib = form.status || editing?.status || 'ABERTO';

  useEffect(() => {
    if (!pedidoId) {
      setFaturamentoResumo(null);
      return;
    }
    setFaturamentoLoading(true);
    pedidosVendaService
      .resumoFaturamento(pedidoId)
      .then(setFaturamentoResumo)
      .catch(() => setFaturamentoResumo(null))
      .finally(() => setFaturamentoLoading(false));
  }, [pedidoId, faturamentoRefreshKey]);

  const nfesVinculadas = (faturamentoResumo?.faturamentos_nfe ?? []).filter((f) => f.nfe_saida_id);
  const linhaEstornoResumo = (faturamentoResumo?.faturamentos_nfe ?? []).find((f) =>
    pedidoFaturamentoPermiteEstorno(f),
  );
  const semNfeGerada =
    (faturamentoResumo?.faturamentos_nfe ?? []).length === 0 &&
    (faturamentoResumo?.historico_nfe_saida ?? []).length === 0;
  const itensSomenteLeitura = pedidoItensBloqueados(form.status);
  const alertaAtendimentoFaturado = pedidoFaturadoSemAtendimento(
    statusExib,
    editing?.resumo_atendimento_operacional ?? faturamentoResumo?.resumo_atendimento_operacional,
  );
  const footerConfig = getPedidoModalFooterActions(modalTab, {
    pedidoId,
    pedidoStatus: statusExib,
    isNovoPedido: !pedidoId,
  });
  const valorFaturadoCard = faturamentoResumo
    ? parseFloat(faturamentoResumo.valor_faturado || '0')
    : null;
  const valorPendenteCard = faturamentoResumo
    ? parseFloat(faturamentoResumo.valor_pendente || '0')
    : null;
  const faturamentoLabel = faturamentoResumo
    ? labelFaturamentoResumo(faturamentoResumo.status)
    : labelFaturamentoResumo(statusExib);

  const handleVisualizarPdf = async () => {
    const id = resolvePedidoVendaId(editing);
    if (id == null) {
      console.error('[PedidoVendaWorkspace] Visualizar PDF: id ausente', editing);
      alert(MSG_PDF_PEDIDO_SEM_ID);
      return;
    }
    const previewTab = window.open('about:blank', '_blank');
    if (!previewTab) {
      alert('Não foi possível abrir uma nova aba (pop-up bloqueado).');
      return;
    }
    try {
      await pedidosVendaService.visualizarPdf(
        id,
        form.numero || editing?.numero || String(id),
        previewTab,
        MSG_PDF_PEDIDO_SEM_ID,
      );
    } catch (e) {
      previewTab.close();
      alert(e instanceof Error ? e.message : 'Não foi possível visualizar o PDF do pedido de venda.');
    }
  };

  const handleBaixarPdf = async () => {
    const id = resolvePedidoVendaId(editing);
    if (id == null) {
      console.error('[PedidoVendaWorkspace] Baixar PDF: id ausente', editing);
      alert(MSG_PDF_PEDIDO_SEM_ID);
      return;
    }
    try {
      await pedidosVendaService.baixarPdf(
        id,
        form.numero || editing?.numero || String(id),
        MSG_PDF_PEDIDO_SEM_ID,
      );
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Não foi possível baixar o PDF do pedido de venda.');
    }
  };

  return (
    <Fragment>
      <div className={`px-4 pb-5 sm:px-5 sm:pb-6 ${pedidoId ? 'space-y-3' : 'space-y-2.5'}`}>
        <PageHeader
          title={editing ? `Pedido ${editing.numero || editing.id}` : 'Novo Pedido de Venda'}
          description="Dados do pedido comercial: cliente, vendedor, itens, condições e totais."
          actions={
            <button type="button" className="erp-btn-outline shrink-0" onClick={onClose}>
              Voltar
            </button>
          }
        />
        {pedidoId ? (
          <div className="grid grid-cols-2 gap-x-3.5 gap-y-1.5 rounded-lg border border-border bg-muted/15 px-2.5 py-1.5 text-sm sm:grid-cols-2 lg:grid-cols-4 lg:gap-x-3 lg:gap-y-1.5">
            <div>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Pedido</span>
              <span className="font-semibold text-foreground">{numeroExib}</span>
            </div>
            <div>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Cliente</span>
              <span className="font-medium truncate block" title={clienteNome}>
                {clienteNome}
              </span>
            </div>
            <div>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Status</span>
              <StatusBadge status={tokenStatusComercialPedido(statusExib)} className="mt-0.5" />
            </div>
            <div>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Total do pedido</span>
              <span className="font-semibold tabular-nums">
                {formatCurrencyBRL(numSafe(total))}
                <span className="text-muted-foreground font-normal"> · {faturamentoLabel}</span>
              </span>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-x-3.5 gap-y-1.5 rounded-lg border border-border bg-muted/15 px-2.5 py-1.5 text-sm sm:grid-cols-2 md:grid-cols-4 md:gap-x-3 md:gap-y-1.5">
            <div>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Número</span>
              <span className="font-semibold text-foreground">{numeroExib}</span>
            </div>
            <div>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Cliente</span>
              <span className="font-medium truncate block" title={clienteNome}>
                {clienteNome}
              </span>
            </div>
            <div>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Status</span>
              <StatusBadge status={statusExib.toLowerCase()} className="mt-0.5" />
            </div>
            <div>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Total do pedido</span>
              <span className="font-semibold tabular-nums text-foreground">
                {formatCurrencyBRL(numSafe(total))}
              </span>
            </div>
          </div>
        )}
        {saveError ? (
          <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2">
            {saveError}
          </p>
        ) : null}

        <Tabs value={modalTab} onValueChange={setModalTab} className="flex flex-col min-h-0">
          <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto whitespace-nowrap bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/90 border border-border border-b-0 rounded-t-lg px-3 pt-2.5 pb-1 sm:px-4">
            <TabsTrigger value="resumo">Dados do pedido</TabsTrigger>
            <TabsTrigger value="itens">Itens</TabsTrigger>
            {pedidoId ? <TabsTrigger value="faturamento">Faturamento</TabsTrigger> : null}
            {pedidoId ? <TabsTrigger value="atendimento">Atendimento operacional</TabsTrigger> : null}
            {pedidoId ? <TabsTrigger value="fiscal">NF-e / Fiscal</TabsTrigger> : null}
            <TabsTrigger value="historico">Observações</TabsTrigger>
          </TabsList>

          <div className="border border-border border-t-0 rounded-b-lg bg-card px-4 py-3.5 sm:px-5 sm:py-4 min-h-0 flex-1">
            <TabsContent value="resumo" className={`mt-0 ${pedidoId ? 'space-y-4' : 'space-y-3.5'}`}>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pt-0.5">
                <div>
                  <label className="erp-label">Número</label>
                  <input
                    className="erp-input mt-1"
                    placeholder={editing ? undefined : 'Gerado automaticamente (PV-AAAAMMDD-NNNN)'}
                    value={form.numero}
                    onChange={(e) => setForm((p) => ({ ...p, numero: e.target.value }))}
                  />
                </div>
                <DateBrInput label="Data" valueIso={form.data} onChangeIso={(iso) => setForm((p) => ({ ...p, data: iso }))} />
                <div>
                  <label className="erp-label">Status</label>
                  <select
                    className="erp-select mt-1 w-full"
                    value={form.status}
                    onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
                  >
                    {statusOpcoesPedido.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
                <div>
                  <label className="erp-label">Cliente</label>
                  <ClienteComercialField
                    valueId={form.cliente_id}
                    selectedCliente={selectedCliente}
                    onSelect={(c) => {
                      setForm((p) => ({ ...p, cliente_id: c.id }));
                      setSelectedCliente(c);
                    }}
                    onClear={() => {
                      setForm((p) => ({ ...p, cliente_id: null }));
                      setSelectedCliente(null);
                    }}
                  />
                </div>
                <div>
                  <label className="erp-label">Vendedor</label>
                  <VendedorComercialField
                    valueId={form.vendedor_id}
                    selectedVendedor={selectedVendedor}
                    selectedColaborador={selectedColaboradorVendedor}
                    onSelect={(vendedorId, colab) => {
                      setForm((p) => ({ ...p, vendedor_id: vendedorId }));
                      setSelectedColaboradorVendedor(colab);
                      setSelectedVendedor({ id: vendedorId, nome: colab.nome, codigo: colab.codigo, ativo: true });
                    }}
                    onClear={() => {
                      setForm((p) => ({ ...p, vendedor_id: null }));
                      setSelectedVendedor(null);
                      setSelectedColaboradorVendedor(null);
                    }}
                  />
                </div>
              </div>

              <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:flex-wrap sm:items-end">
                {empresas.length > 1 ? (
                  <div className="w-full min-w-0 sm:min-w-[14rem] sm:flex-1">
                    <label className="erp-label">Empresa emitente</label>
                    <select
                      className="erp-select mt-1 w-full"
                      value={form.empresa_emitente_id ?? ''}
                      onChange={(e) =>
                        setForm((p) => ({
                          ...p,
                          empresa_emitente_id: e.target.value ? Number(e.target.value) : null,
                        }))
                      }
                    >
                      <option value="">Selecione matriz ou filial</option>
                      {empresas.map((em) => (
                        <option key={em.id} value={em.id}>
                          {em.razao_social}
                          {em.uf ? ` (${em.uf})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : empresas.length === 1 ? (
                  <p className="text-sm text-muted-foreground">
                    Emitente: <span className="font-medium text-foreground">{empresas[0].razao_social}</span>
                  </p>
                ) : null}
                {editing?.proposta_id ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="erp-badge-success">
                      Origem: Proposta {editing.proposta_numero || editing.proposta_id}
                    </span>
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                      onClick={() => navigate('/propostas')}
                    >
                      <ExternalLink className="h-3 w-3" />
                      Ver proposta
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 border-t border-border pt-3.5">
                <div>
                  <label className="erp-label">Condição de pagamento</label>
                  <input
                    className="erp-input mt-1"
                    placeholder="Ex.: 30, 45, 60"
                    value={form.condicao_pagamento_texto}
                    onChange={(e) => setForm((p) => ({ ...p, condicao_pagamento_texto: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    {condicaoPreview.erro ? condicaoPreview.erro : condicaoPreview.resumo}
                  </p>
                </div>
                <div>
                  <label className="erp-label">Vencimentos previstos</label>
                  <div className="mt-1 rounded-md border border-border bg-muted/10 p-3">
                    <CondicaoPagamentoResumo condicao={form.condicao_pagamento_texto} dataBaseIso={form.data} />
                  </div>
                </div>
                <div className="md:col-span-2">
                  <label className="erp-label">Prazo previsto de entrega</label>
                  <input
                    className="erp-input mt-1"
                    placeholder="Ex.: 30 dias após aprovação do pedido"
                    value={form.prazo_entrega_texto}
                    onChange={(e) => setForm((p) => ({ ...p, prazo_entrega_texto: e.target.value }))}
                  />
                  {editing?.proposta_id ? (
                    <p className="text-xs text-muted-foreground mt-1">
                      Herdado da proposta ao converter; pode ser ajustado conforme o compromisso operacional.
                    </p>
                  ) : null}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="itens" className="mt-0 space-y-3">
              {itensSomenteLeitura ? (
                <p className="text-sm text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                  {MSG_PEDIDO_FATURADO_ITENS}
                </p>
              ) : null}
              <div className="bg-muted/20 border border-border rounded-t-md p-3">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <h3 className="font-medium text-sm">Itens do pedido</h3>
                    <span className="inline-flex items-center justify-center rounded-md bg-background px-2 py-0.5 text-xs font-medium text-muted-foreground min-w-[2rem] text-center tabular-nums ring-1 ring-border/50">
                      {itens.length}
                    </span>
                  </div>
                  {!itensSomenteLeitura ? (
                    <button type="button" onClick={addItem} className="erp-btn-outline erp-btn-sm w-full sm:w-auto justify-center shrink-0">
                      <Plus className="h-3 w-3" /> Adicionar item
                    </button>
                  ) : null}
                </div>
              </div>
              <div className="space-y-3">
                {itens.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4 border border-dashed rounded-md">
                    {itensSomenteLeitura ? 'Nenhum item no pedido.' : 'Nenhum item. Clique em Adicionar item.'}
                  </p>
                ) : itensSomenteLeitura ? (
                  <div className="border border-border rounded-md overflow-x-auto bg-muted/5">
                    <table className="erp-table text-sm">
                      <thead>
                        <tr>
                          <th>Produto</th>
                          <th className="text-right">Qtd</th>
                          <th className="text-right">Fat.</th>
                          <th className="text-right">Pend.</th>
                          <th className="text-right">Preço</th>
                          <th className="text-right">Desc.</th>
                          <th className="text-right">Total</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {itens.map((item) => {
                          const qtd = numSafe(item.quantidade_negociada ?? item.quantidade);
                          const qFat = numSafe(item.quantidade_faturada);
                          const qPend = numSafe(item.quantidade_pendente ?? qtd - qFat);
                          const un = item.unidade_negociada || '';
                          return (
                            <tr key={item.id}>
                              <td className="max-w-[280px]">
                                <span className="font-medium block truncate" title={item.produto_nome}>
                                  {item.produto_nome || (item.produto_id ? 'Produto' : '—')}
                                </span>
                              </td>
                              <td className="text-right tabular-nums">{formatQuantidadeBR(qtd, un)}</td>
                              <td className="text-right tabular-nums">{formatQuantidadeBR(qFat, un)}</td>
                              <td className="text-right tabular-nums">{formatQuantidadeBR(qPend, un)}</td>
                              <td className="text-right tabular-nums">
                                {formatPrecoUnitarioBRL(item.preco_por_unidade_negociada ?? item.valor_unitario)}
                              </td>
                              <td className="text-right tabular-nums">{formatCurrencyBRL(itemDesconto(item))}</td>
                              <td className="text-right tabular-nums font-medium">
                                {formatCurrencyBRL(itemTotalLinha(item))}
                              </td>
                              <td>
                                <span className={statusItemBadge(item.status_item)}>
                                  {getStatusItemLabel(item.status_item)}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="border border-border rounded-md overflow-x-auto">
                    <table className="erp-table text-sm">
                      <thead>
                        <tr>
                          <th className="w-8" />
                          <th>Produto</th>
                          <th>Un.</th>
                          <th className="text-right">Qtd</th>
                          <th className="text-right">Fat.</th>
                          <th className="text-right">Pend.</th>
                          <th className="text-right">Preço</th>
                          <th className="text-right">Desc.</th>
                          <th className="text-right">Total</th>
                          <th>Status</th>
                          <th className="w-16" />
                        </tr>
                      </thead>
                      <tbody>
                        {itens.map((item, idx) => {
                          const expandido = expandedItemId === item.id;
                          const qtd = numSafe(item.quantidade_negociada ?? item.quantidade);
                          const qFat = numSafe(item.quantidade_faturada);
                          const qPend = numSafe(item.quantidade_pendente ?? qtd - qFat);
                          const readOnly = itemPedidoReadOnly(item, form.status);
                          const qtdEditavel = itemPedidoQuantidadeEditavel(item, form.status);
                          const podeExcluir = itemPedidoPodeExcluir(item, form.status);
                          const parcialFaturado =
                            (item.status_item || '').toUpperCase() === 'PARCIAL' && qFat > 0;
                          const patchQtd = (qtdVal: number): Partial<ItemPedido> => ({
                            quantidade_negociada: qtdVal,
                            quantidade: qtdVal,
                          });
                          return (
                            <Fragment key={item.id}>
                              <tr className="align-top">
                                <td>
                                  <button
                                    type="button"
                                    className="erp-btn-ghost erp-btn-sm p-1"
                                    onClick={() => setExpandedItemId(expandido ? null : item.id)}
                                    aria-label={expandido ? 'Recolher' : 'Editar item'}
                                  >
                                    {expandido ? (
                                      <ChevronDown className="h-4 w-4" />
                                    ) : (
                                      <ChevronRight className="h-4 w-4" />
                                    )}
                                  </button>
                                </td>
                                <td className="max-w-[220px]">
                                  <span className="font-medium block truncate">
                                    {item.produto_nome || (item.produto_id ? 'Produto' : '—')}
                                  </span>
                                </td>
                                <td>{(item.unidade_negociada || '—').toUpperCase()}</td>
                                <td className="text-right tabular-nums">
                                  <QuantityDisplay value={qtd} unidade={item.unidade_negociada} />
                                </td>
                                <td className="text-right tabular-nums">
                                  <QuantityDisplay value={qFat} unidade={item.unidade_negociada} />
                                </td>
                                <td className="text-right tabular-nums">
                                  <QuantityDisplay value={qPend} unidade={item.unidade_negociada} />
                                </td>
                                <td className="text-right tabular-nums">
                                  <UnitPriceDisplay value={item.preco_por_unidade_negociada ?? item.valor_unitario} />
                                </td>
                                <td className="text-right tabular-nums">
                                  <MoneyDisplay value={itemDesconto(item)} />
                                </td>
                                <td className="text-right tabular-nums font-medium">
                                  <MoneyDisplay value={itemTotalLinha(item)} />
                                </td>
                                <td>
                                  <span className={statusItemBadge(item.status_item)}>
                                    {getStatusItemLabel(item.status_item)}
                                  </span>
                                </td>
                                <td>
                                  {podeExcluir ? (
                                    <button
                                      type="button"
                                      onClick={() => removeItem(item.id)}
                                      className="erp-btn-ghost erp-btn-sm text-destructive"
                                    >
                                      <X className="h-4 w-4" />
                                    </button>
                                  ) : null}
                                </td>
                              </tr>
                              {expandido ? (
                                <tr>
                                  <td colSpan={11} className="bg-muted/10 p-4">
                                    <div className="space-y-3 max-w-full">
                                      {parcialFaturado ? (
                                        <p className="text-xs text-amber-800 dark:text-amber-200 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1">
                                          Item parcialmente faturado: quantidade mínima{' '}
                                          {formatQuantidadeBR(qFat, item.unidade_negociada)}; produto e preço
                                          bloqueados.
                                        </p>
                                      ) : null}
                                      <div>
                                        <label className="text-xs text-muted-foreground">Produto</label>
                                        {readOnly ? (
                                          <p className="erp-input mt-1 bg-muted/30 text-sm">
                                            {item.produto_nome || (item.produto_id ? `Produto #${item.produto_id}` : '—')}
                                          </p>
                                        ) : (
                                          <ProdutoComercialField
                                            valueId={item.produto_id || null}
                                            selectedProduto={
                                              item.produto_id ? produtoCache.get(item.produto_id) ?? null : null
                                            }
                                            onSelect={(pr) => {
                                              mergeProdutoCache(pr);
                                              const unidades = unidadesNegociacaoProduto(pr);
                                              const patch = {
                                                produto_id: pr.id,
                                                produto_nome: pr.descricao,
                                                unidade_negociada: unidades[0] || item.unidade_negociada || 'PC',
                                              };
                                              updateItem(idx, patch);
                                              void aplicarConversao(idx, patch);
                                            }}
                                            onClear={() => updateItem(idx, { produto_id: 0, produto_nome: '' })}
                                          />
                                        )}
                                      </div>
                                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                                        <div>
                                          <label className="text-xs text-muted-foreground">Unidade</label>
                                          <UnitSelect
                                            value={item.unidade_negociada || ''}
                                            disabled={readOnly}
                                            options={(() => {
                                              const p = item.produto_id ? produtoCache.get(item.produto_id) : undefined;
                                              return p ? unidadesNegociacaoProduto(p) : todasUnidadesPadrao();
                                            })()}
                                            onChange={(value) => {
                                              const patch = { unidade_negociada: value };
                                              updateItem(idx, patch);
                                              void aplicarConversao(idx, patch);
                                            }}
                                          />
                                        </div>
                                        <div>
                                          <label className="text-xs text-muted-foreground">Quantidade comercial</label>
                                          <QuantityInput
                                            value={Number(inputNumberValue(item.quantidade_negociada ?? item.quantidade, 1))}
                                            min={qFat > 0 ? qFat : 0.001}
                                            readOnly={!qtdEditavel}
                                            onChange={(val) => {
                                              updateItem(idx, patchQtd(val));
                                              void aplicarConversao(idx, patchQtd(val));
                                            }}
                                          />
                                        </div>
                                        <div>
                                          <label className="text-xs text-muted-foreground">
                                            {labelPrecoPorUnidade(item.unidade_negociada)}
                                          </label>
                                          <UnitPriceInput
                                            value={item.preco_por_unidade_negociada ?? item.valor_unitario}
                                            readOnly={readOnly}
                                            onChange={(value) => updateItem(idx, { preco_por_unidade_negociada: value })}
                                          />
                                        </div>
                                        <div>
                                          <label className="text-xs text-muted-foreground">Desconto (R$)</label>
                                          <DiscountInput
                                            value={itemDesconto(item)}
                                            readOnly={readOnly}
                                            onChange={(v) => {
                                              updateItem(idx, {
                                                desconto_valor: v,
                                                ...({ desconto: v } as Partial<ItemPedido>),
                                              });
                                            }}
                                          />
                                        </div>
                                        <div>
                                          <label className="text-xs text-muted-foreground">Total linha</label>
                                          <ReadonlyCalculatedField value={formatCurrencyBRL(itemTotalLinha(item))} />
                                        </div>
                                      </div>
                                      <p className="text-xs text-muted-foreground">{previewConversaoItem(item)}</p>
                                      <details className="rounded-md border border-border bg-muted/10 text-xs">
                                        <summary className="cursor-pointer px-3 py-2 font-medium text-muted-foreground select-none">
                                          Conversão dimensional e preços equivalentes
                                        </summary>
                                        <div className="px-3 pb-2 text-muted-foreground">
                                          {equivalentesPreco(item).length
                                            ? equivalentesPreco(item).join(' · ')
                                            : 'Sem equivalentes calculados.'}
                                        </div>
                                      </details>
                                      <details className="rounded-md border border-border bg-muted/10 text-xs">
                                        <summary className="cursor-pointer px-3 py-2 font-medium text-muted-foreground select-none">
                                          Impostos e adicionais (fiscal)
                                        </summary>
                                        <ItemComercialMetricasGrid className="p-3 pt-0">
                                          <div>
                                            <label className="text-xs text-muted-foreground">IPI (R$)</label>
                                            <input
                                              type="number"
                                              className="erp-input h-8 text-sm w-full"
                                              value={numSafe(item.ipi_valor)}
                                              onChange={(e) => updateItem(idx, { ipi_valor: +e.target.value })}
                                            />
                                          </div>
                                          <div>
                                            <label className="text-xs text-muted-foreground">ICMS ST (R$)</label>
                                            <input
                                              type="number"
                                              className="erp-input h-8 text-sm w-full"
                                              value={numSafe(item.icms_st_valor)}
                                              onChange={(e) => updateItem(idx, { icms_st_valor: +e.target.value })}
                                            />
                                          </div>
                                          <div>
                                            <label className="text-xs text-muted-foreground">Frete (R$)</label>
                                            <input
                                              type="number"
                                              className="erp-input h-8 text-sm w-full"
                                              value={numSafe(item.frete_valor)}
                                              onChange={(e) => updateItem(idx, { frete_valor: +e.target.value })}
                                            />
                                          </div>
                                        </ItemComercialMetricasGrid>
                                      </details>
                                    </div>
                                  </td>
                                </tr>
                              ) : null}
                            </Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-1.5 rounded-b-md border border-t-0 border-border bg-muted/15 px-3.5 py-2">
                  <div className="text-xs text-muted-foreground sm:text-left">
                    Quantidade negociada:{' '}
                    <span className="font-medium tabular-nums text-foreground/85">
                      {formatQuantidadeBR(
                        itens.reduce((acc, it) => acc + Number(it.quantidade_negociada ?? it.quantidade ?? 0), 0),
                        'UN',
                      )}
                    </span>
                  </div>
                  <div className="text-right text-sm font-medium tabular-nums text-foreground/85">
                    Subtotal itens: {formatCurrencyBRL(total)}
                  </div>
                </div>
              </div>
            </TabsContent>

            {pedidoId ? (
              <TabsContent value="faturamento" className="mt-0 space-y-3">
                <PedidoFaturamentoPanel
                  embedded
                  pedidoId={pedidoId}
                  itens={itens}
                  onAtualizado={onFaturamentoAtualizado}
                />
              </TabsContent>
            ) : null}

            {pedidoId ? (
              <TabsContent value="atendimento" className="mt-0 space-y-3">
                {alertaAtendimentoFaturado ? (
                  <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                    {MSG_PEDIDO_FATURADO_SEM_ATENDIMENTO}
                  </p>
                ) : null}
                <AlocacaoAtendimentoGerenciarPanel
                  pedidoVendaId={pedidoId}
                  itens={itens}
                  resumoInicial={editing?.resumo_atendimento_operacional}
                  onResumoAtualizado={onAtendimentoResumoAtualizado}
                />
              </TabsContent>
            ) : null}

            {pedidoId ? (
              <TabsContent value="fiscal" className="mt-0 space-y-4">
                <p className="text-xs text-muted-foreground">
                  Detalhes fiscais por faturamento. DANFE e XML ficam nesta aba; o PDF do pedido de venda está no
                  rodapé da página.
                </p>
                {faturamentoLoading ? (
                  <p className="text-sm text-muted-foreground">Carregando…</p>
                ) : (faturamentoResumo?.historico_nfe_saida ?? []).length === 0 &&
                  (faturamentoResumo?.faturamentos_nfe ?? []).length === 0 ? (
                  <p className="text-sm text-muted-foreground py-6 text-center border border-dashed rounded-md">
                    Nenhuma NF-e vinculada a este pedido.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {(faturamentoResumo?.historico_nfe_saida ?? []).length > 0 ? (
                      <div className="rounded-md border border-border p-4 space-y-2">
                        <p className="text-sm font-medium">Histórico fiscal de NF-e</p>
                        <PedidoVendaNfeHistoricoList
                          historico={faturamentoResumo?.historico_nfe_saida ?? []}
                          compacto
                        />
                      </div>
                    ) : null}
                    {(faturamentoResumo?.faturamentos_nfe ?? []).map((f) => {
                      const inconsistencia = mensagemNfeFaturamentoInconsistencia(f);
                      const sefazLabel = getNfeEmissaoSefazLabel(f.nfe_status_emissao_sefaz, f.nfe_saida_status);
                      const casoNfe = classificarNfeResumoPedido(f);
                      return (
                        <div key={f.faturamento_id} className="rounded-md border border-border p-4 space-y-3">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <div className="font-medium text-sm">
                                {f.numero_faturamento || `Faturamento #${f.faturamento_id}`}
                              </div>
                              <div className="text-xs text-muted-foreground mt-0.5">
                                Status faturamento: {getFaturamentoStatusLabel(f.status)}
                              </div>
                              <p className="text-[10px] text-muted-foreground/80">
                                Código interno: {f.status}
                              </p>
                            </div>
                            <StatusBadge status={tokenStatusComercialPedido(faturamentoResumo?.status)} />
                          </div>
                          {inconsistencia ? (
                            <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md bg-amber-500/10 px-2 py-1.5 border border-amber-500/20">
                              {inconsistencia}
                            </p>
                          ) : null}
                          {f.nfe_saida_id ? (
                            <>
                              <div className="space-y-1">
                                <p className="text-sm font-medium">{tituloResumoNfePedido(f)}</p>
                                <div className="flex flex-wrap gap-1.5">
                                  {getNFeFiscalBadgeTokens(f).map((tok) => (
                                    <StatusBadge key={tok} status={tok} />
                                  ))}
                                </div>
                                {casoNfe === 'cancelada' ? (
                                  <p className="text-xs text-destructive/90 rounded-md bg-destructive/5 px-2 py-1.5 border border-destructive/20">
                                    NF-e cancelada na SEFAZ — não representa faturamento fiscal válido.
                                    {f.nfe_motivo_cancelamento ? ` Motivo: ${f.nfe_motivo_cancelamento}` : ''}
                                  </p>
                                ) : null}
                                <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-3 gap-y-1 text-xs text-muted-foreground pt-1">
                                  {f.nfe_numero_fiscal ? (
                                    <>
                                      <dt>Número fiscal</dt>
                                      <dd className="text-foreground">{f.nfe_numero_fiscal}</dd>
                                    </>
                                  ) : null}
                                  {f.nfe_serie_fiscal ? (
                                    <>
                                      <dt>Série</dt>
                                      <dd className="text-foreground">{f.nfe_serie_fiscal}</dd>
                                    </>
                                  ) : null}
                                  {sefazLabel ? (
                                    <>
                                      <dt>Status fiscal</dt>
                                      <dd className="text-foreground">{sefazLabel}</dd>
                                    </>
                                  ) : null}
                                  {f.nfe_cstat ? (
                                    <>
                                      <dt>cStat</dt>
                                      <dd className="text-foreground">{f.nfe_cstat}</dd>
                                    </>
                                  ) : null}
                                  <dt>Ambiente</dt>
                                  <dd className="text-foreground">
                                    {f.nfe_status_emissao_sefaz === 'AUTORIZADA_HOMOLOGACAO'
                                      ? 'Homologação'
                                      : 'Conferência / produção futura'}
                                  </dd>
                                </dl>
                                {referenciaInternaNfe(f) ? (
                                  <p className="text-[10px] text-muted-foreground">
                                    Referência interna: {referenciaInternaNfe(f)}
                                  </p>
                                ) : null}
                              </div>
                              <PedidoVendaFiscalNfeAcoes
                                nfeSaidaId={f.nfe_saida_id}
                                nfeStatusEmissaoSefaz={f.nfe_status_emissao_sefaz}
                                nfeSaidaStatus={f.nfe_saida_status}
                              />
                              {(f.duplicatas_nfe?.length ?? 0) > 0 ? (
                                <div className="rounded-md border border-border p-3 space-y-2">
                                  <p className="text-sm font-medium">Duplicatas da NF-e</p>
                                  <p className="text-xs text-muted-foreground">
                                    As duplicatas representam a cobrança informada na NF-e. Nesta fase, não
                                    geram contas a receber automaticamente.
                                  </p>
                                  <div className="overflow-x-auto">
                                    <table className="w-full text-xs">
                                      <thead>
                                        <tr className="text-muted-foreground border-b border-border">
                                          <th className="text-left py-1 pr-3 font-medium">Número</th>
                                          <th className="text-left py-1 pr-3 font-medium">Vencimento</th>
                                          <th className="text-right py-1 font-medium">Valor</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {f.duplicatas_nfe!.map((dup) => (
                                          <tr key={dup.numero} className="border-b border-border/60 last:border-0">
                                            <td className="py-1 pr-3 text-foreground">{dup.numero}</td>
                                            <td className="py-1 pr-3 text-foreground">
                                              {dup.vencimento_formatado}
                                            </td>
                                            <td className="py-1 text-right text-foreground">
                                              {dup.valor_formatado}
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              ) : null}
                            </>
                          ) : (
                            <p className="text-xs text-muted-foreground">
                              {inconsistencia
                                ? null
                                : 'NF-e ainda não gerada para este faturamento.'}
                            </p>
                          )}
                          {!f.nfe_saida_id && f.status === 'PRONTO_PARA_NFE' ? (
                            <button
                              type="button"
                              className="erp-btn-outline erp-btn-sm"
                              onClick={() => setModalTab('faturamento')}
                            >
                              Ir para Faturamento
                            </button>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                )}
              </TabsContent>
            ) : null}

            <TabsContent value="historico" className={`mt-0 ${pedidoId ? 'space-y-4' : 'space-y-3.5'} pb-2.5`}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                <div>
                  <label className="erp-label">Observações comerciais</label>
                  <textarea
                    className="erp-input mt-1 w-full min-h-[104px]"
                    value={form.observacoes_comerciais}
                    onChange={(e) => setForm((p) => ({ ...p, observacoes_comerciais: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="erp-label">Observações internas</label>
                  <textarea
                    className="erp-input mt-1 w-full min-h-[104px]"
                    value={form.observacoes_internas}
                    onChange={(e) => setForm((p) => ({ ...p, observacoes_internas: e.target.value }))}
                  />
                </div>
              </div>
              {editing?.proposta_id ? (
                <div className="rounded-md border border-border p-3 text-sm">
                  <span className="font-medium">Origem: </span>
                  Proposta {editing.proposta_numero || editing.proposta_id}
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm ml-3 inline-flex items-center gap-1"
                    onClick={() => navigate('/propostas')}
                  >
                    <ExternalLink className="h-3 w-3" />
                    Abrir proposta
                  </button>
                </div>
              ) : null}
              {editing?.data ? (
                <p className="text-xs text-muted-foreground">Data do pedido: {formatDateBr(editing.data)}</p>
              ) : null}

              <details className="rounded-md border border-border bg-muted/10">
                <summary className="cursor-pointer px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground select-none">
                  Referências comerciais (frete e custo de compra)
                </summary>
                <div className="p-3 pt-0 space-y-3">
                  {referenciaFrete ? (
                    <div className="text-sm">
                      <p className="text-xs font-medium text-muted-foreground mb-1">Frete observado</p>
                      <p className="text-xs">{referenciaFrete.mensagem}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">Sem referência de frete para o período.</p>
                  )}
                  {referenciaCustoCompra ? (
                    <div className="text-sm">
                      <p className="text-xs font-medium text-muted-foreground mb-1">Custo de compra observado</p>
                      <p className="text-xs">{referenciaCustoCompra.mensagem}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">Sem referência de custo de compra.</p>
                  )}
                </div>
              </details>
            </TabsContent>
          </div>
        </Tabs>

        <div className="rounded-lg border border-border bg-card px-4 py-3 shadow-sm sm:px-4 sm:py-3.5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-8">
              <div>
                <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Itens</span>
                <span className="font-medium tabular-nums text-sm">{itens.length} item(ns)</span>
              </div>
              <div className="text-left">
                <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">Total do pedido</span>
                <span className="font-bold tabular-nums text-2xl tracking-tight">
                  {formatCurrencyBRL(numSafe(total))}
                </span>
              </div>
            </div>
            <div className="flex w-full flex-col-reverse gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:justify-end">
              {footerConfig.primaryKind === 'save' ? (
                <button type="button" onClick={onClose} className="erp-btn-outline w-full sm:w-auto">
                  Cancelar
                </button>
              ) : null}
              {footerConfig.showPedidoPdf ? (
                <>
                  <button
                    type="button"
                    className="erp-btn-outline inline-flex w-full items-center gap-1 sm:w-auto"
                    onClick={() => void handleVisualizarPdf()}
                  >
                    <FileDown className="h-4 w-4" />
                    Ver PDF do pedido
                  </button>
                  <button
                    type="button"
                    className="erp-btn-outline inline-flex w-full items-center gap-1 sm:w-auto"
                    onClick={() => void handleBaixarPdf()}
                  >
                    <Download className="h-4 w-4" />
                    Baixar PDF do pedido
                  </button>
                </>
              ) : (
                <span className="text-xs text-muted-foreground self-center">Salve antes de gerar PDF.</span>
              )}
              <button
                type="button"
                onClick={footerConfig.primaryKind === 'close' ? onClose : handleSave}
                className="erp-btn-primary w-full sm:w-auto"
              >
                {footerConfig.primaryLabel}
              </button>
            </div>
          </div>
        </div>
      </div>

      <MotivoAcaoDestrutivaModal
        open={estornoModal != null}
        onOpenChange={(open) => {
          if (!open) setEstornoModal(null);
        }}
        title="Estornar faturamento"
        description="Este faturamento ainda não possui NF-e autorizada. O estorno é interno e reverte as quantidades faturadas do pedido."
        avisoSefaz="Nenhum evento será enviado à SEFAZ."
        detalhes={
          estornoModal ? (
            <p className="text-sm text-muted-foreground">
              Faturamento: <strong>{estornoModal.label}</strong>
            </p>
          ) : null
        }
        confirmLabel="Estornar faturamento e reabrir pedido"
        loading={estornoLoading}
        onConfirm={async (motivo) => {
          if (!pedidoId || !estornoModal) return;
          setEstornoLoading(true);
          try {
            const r = await pedidosVendaService.estornarFaturamento(pedidoId, estornoModal.faturamentoId, {
              motivo,
            });
            const msg = r.mensagens?.[0] || 'Faturamento estornado. Pedido reaberto para edição.';
            if (r.ja_estava_estornado) {
              toast.info(msg);
            } else {
              toast.success(msg);
            }
            setEstornoModal(null);
            const novo = await pedidosVendaService.resumoFaturamento(pedidoId);
            setFaturamentoResumo(novo);
            await onFaturamentoAtualizado();
          } catch (e) {
            toast.error(apiErrorMessage(e, { fallback: 'Não foi possível estornar o faturamento.' }));
            throw e;
          } finally {
            setEstornoLoading(false);
          }
        }}
      />
    </Fragment>
  );
}
