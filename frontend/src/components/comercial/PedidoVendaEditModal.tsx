import { Fragment, useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight, Download, ExternalLink, FileDown, Plus, RotateCcw, X } from 'lucide-react';
import { toast } from 'sonner';
import { MSG_PDF_PEDIDO_SEM_ID, resolvePedidoVendaId } from '@/lib/pedidoVendaId';
import { MotivoAcaoDestrutivaModal } from '@/components/comercial/MotivoAcaoDestrutivaModal';
import { pedidosVendaService } from '@/services/api/comercial';
import { apiErrorMessage } from '@/services/api/config';
import { Modal } from '@/components/Modal';
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
  MoneyInput,
  QuantityDisplay,
  QuantityInput,
  ReadonlyCalculatedField,
  UnitSelect,
} from '@/components/comercial/fields';
import { VendedorComercialField } from '@/components/comercial/VendedorComercialField';
import { ItemComercialMetricasGrid } from '@/components/comercial/ItemComercialMetricasGrid';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatDateBr } from '@/lib/dateBr';
import { formatCurrencyBRL, formatQuantidadeBR } from '@/lib/formatBr';
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
import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';

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

export type PedidoVendaEditModalProps = {
  isOpen: boolean;
  onClose: () => void;
  editing: PedidoVenda | null;
  form: PedidoForm;
  setForm: Dispatch<SetStateAction<PedidoForm>>;
  itens: ItemPedido[];
  setItens: Dispatch<SetStateAction<ItemPedido[]>>;
  empresas: Empresa[];
  selectedCliente: Cliente | null;
  selectedVendedor: Vendedor | null;
  selectedColaboradorVendedor: Colaborador | null;
  setSelectedCliente: (c: Cliente | null) => void;
  setSelectedVendedor: (v: Vendedor | null) => void;
  setSelectedColaboradorVendedor: (c: Colaborador | null) => void;
  produtoCache: Map<number, Produto>;
  mergeProdutoCache: (p: Produto) => void;
  updateItem: (idx: number, patch: Partial<ItemPedido>) => void;
  aplicarConversao: (idx: number, patch?: Partial<ItemPedido>) => void | Promise<void>;
  addItem: () => void;
  removeItem: (id: number) => void;
  total: number;
  statusOpcoesPedido: { value: string; label: string }[];
  onSave: () => void;
  onFaturamentoAtualizado: () => void | Promise<void>;
  onAtendimentoResumoAtualizado?: (resumo: ResumoAtendimentoOperacional | null) => void;
  faturamentoRefreshKey?: number;
  referenciaFrete: RefFrete | null;
  referenciaCustoCompra: RefCusto | null;
  saveError?: string | null;
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

export function PedidoVendaEditModal({
  isOpen,
  onClose,
  editing,
  form,
  setForm,
  itens,
  empresas,
  selectedCliente,
  selectedVendedor,
  selectedColaboradorVendedor,
  setSelectedCliente,
  setSelectedVendedor,
  setSelectedColaboradorVendedor,
  produtoCache,
  mergeProdutoCache,
  updateItem,
  aplicarConversao,
  addItem,
  removeItem,
  total,
  statusOpcoesPedido,
  referenciaFrete,
  referenciaCustoCompra,
  saveError,
  onSave,
  onFaturamentoAtualizado,
  onAtendimentoResumoAtualizado,
  faturamentoRefreshKey = 0,
}: PedidoVendaEditModalProps) {
  const navigate = useNavigate();
  const [modalTab, setModalTab] = useState('resumo');
  const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
  const [faturamentoResumo, setFaturamentoResumo] = useState<ResumoFaturamentoPedido | null>(null);
  const [faturamentoLoading, setFaturamentoLoading] = useState(false);
  const [estornoModal, setEstornoModal] = useState<{ faturamentoId: number; label: string } | null>(null);
  const [estornoLoading, setEstornoLoading] = useState(false);

  const condicaoPreview = previewCondicaoPagamento(form.condicao_pagamento_texto ?? '', form.data ?? '');
  const pedidoId = editing?.id;
  const clienteNome = selectedCliente?.razao_social || editing?.cliente_nome || '—';
  const vendedorNome =
    selectedVendedor?.nome || editing?.vendedor_nome || editing?.vendedor || '—';
  const numeroExib = form.numero || editing?.numero || (editing ? '—' : 'Novo');
  const statusExib = form.status || editing?.status || 'ABERTO';

  useEffect(() => {
    if (!isOpen) {
      setModalTab('resumo');
      setExpandedItemId(null);
      setFaturamentoResumo(null);
      return;
    }
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
  }, [isOpen, pedidoId, faturamentoRefreshKey]);

  const handleAtendimentoResumoAtualizado = useCallback(
    (resumo: ResumoAtendimentoOperacional | null) => {
      onAtendimentoResumoAtualizado?.(resumo);
    },
    [onAtendimentoResumoAtualizado],
  );

  const nfesVinculadas = (faturamentoResumo?.faturamentos_nfe ?? []).filter((f) => f.nfe_saida_id);
  const linhaEstornoResumo = (faturamentoResumo?.faturamentos_nfe ?? []).find(
    (f) => f.pode_estornar_pre_autorizacao !== false,
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
      console.error('[PedidoVendaEditModal] Visualizar PDF: id ausente', editing);
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
      console.error('[PedidoVendaEditModal] Baixar PDF: id ausente', editing);
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

  const footer = (
    <div className="flex flex-wrap justify-end gap-2 p-4">
      {footerConfig.primaryKind === 'save' ? (
        <button type="button" onClick={onClose} className="erp-btn-outline">
          Cancelar
        </button>
      ) : null}
      {footerConfig.showPedidoPdf ? (
        <>
          <button
            type="button"
            className="erp-btn-outline inline-flex items-center gap-1"
            onClick={() => void handleVisualizarPdf()}
          >
            <FileDown className="h-4 w-4" />
            Ver PDF do pedido
          </button>
          <button
            type="button"
            className="erp-btn-outline inline-flex items-center gap-1"
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
        onClick={footerConfig.primaryKind === 'close' ? onClose : onSave}
        className="erp-btn-primary"
      >
        {footerConfig.primaryLabel}
      </button>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={editing ? 'Pedido de Venda' : 'Novo Pedido de Venda'}
      size="2xl"
      footer={footer}
    >
      <div className="rounded-lg border border-border bg-muted/15 px-4 py-3 mb-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
        <div>
          <span className="text-xs text-muted-foreground block">Pedido</span>
          <span className="font-semibold text-foreground">{numeroExib}</span>
        </div>
        <div>
          <span className="text-xs text-muted-foreground block">Cliente</span>
          <span className="font-medium truncate block" title={clienteNome}>
            {clienteNome}
          </span>
        </div>
        <div>
          <span className="text-xs text-muted-foreground block">Status</span>
          <StatusBadge status={tokenStatusComercialPedido(statusExib)} className="mt-0.5" />
        </div>
        <div>
          <span className="text-xs text-muted-foreground block">Total / Faturamento</span>
          <span className="font-semibold tabular-nums">
            {formatCurrencyBRL(numSafe(total))}
            <span className="text-muted-foreground font-normal"> · {faturamentoLabel}</span>
          </span>
        </div>
      </div>
      {saveError ? (
        <p className="mb-3 text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2">
          {saveError}
        </p>
      ) : null}

      <Tabs value={modalTab} onValueChange={setModalTab} className="flex flex-col min-h-0">
        <TabsList className="w-full flex flex-wrap h-auto gap-1 mb-2">
          <TabsTrigger value="resumo">Resumo</TabsTrigger>
          <TabsTrigger value="itens">Itens</TabsTrigger>
          {pedidoId ? <TabsTrigger value="faturamento">Faturamento</TabsTrigger> : null}
          {pedidoId ? <TabsTrigger value="atendimento">Atendimento operacional</TabsTrigger> : null}
          {pedidoId ? <TabsTrigger value="fiscal">NF-e / Fiscal</TabsTrigger> : null}
          <TabsTrigger value="historico">Observações / Histórico</TabsTrigger>
        </TabsList>

        <TabsContent value="resumo" className="max-h-[min(58vh,520px)] overflow-y-auto pr-1 space-y-4 mt-0">
          {pedidoId && faturamentoLoading ? (
            <p className="text-xs text-muted-foreground">Carregando resumo de faturamento…</p>
          ) : null}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Número', value: numeroExib },
              { label: 'Status', value: labelStatusPedidoVenda(statusExib) },
              { label: 'Cliente', value: clienteNome },
              { label: 'Vendedor', value: vendedorNome },
              {
                label: 'Total pedido',
                value: formatCurrencyBRL(numSafe(total)),
              },
              {
                label: 'Valor faturado',
                value: valorFaturadoCard != null ? formatCurrencyBRL(valorFaturadoCard) : '—',
              },
              {
                label: 'Valor pendente',
                value: valorPendenteCard != null ? formatCurrencyBRL(valorPendenteCard) : '—',
              },
              { label: 'Faturamento', value: faturamentoLabel },
            ].map((c) => (
              <div key={c.label} className="rounded-md border border-border bg-card px-3 py-2">
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{c.label}</div>
                <div className="text-sm font-medium mt-0.5 truncate" title={String(c.value)}>
                  {c.value}
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-md border border-border bg-card px-3 py-2 space-y-2">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">NF-e vinculada</div>
            {semNfeGerada && !faturamentoLoading ? (
              <p className="text-sm text-muted-foreground">Nenhuma NF-e gerada</p>
            ) : null}
            {nfesVinculadas.map((f) => {
              const refInt = referenciaInternaNfe(f);
              return (
                <div key={f.faturamento_id} className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{tituloResumoNfePedido(f)}</span>
                    {getNFeFiscalBadgeTokens(f).map((tok) => (
                      <StatusBadge key={tok} status={tok} />
                    ))}
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                      onClick={() => navigate(`/nfe-saida?nfe=${f.nfe_saida_id}`)}
                    >
                      <ExternalLink className="h-3 w-3" />
                      Abrir NF-e
                    </button>
                    {f.pode_estornar_pre_autorizacao !== false ? (
                      <button
                        type="button"
                        className="erp-btn-outline erp-btn-sm text-destructive border-destructive/40 inline-flex items-center gap-1"
                        disabled={estornoLoading}
                        onClick={() =>
                          setEstornoModal({
                            faturamentoId: f.faturamento_id,
                            label: linhaFaturamentoNfeAmigavel(f),
                          })
                        }
                      >
                        <RotateCcw className="h-3 w-3" aria-hidden />
                        Estornar faturamento
                      </button>
                    ) : null}
                  </div>
                  {refInt ? (
                    <p className="text-[10px] text-muted-foreground">Referência interna: {refInt}</p>
                  ) : null}
                </div>
              );
            })}
          </div>

          {linhaEstornoResumo ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 flex flex-wrap gap-2 items-center justify-between">
              <p className="text-xs text-muted-foreground">
                NF-e ainda não autorizada — você pode estornar o faturamento e reabrir o pedido (sem SEFAZ).
              </p>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-destructive border-destructive/50 inline-flex items-center gap-1 shrink-0"
                disabled={estornoLoading}
                onClick={() =>
                  setEstornoModal({
                    faturamentoId: linhaEstornoResumo.faturamento_id,
                    label: linhaFaturamentoNfeAmigavel(linhaEstornoResumo),
                  })
                }
              >
                <RotateCcw className="h-3 w-3" aria-hidden />
                Estornar faturamento
              </button>
            </div>
          ) : null}

          {alertaAtendimentoFaturado ? (
            <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
              {MSG_PEDIDO_FATURADO_SEM_ATENDIMENTO}
            </p>
          ) : null}

          <AtendimentoOperacionalResumo resumo={editing?.resumo_atendimento_operacional} />

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 border-t border-border pt-4">
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

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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

          <div className="flex flex-wrap gap-3 items-end">
            {empresas.length > 1 ? (
              <div className="flex-1 min-w-[14rem]">
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

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-border pt-4">
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

        <TabsContent value="itens" className="max-h-[min(58vh,520px)] overflow-y-auto pr-1 mt-0 space-y-3">
          {itensSomenteLeitura ? (
            <p className="text-sm text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
              {MSG_PEDIDO_FATURADO_ITENS}
            </p>
          ) : null}
          <div className="flex justify-between items-center">
            <p className="text-sm text-muted-foreground">{itens.length} item(ns)</p>
            {!itensSomenteLeitura ? (
              <button type="button" onClick={addItem} className="erp-btn-outline erp-btn-sm">
                <Plus className="h-3 w-3" /> Adicionar item
              </button>
            ) : null}
          </div>

          {itens.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8 border border-dashed rounded-md">
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
                          {formatCurrencyBRL(item.preco_por_unidade_negociada ?? item.valor_unitario)}
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
                            <MoneyDisplay value={item.preco_por_unidade_negociada ?? item.valor_unitario} />
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
                                    <MoneyInput
                                      value={item.preco_por_unidade_negociada ?? item.valor_unitario}
                                      step="0.0001"
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
          <div className="text-right font-bold text-sm pt-2 border-t">
            Total: {formatCurrencyBRL(total)}
          </div>
        </TabsContent>

        {pedidoId ? (
          <TabsContent value="faturamento" className="max-h-[min(70vh,640px)] overflow-y-auto pr-1 mt-0 space-y-3">
            {alertaAtendimentoFaturado ? (
              <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                {MSG_ALERTA_FATURAMENTO_SEM_ATENDIMENTO}
              </p>
            ) : null}
            <PedidoFaturamentoPanel
              embedded
              pedidoId={pedidoId}
              itens={itens}
              onAtualizado={onFaturamentoAtualizado}
            />
          </TabsContent>
        ) : null}

        {pedidoId ? (
          <TabsContent value="atendimento" className="max-h-[min(58vh,520px)] overflow-y-auto pr-1 mt-0 space-y-3">
            {alertaAtendimentoFaturado ? (
              <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                {MSG_PEDIDO_FATURADO_SEM_ATENDIMENTO}
              </p>
            ) : null}
            <AlocacaoAtendimentoGerenciarPanel
              pedidoVendaId={pedidoId}
              itens={itens}
              resumoInicial={editing?.resumo_atendimento_operacional}
                onResumoAtualizado={handleAtendimentoResumoAtualizado}
            />
          </TabsContent>
        ) : null}

        {pedidoId ? (
          <TabsContent value="fiscal" className="max-h-[min(58vh,520px)] overflow-y-auto pr-1 mt-0 space-y-4">
            <p className="text-xs text-muted-foreground">
              Detalhes fiscais por faturamento. DANFE e XML ficam nesta aba; o PDF do pedido de venda está no rodapé da
              modal.
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

        <TabsContent value="historico" className="max-h-[min(58vh,520px)] overflow-y-auto pr-1 mt-0 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="erp-label">Observações comerciais</label>
              <textarea
                className="erp-input mt-1 w-full min-h-[88px]"
                value={form.observacoes_comerciais}
                onChange={(e) => setForm((p) => ({ ...p, observacoes_comerciais: e.target.value }))}
              />
            </div>
            <div>
              <label className="erp-label">Observações internas</label>
              <textarea
                className="erp-input mt-1 w-full min-h-[88px]"
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
      </Tabs>

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
            toast.success(r.mensagens?.[0] || 'Faturamento estornado. Pedido reaberto para edição.');
            setEstornoModal(null);
            const novo = await pedidosVendaService.resumoFaturamento(pedidoId);
            setFaturamentoResumo(novo);
            onFaturamentoAtualizado?.();
          } catch (e) {
            toast.error(apiErrorMessage(e, { fallback: 'Não foi possível estornar o faturamento.' }));
            throw e;
          } finally {
            setEstornoLoading(false);
          }
        }}
      />
    </Modal>
  );
}
