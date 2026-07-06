import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Modal } from '@/components/Modal';
import { PageHeader } from '@/components/PageHeader';
import { GerarContasPagarNfeEntradaModal } from '@/components/fiscal/GerarContasPagarNfeEntradaModal';
import { FornecedorEntradaAcoes } from '@/components/fiscal/FornecedorEntradaAcoes';
import { NFeEntradaFinanceiroAcoes } from '@/components/fiscal/NFeEntradaFinanceiroAcoes';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import {
  badgeClassStatusConferencia,
  badgeClassElegibilidadeEstoque,
  badgeClassStatusFiscalEntrada,
  divergenciasFiscaisResumo,
  labelAlertaResumoQuantitativo,
  labelElegibilidadeEstoque,
  labelDivergenciaConferencia,
  labelItemPedidoCompraOption,
  labelProdutoLinhaConferencia,
  labelStatusConferenciaItem,
  labelStatusConferenciaCabecalho,
  labelStatusFiscalEntrada,
  labelStatusQuantitativoPedido,
  labelStatusSaldoGlobalPedido,
  labelSugestaoItemPedidoCurta,
  NOTA_SALDO_CONFERENCIA_PEDIDO,
  SCORE_SUGESTAO_ITEM_PEDIDO_ALTO,
} from '@/lib/conferenciaNfeLabels';
import { aplicarStatusAutomaticoItem } from '@/lib/conferenciaNfeStatus';
import { prepararEstoqueErrorMessage } from '@/lib/conferenciaNfePreparar';
import {
  buildCriarRegraFiscalEntradaUrl,
  mensagemFiscalEntrada,
  resumoImpostosLinha,
  tituloMatchRegraFiscal,
} from '@/lib/regrasFiscaisEntradaHelpers';
import { apiErrorMessage } from '@/services/api/config';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import { pedidosCompraService } from '@/services/api/comercial';
import { produtosService } from '@/services/api/produtos';
import { normalizeOperationalInput } from '@/lib/textNormalize';
import {
  AVISO_EQUIVALENCIA_SEM_ESTOQUE,
  badgeConfiancaEquivalencia,
  formatMoedaBRL,
  labelTipoComposicao,
  labelTipoEquivalencia,
} from '@/lib/conferenciaEquivalencia';
import { AtenderVendasPendentesBlock } from '@/components/AtenderVendasPendentesBlock';
import {
  CorridaSplitEditor,
  criarSplitsIniciais,
  itemUsaSplitCorrida,
  mapItemPayloadCorrida,
  qtyAlvoItemConferencia,
} from '@/components/fiscal/CorridaSplitEditor';
import type {
  ItemConferenciaNFeEntrada,
  NFeEntradaConferencia,
  PedidoCompra,
  Produto,
  ResultadoAplicacaoEstoque,
} from '@/types';

export type NFeEntradaConferenciaPanelProps = {
  nfeHistoricaId: number;
  embedded?: boolean;
  onUpdated?: () => void;
  onClose?: () => void;
};

export function NFeEntradaConferenciaPanel({
  nfeHistoricaId,
  embedded = false,
  onUpdated,
  onClose,
}: NFeEntradaConferenciaPanelProps) {
  const navigate = useNavigate();
  const nfId = nfeHistoricaId;
  const [dados, setDados] = useState<NFeEntradaConferencia | null>(null);
  const [pedidos, setPedidos] = useState<PedidoCompra[]>([]);
  const [produtoCache, setProdutoCache] = useState<Map<number, Produto>>(() => new Map());
  const [erro, setErro] = useState('');
  const [avisoPedido, setAvisoPedido] = useState('');
  const [busy, setBusy] = useState(false);
  const [resumoAberto, setResumoAberto] = useState(true);
  const [resumoFiscalAberto, setResumoFiscalAberto] = useState(true);
  const [resumoElegibilidadeAberto, setResumoElegibilidadeAberto] = useState(true);
  const [equivalenciasAberto, setEquivalenciasAberto] = useState(true);
  const [eqBusy, setEqBusy] = useState(false);
  const [modalAplicarOpen, setModalAplicarOpen] = useState(false);
  const [previewAplicar, setPreviewAplicar] = useState<ResultadoAplicacaoEstoque | null>(null);
  const [confirmarAlertasAplicar, setConfirmarAlertasAplicar] = useState(false);
  const [obsAplicar, setObsAplicar] = useState('');
  const [modalAplicarErro, setModalAplicarErro] = useState('');
  const [gerarCpOpen, setGerarCpOpen] = useState(false);

  const produtosMap = produtoCache;
  const estoqueJaAplicado = Boolean(dados?.estoque_aplicado_em);
  const podeAplicarEstoque =
    dados &&
    !estoqueJaAplicado &&
    (dados.status === 'PREPARADA' || dados.status === 'CONFERIDA');

  const buscarProdutos = useCallback((term: string, limit?: number) => produtosService.search(term, limit ?? 40), []);

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
    setProdutoCache(cache);
  }, []);

  const pedidoSelecionado = useMemo(
    () => (dados?.pedido_compra_id ? pedidos.find((p) => p.id === dados.pedido_compra_id) : undefined),
    [dados?.pedido_compra_id, pedidos],
  );

  const load = async () => {
    if (!nfId) return;
    setErro('');
    setAvisoPedido('');
    const [conf, pcs] = await Promise.all([
      nfeEntradaConferenciaService.get(nfId),
      pedidosCompraService.getAll(),
    ]);
    setDados(conf);
    setPedidos(pcs);
    await hydrateProdutoCache(conf);
  };

  useEffect(() => {
    void load().catch((e) => setErro(apiErrorMessage(e)));
  }, [nfId]);

  const notifyUpdated = () => {
    onUpdated?.();
  };

  const updateItem = (itemId: number, patch: Partial<ItemConferenciaNFeEntrada>) => {
    if (!dados) return;
    setDados({
      ...dados,
      itens: dados.itens.map((it) => {
        if (it.id !== itemId) return it;
        const merged = { ...it, ...patch };
        if (patch.status === 'IGNORADO') {
          return merged;
        }
        if (Object.prototype.hasOwnProperty.call(patch, 'status')) {
          return merged;
        }
        return aplicarStatusAutomaticoItem(merged);
      }),
    });
  };

  const onChangePedidoCompra = (pedidoId: number | null) => {
    if (!dados) return;
    const tinhaVinculos = dados.itens.some((it) => it.item_pedido_compra_id);
    const pedidoMudou = pedidoId !== dados.pedido_compra_id;
    const itensAtualizados =
      pedidoMudou && tinhaVinculos
        ? dados.itens.map((it) => aplicarStatusAutomaticoItem({ ...it, item_pedido_compra_id: null }))
        : dados.itens.map((it) => aplicarStatusAutomaticoItem(it));
    setDados({
      ...dados,
      pedido_compra_id: pedidoId,
      itens: itensAtualizados,
      resumo_pedido: pedidoMudou ? undefined : dados.resumo_pedido,
    });
    if (pedidoMudou && tinhaVinculos) {
      setAvisoPedido(
        'O pedido de compra foi alterado. Os vínculos de itens do pedido nas linhas foram removidos; vincule novamente.',
      );
    } else {
      setAvisoPedido('');
    }
  };

  const salvar = async () => {
    if (!dados) return;
    setBusy(true);
    setErro('');
    try {
      const payload = {
        pedido_compra_id: dados.pedido_compra_id,
        data_entrada: dados.data_entrada || null,
        divergencias_aceitas: dados.divergencias_aceitas,
        observacao_divergencias: dados.observacao_divergencias,
        itens: dados.itens.map((it) => mapItemPayloadCorrida(it)),
      };
      const next = await nfeEntradaConferenciaService.salvar(nfId, payload);
      setDados(next);
      await hydrateProdutoCache(next);
      setAvisoPedido('');
      if (next.financeiro?.possui_pendencias_operacionais) {
        toast.success(
          'Conferência salva com pendências. Você ainda pode gerar contas a pagar, mas a conferência não foi finalizada e a aplicação de estoque permanece pendente.',
        );
      } else {
        toast.success('Conferência salva.');
      }
      notifyUpdated();
    } catch (e) {
      const msg = apiErrorMessage(e);
      setErro(msg);
      toast.error(msg.split('\n')[0] || 'Não foi possível salvar a conferência.');
    } finally {
      setBusy(false);
    }
  };

  const abrirModalAplicar = async () => {
    if (!nfId) return;
    if (!dados?.data_entrada) {
      setErro('Informe a data de entrada da NF-e antes de aplicar estoque físico.');
      return;
    }
    setModalAplicarOpen(true);
    setModalAplicarErro('');
    setConfirmarAlertasAplicar(false);
    setObsAplicar('');
    setBusy(true);
    try {
      const saved = await salvarSilencioso();
      if (saved) setDados(saved);
      const preview = await nfeEntradaConferenciaService.previewAplicarEstoque(nfId, false);
      setPreviewAplicar(preview);
    } catch (e) {
      setModalAplicarErro(apiErrorMessage(e));
      setPreviewAplicar(null);
    } finally {
      setBusy(false);
    }
  };

  const salvarSilencioso = async (): Promise<NFeEntradaConferencia | null> => {
    if (!dados || !nfId) return null;
    const payload = {
      pedido_compra_id: dados.pedido_compra_id,
      data_entrada: dados.data_entrada || null,
      divergencias_aceitas: dados.divergencias_aceitas,
      observacao_divergencias: dados.observacao_divergencias,
      itens: dados.itens.map((it) => ({
        id: it.id,
        produto_id: it.produto_id ?? null,
        item_pedido_compra_id: it.item_pedido_compra_id ?? null,
        corrida: it.corrida ?? '',
        lote: it.lote ?? '',
        status: it.status,
        motivo_ignorado: it.motivo_ignorado ?? '',
        observacao: it.observacao ?? '',
      })),
    };
    return nfeEntradaConferenciaService.salvar(nfId, payload);
  };

  const confirmarAplicarEstoque = async () => {
    if (!nfId) return;
    setBusy(true);
    setModalAplicarErro('');
    try {
      const res = await nfeEntradaConferenciaService.aplicarEstoque(nfId, {
        confirmar_alertas: confirmarAlertasAplicar,
        observacao: obsAplicar,
        data_entrada: dados?.data_entrada || undefined,
      });
      if (res.conferencia) {
        setDados(res.conferencia);
        await hydrateProdutoCache(res.conferencia);
      } else {
        await load();
      }
      setModalAplicarOpen(false);
      setPreviewAplicar(null);
      const baixa = res.pedido_compra_baixa;
      if (baixa?.aplicado) {
        toast.success(baixa.mensagem || 'Pedido de compra baixado.');
      } else if (baixa?.ja_baixado) {
        toast.info(baixa.mensagem || 'Pedido de compra já estava baixado para esta NF-e.');
      }
      notifyUpdated();
    } catch (e: unknown) {
      const err = e as { response?: { data?: ResultadoAplicacaoEstoque & { detail?: string } } };
      const data = err.response?.data;
      if (data?.pendencias || data?.alertas) {
        setPreviewAplicar(data);
        setModalAplicarErro(data.detail || 'Não foi possível aplicar estoque físico.');
      } else {
        setModalAplicarErro(apiErrorMessage(e));
      }
    } finally {
      setBusy(false);
    }
  };

  const preparar = async () => {
    if (!dados) return;
    if (!dados.data_entrada) {
      setErro('Informe a data de entrada da NF-e antes de finalizar a conferência.');
      return;
    }
    setBusy(true);
    setErro('');
    try {
      const payload = {
        pedido_compra_id: dados.pedido_compra_id,
        data_entrada: dados.data_entrada || null,
        divergencias_aceitas: dados.divergencias_aceitas,
        observacao_divergencias: dados.observacao_divergencias,
        itens: dados.itens.map((it) => mapItemPayloadCorrida(it)),
      };
      const saved = await nfeEntradaConferenciaService.salvar(nfId, payload);
      setDados(saved);
      await hydrateProdutoCache(saved);
      const next = await nfeEntradaConferenciaService.prepararEstoque(nfId, {
        data_entrada: dados.data_entrada || null,
      });
      setDados(next);
      setAvisoPedido('');
      toast.success('Conferência finalizada com sucesso.');
      notifyUpdated();
    } catch (e) {
      const msg = prepararEstoqueErrorMessage(e);
      setErro(msg);
      toast.error(msg.split('\n')[0] || 'Não foi possível finalizar a conferência.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      {!embedded ? <PageHeader title="Conferência NF-e de Entrada" /> : null}
      {!embedded ? (
      <div className="mb-4 rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
        Revisão segura da NF-e importada: salvar ou finalizar a conferência não gera contas a pagar, não movimenta estoque e não
        concilia atendimento automaticamente. A aplicação de estoque físico e o financeiro exigem ação explícita posterior.
      </div>
      ) : null}
      {dados && (
        <div className="erp-card p-4 mb-4 grid md:grid-cols-4 gap-3 text-sm">
          <div><div className="text-muted-foreground text-xs">Fornecedor</div><div>{dados.fornecedor_nome}</div></div>
          <div><div className="text-muted-foreground text-xs">CNPJ</div><div>{dados.fornecedor_cnpj || '—'}</div></div>
          <div><div className="text-muted-foreground text-xs">NF-e</div><div>{dados.numero}/{dados.serie}</div></div>
          <div>
            <div className="text-muted-foreground text-xs">Status</div>
            <div>{labelStatusConferenciaCabecalho(dados.status)}</div>
            {estoqueJaAplicado ? (
              <span className="erp-badge-success text-[10px] mt-1 inline-block">Estoque aplicado</span>
            ) : null}
            {dados.pedido_baixa_aplicado_em ? (
              <span className="erp-badge-success text-[10px] mt-1 inline-block ml-1">Pedido baixado</span>
            ) : null}
          </div>
          <div><div className="text-muted-foreground text-xs">Emissão</div><div>{dados.data_emissao?.slice(0, 10)}</div></div>
          <div>
            <div className="text-muted-foreground text-xs">Data de entrada *</div>
            <input
              type="date"
              className="erp-input mt-1 w-full max-w-[11rem]"
              value={dados.data_entrada?.slice(0, 10) || ''}
              disabled={estoqueJaAplicado}
              onChange={(e) =>
                setDados((prev) => (prev ? { ...prev, data_entrada: e.target.value || null } : prev))
              }
            />
            <p className="text-[11px] text-muted-foreground mt-1">
              Competência operacional/fiscal da entrada. Pode ser diferente da emissão (ex.: virada de mês).
            </p>
          </div>
          <div><div className="text-muted-foreground text-xs">Valor total</div><div>R$ {Number(dados.valor_total || 0).toFixed(2)}</div></div>
          <div className="md:col-span-2">
            <div className="text-muted-foreground text-xs">Pedido de compra vinculado</div>
            <select
              className="erp-select mt-1"
              value={dados.pedido_compra_id ?? ''}
              onChange={(e) => onChangePedidoCompra(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Sem pedido vinculado</option>
              {pedidos
                .filter((p) => !dados.fornecedor_nome || p.fornecedor_nome === dados.fornecedor_nome)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.numero}
                  </option>
                ))}
            </select>
            {!dados.pedido_compra_id ? (
              <p className="text-xs text-muted-foreground mt-2">
                Sem pedido de compra vinculado. A conferência seguirá sem comparação Pedido × NF.
              </p>
            ) : (
              <p className="text-xs text-muted-foreground mt-2">
                Vincule itens do pedido linha a linha para comparar Pedido × NF (opcional para finalizar a conferência).
              </p>
            )}
          </div>
          <div className="md:col-span-4">
            <FornecedorEntradaAcoes
              status={dados.fornecedor}
              busy={busy}
              onVincular={async (fornecedorId) => {
                const res = await nfeEntradaConferenciaService.vincularFornecedor(nfId, fornecedorId);
                setDados(res.conferencia);
              }}
              onCadastrar={async (payload) => {
                const res = await nfeEntradaConferenciaService.cadastrarVincularFornecedor(nfId, payload);
                setDados(res.conferencia);
              }}
            />
          </div>
          <div className="md:col-span-4 pt-2 border-t border-border/60">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">Ações financeiras</p>
            <NFeEntradaFinanceiroAcoes
              nfeEntradaId={nfId}
              conferenciaStatus={dados.status}
              financeiro={dados.financeiro ?? null}
              onGerar={() => setGerarCpOpen(true)}
            />
          </div>
        </div>
      )}
      {avisoPedido ? <div className="text-amber-700 dark:text-amber-300 text-sm mb-3">{avisoPedido}</div> : null}
      {dados ? (
        <details className="erp-card mb-4 group" open={resumoAberto} onToggle={(e) => setResumoAberto(e.currentTarget.open)}>
          <summary className="cursor-pointer list-none px-4 py-3 flex flex-wrap items-center gap-2 border-b border-border/60">
            <span className="text-sm font-medium">Resumo Pedido × NF</span>
            {dados.resumo_pedido?.pedido_selecionado ? (
              <>
                <span className="erp-badge-success text-[10px]">Vinculados: {dados.resumo_pedido.totais.vinculados}</span>
                <span className={dados.resumo_pedido.totais.faltantes ? 'erp-badge-warning text-[10px]' : 'erp-badge-success text-[10px]'}>
                  Faltantes: {dados.resumo_pedido.totais.faltantes}
                </span>
                <span className={dados.resumo_pedido.totais.extras ? 'erp-badge-warning text-[10px]' : 'erp-badge-success text-[10px]'}>
                  Extras: {dados.resumo_pedido.totais.extras}
                </span>
                <span className={dados.resumo_pedido.totais.itens_parciais ? 'erp-badge-warning text-[10px]' : 'erp-badge-info text-[10px]'}>
                  Parciais: {dados.resumo_pedido.totais.itens_parciais ?? 0}
                </span>
                <span className={dados.resumo_pedido.totais.itens_excedentes ? 'erp-badge-danger text-[10px]' : 'erp-badge-info text-[10px]'}>
                  Excedentes: {dados.resumo_pedido.totais.itens_excedentes ?? 0}
                </span>
                <span className={dados.resumo_pedido.totais.itens_completos ? 'erp-badge-success text-[10px]' : 'erp-badge-info text-[10px]'}>
                  Completos: {dados.resumo_pedido.totais.itens_completos ?? 0}
                </span>
              </>
            ) : null}
          </summary>
          <div className="px-4 py-3 text-sm space-y-3">
            {!dados.resumo_pedido ? (
              <p className="text-muted-foreground text-xs">Salve a conferência para atualizar o resumo após alterar o pedido ou vínculos.</p>
            ) : !dados.resumo_pedido.pedido_selecionado ? (
              <p className="text-muted-foreground">{dados.resumo_pedido.mensagem}</p>
            ) : (
              <>
                {dados.resumo_pedido.totais.faltantes === 0 &&
                dados.resumo_pedido.totais.extras === 0 &&
                dados.resumo_pedido.totais.itens_nf > 0 ? (
                  <p className="text-emerald-700 dark:text-emerald-300 font-medium">
                    Todos os itens da NF estão vinculados ao pedido.
                  </p>
                ) : null}
                {dados.resumo_pedido.itens_pedido_sem_nf.length > 0 ? (
                  <div>
                    <p className="font-medium text-amber-800 dark:text-amber-300 mb-1">
                      Itens do pedido não encontrados na NF ({dados.resumo_pedido.itens_pedido_sem_nf.length})
                    </p>
                    <ul className="text-xs text-muted-foreground space-y-1 max-h-32 overflow-auto">
                      {dados.resumo_pedido.itens_pedido_sem_nf.map((row) => (
                        <li key={row.id}>
                          {row.produto_codigo || '—'} · {row.descricao || '—'} · {Number(row.quantidade).toFixed(3)}{' '}
                          {row.unidade} · R$ {Number(row.valor_unitario).toFixed(2)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {dados.resumo_pedido.itens_nf_sem_pedido.length > 0 ? (
                  <div>
                    <p className="font-medium text-amber-800 dark:text-amber-300 mb-1">
                      Itens da NF sem vínculo com pedido ({dados.resumo_pedido.itens_nf_sem_pedido.length})
                    </p>
                    <ul className="text-xs text-muted-foreground space-y-1 max-h-32 overflow-auto">
                      {dados.resumo_pedido.itens_nf_sem_pedido.map((row) => (
                        <li key={row.id}>
                          Item {row.n_item} · {row.codigo_fornecedor || '—'} · {row.descricao_fornecedor || '—'} ·{' '}
                          {Number(row.quantidade).toFixed(3)} {row.unidade} · R$ {Number(row.valor_unitario).toFixed(2)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {(dados.resumo_pedido.resumo_quantitativo?.length ?? 0) > 0 ? (
                  <div>
                    <p className="font-medium mb-2">Quantidade por item do pedido</p>
                    <ul className="space-y-3 max-h-64 overflow-auto">
                      {dados.resumo_pedido.resumo_quantitativo.map((row) => (
                        <li key={row.item_pedido_id} className="text-xs border border-border/60 rounded-md p-2 space-y-1">
                          <div className="font-medium">
                            {row.produto_codigo || '—'} · {row.descricao || '—'}
                          </div>
                          <div className="text-muted-foreground grid grid-cols-2 sm:grid-cols-4 gap-x-3 gap-y-0.5">
                            <span>Pedido: {Number(row.quantidade_pedido).toFixed(3)}</span>
                            <span>NF vinculada: {Number(row.quantidade_nf_vinculada).toFixed(3)}</span>
                            <span>Saldo: {Number(row.saldo_na_nf).toFixed(3)}</span>
                            <span>
                              Status:{' '}
                              <span
                                className={
                                  row.status_quantitativo === 'completo'
                                    ? 'text-emerald-700 dark:text-emerald-300'
                                    : row.status_quantitativo === 'excedente'
                                      ? 'text-destructive'
                                      : row.status_quantitativo === 'parcial'
                                        ? 'text-amber-700 dark:text-amber-300'
                                        : ''
                                }
                              >
                                {labelStatusQuantitativoPedido(row.status_quantitativo)}
                              </span>
                            </span>
                          </div>
                          {row.linhas_vinculadas.length > 0 ? (
                            <div className="text-muted-foreground">
                              Linhas NF: {row.linhas_vinculadas.map((lv) => `item ${lv.n_item}`).join(', ')}
                            </div>
                          ) : null}
                          {row.alertas.length > 0 ? (
                            <ul className="space-y-0.5">
                              {row.alertas.map((codigo) => (
                                <li
                                  key={codigo}
                                  className={
                                    codigo === 'quantidade_nf_maior_que_pedido'
                                      ? 'text-destructive'
                                      : 'text-amber-700 dark:text-amber-300'
                                  }
                                >
                                  {labelAlertaResumoQuantitativo(codigo)}
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {(dados.resumo_pedido.saldo_pedido_global?.length ?? 0) > 0 ? (
                  <details className="border border-border/60 rounded-md">
                    <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
                      Saldo acumulado do pedido
                      <span className="ml-2 erp-badge-info text-[10px]">
                        Parciais: {dados.resumo_pedido.totais.itens_parciais_global ?? 0}
                      </span>
                      <span className="ml-1 erp-badge-success text-[10px]">
                        Completos: {dados.resumo_pedido.totais.itens_completos_global ?? 0}
                      </span>
                    </summary>
                    <div className="px-3 pb-3 space-y-3 text-xs">
                      <p className="text-muted-foreground">{NOTA_SALDO_CONFERENCIA_PEDIDO}</p>
                      {(dados.resumo_pedido.totais.itens_completos_global ?? 0) > 0 &&
                      (dados.resumo_pedido.totais.itens_parciais_global ?? 0) === 0 &&
                      (dados.resumo_pedido.totais.itens_excedentes_global ?? 0) === 0 &&
                      (dados.resumo_pedido.totais.itens_pendentes_global ?? 0) === 0 ? (
                        <p className="text-emerald-700 dark:text-emerald-300 font-medium">
                          Pedido completamente atendido pelas conferências vinculadas.
                        </p>
                      ) : null}
                      <ul className="space-y-3 max-h-72 overflow-auto">
                        {dados.resumo_pedido.saldo_pedido_global.map((row) => (
                          <li key={row.item_pedido_id} className="border border-border/40 rounded-md p-2 space-y-1">
                            <div className="font-medium">
                              {row.produto_codigo || '—'} · {row.descricao || '—'}
                            </div>
                            <div className="text-muted-foreground grid grid-cols-2 sm:grid-cols-3 gap-x-3 gap-y-0.5">
                              <span>Pedido: {Number(row.quantidade_pedido).toFixed(3)}</span>
                              <span>Esta NF: {Number(row.quantidade_nf_atual).toFixed(3)}</span>
                              <span>Outras NFs: {Number(row.quantidade_outras_nfs).toFixed(3)}</span>
                              <span>Total conferido: {Number(row.quantidade_total_conferida).toFixed(3)}</span>
                              <span>Saldo: {Number(row.saldo_pedido).toFixed(3)}</span>
                              <span>
                                Status:{' '}
                                <span
                                  className={
                                    row.status_saldo === 'completo'
                                      ? 'text-emerald-700 dark:text-emerald-300'
                                      : row.status_saldo === 'excedente'
                                        ? 'text-destructive'
                                        : row.status_saldo === 'parcial'
                                          ? 'text-amber-700 dark:text-amber-300'
                                          : ''
                                  }
                                >
                                  {labelStatusSaldoGlobalPedido(row.status_saldo)}
                                </span>
                              </span>
                            </div>
                            {row.conferencias_relacionadas.length > 0 ? (
                              <div className="text-muted-foreground">
                                NFs:{' '}
                                {row.conferencias_relacionadas
                                  .map((c) =>
                                    `${c.nf_numero}/${c.nf_serie} (${Number(c.quantidade).toFixed(3)}${c.atual ? ', esta NF' : ''})`,
                                  )
                                  .join(' · ')}
                              </div>
                            ) : null}
                            {row.status_saldo === 'excedente' ? (
                              <p className="text-destructive">
                                Quantidade conferida acumulada excede o pedido.
                              </p>
                            ) : null}
                            {row.status_saldo === 'parcial' ? (
                              <p className="text-amber-700 dark:text-amber-300">
                                Item parcialmente atendido considerando múltiplas NFs.
                              </p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </details>
                ) : null}
              </>
            )}
          </div>
        </details>
      ) : null}

      {dados?.equivalencias ? (
        <details
          className="erp-card mb-4 group"
          open={equivalenciasAberto}
          onToggle={(e) => setEquivalenciasAberto(e.currentTarget.open)}
        >
          <summary className="cursor-pointer list-none px-4 py-3 flex flex-wrap items-center gap-2 border-b border-border/60">
            <span className="text-sm font-medium">Equivalências e Composições</span>
            {(dados.equivalencias.sugestoes?.length ?? 0) > 0 ? (
              <span className="erp-badge-warning text-[10px]">
                {dados.equivalencias.sugestoes.length} sugestão(ões)
              </span>
            ) : (
              <span className="erp-badge-info text-[10px]">Sem sugestões automáticas</span>
            )}
          </summary>
          <div className="px-4 py-3 text-sm space-y-3">
            <p className="text-xs text-muted-foreground">{AVISO_EQUIVALENCIA_SEM_ESTOQUE}</p>
            {dados.equivalencias.comparacao_pedido_nf ? (
              <div className="text-xs border border-border/60 rounded-md p-2 space-y-1">
                <p className="font-medium">Comparação Pedido × NF (informativa)</p>
                <p>
                  Produtos pedido: {formatMoedaBRL(dados.equivalencias.comparacao_pedido_nf.valor_produtos_pedido)} ·
                  Produtos NF: {formatMoedaBRL(dados.equivalencias.comparacao_pedido_nf.valor_produtos_nf)} ·
                  Diferença: {formatMoedaBRL(dados.equivalencias.comparacao_pedido_nf.diferenca_produtos)}
                </p>
              </div>
            ) : null}
            {(dados.equivalencias.sugestoes ?? []).map((sug, idx) => {
              const badge = badgeConfiancaEquivalencia(sug.nivel_confianca);
              return (
                <div key={`eq-sug-${idx}`} className="border border-border/60 rounded-md p-3 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="erp-badge-primary text-[10px]">{labelTipoEquivalencia(sug.tipo)}</span>
                    {sug.tipo_composicao ? (
                      <span className="erp-badge-outline text-[10px]">{labelTipoComposicao(sug.tipo_composicao)}</span>
                    ) : null}
                    <span className={`${badge.className} text-[10px]`}>{badge.label} ({sug.confianca}%)</span>
                    {sug.dentro_tolerancia === false ? (
                      <span className="erp-badge-danger text-[10px]">Fora da tolerância</span>
                    ) : (
                      <span className="erp-badge-success text-[10px]">Dentro da tolerância</span>
                    )}
                  </div>
                  <p className="font-medium">
                    {sug.produto_interno_codigo} — {sug.produto_interno_descricao}
                  </p>
                  {sug.alerta_filial ? <p className="text-xs text-amber-700 dark:text-amber-300">{sug.alerta_filial}</p> : null}
                  <ul className="text-xs text-muted-foreground space-y-1">
                    {(sug.itens_nfe ?? []).map((it, j) => (
                      <li key={`eq-it-${idx}-${j}`}>
                        {it.codigo_fornecedor || '—'} · {it.descricao || '—'} · qtd {it.quantidade} ·{' '}
                        {formatMoedaBRL(it.valor_total)}
                      </li>
                    ))}
                  </ul>
                  <p className="text-xs">
                    Total NF: {formatMoedaBRL(sug.valor_total_agrupado)} · Pedido:{' '}
                    {formatMoedaBRL(sug.valor_pedido_referencia)} · Diferença:{' '}
                    {formatMoedaBRL(sug.diferenca_valor)}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="erp-btn-primary erp-btn-sm"
                      disabled={eqBusy || estoqueJaAplicado}
                      onClick={async () => {
                        if (!sug.produto_interno_id || !(sug.itens_nfe_conferencia_ids?.length ?? 0)) return;
                        setEqBusy(true);
                        setErro('');
                        try {
                          const res = await nfeEntradaConferenciaService.confirmarEquivalencia(nfId, {
                            produto_interno_id: sug.produto_interno_id,
                            item_pedido_compra_id: sug.item_pedido_compra_id ?? undefined,
                            itens_nfe_conferencia_ids: sug.itens_nfe_conferencia_ids ?? [],
                            tipo_agrupamento: sug.tipo,
                            quantidade_equivalente: sug.quantidade_equivalente,
                            confianca: sug.confianca,
                            salvar_regra_fornecedor: true,
                          });
                          setDados(res.conferencia);
                          await hydrateProdutoCache(res.conferencia);
                        } catch (err) {
                          setErro(apiErrorMessage(err));
                        } finally {
                          setEqBusy(false);
                        }
                      }}
                    >
                      Confirmar vínculo
                    </button>
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      disabled={eqBusy}
                      onClick={async () => {
                        if (!sug.produto_interno_id) return;
                        setEqBusy(true);
                        try {
                          const res = await nfeEntradaConferenciaService.rejeitarEquivalencia(nfId, {
                            produto_interno_id: sug.produto_interno_id,
                            itens_nfe_conferencia_ids: sug.itens_nfe_conferencia_ids ?? [],
                          });
                          setDados(res.conferencia);
                        } catch (err) {
                          setErro(apiErrorMessage(err));
                        } finally {
                          setEqBusy(false);
                        }
                      }}
                    >
                      Rejeitar sugestão
                    </button>
                  </div>
                </div>
              );
            })}
            {(dados.equivalencias.agrupamentos?.length ?? 0) > 0 ? (
              <div>
                <p className="font-medium text-xs mb-1">Agrupamentos confirmados</p>
                <ul className="text-xs text-muted-foreground space-y-1">
                  {dados.equivalencias.agrupamentos.map((agr: { id?: number; produto_interno_codigo?: string; status?: string }) => (
                    <li key={`agr-${agr.id}`}>
                      #{agr.id} · {agr.produto_interno_codigo} · {agr.status}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </details>
      ) : null}

      {dados?.resumo_fiscal ? (
        <details
          className="erp-card mb-4 group"
          open={resumoFiscalAberto}
          onToggle={(e) => setResumoFiscalAberto(e.currentTarget.open)}
        >
          <summary className="cursor-pointer list-none px-4 py-3 flex flex-wrap items-center gap-2 border-b border-border/60">
            <span className="text-sm font-medium">Resumo fiscal (entrada)</span>
            <span className="erp-badge-success text-[10px]">OK: {dados.resumo_fiscal.ok}</span>
            <span className="erp-badge-warning text-[10px]">Alerta: {dados.resumo_fiscal.alerta}</span>
            <span className="erp-badge-warning text-[10px]">Sem regra: {dados.resumo_fiscal.sem_regra}</span>
            <span className="erp-badge-danger text-[10px]">Bloqueado: {dados.resumo_fiscal.bloqueado}</span>
            <span className="erp-badge-info text-[10px]">
              Mov. estoque: {dados.resumo_fiscal.movimenta_estoque}
            </span>
            <span className="erp-badge-info text-[10px]">
              Cert. fornec.: {dados.resumo_fiscal.exige_certificado_fornecedor}
            </span>
          </summary>
          <div className="px-4 py-3 text-sm space-y-2">
            <p className="text-xs text-muted-foreground">
              Diagnóstico das regras fiscais de entrada por item. Itens com status Bloqueado (regra com severidade
              BLOQUEIO) impedem finalizar a conferência até revisão fiscal.
              {dados.resumo_fiscal.bloqueado > 0 ? (
                <span className="block mt-1 text-destructive font-medium">
                  Esta NF possui {dados.resumo_fiscal.bloqueado} item(ns) bloqueado(s) — revise antes de finalizar a conferência.
                </span>
              ) : null}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div>
                <span className="text-muted-foreground">Itens avaliados</span>
                <div className="font-medium">{dados.resumo_fiscal.total_itens}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Ignorados</span>
                <div className="font-medium">{dados.resumo_fiscal.ignorados}</div>
              </div>
              {(dados.resumo_fiscal.uf_origem || dados.resumo_fiscal.uf_destino) ? (
                <div className="sm:col-span-2">
                  <span className="text-muted-foreground">UF NF</span>
                  <div className="font-medium">
                    {dados.resumo_fiscal.uf_origem || '—'} → {dados.resumo_fiscal.uf_destino || '—'}
                  </div>
                </div>
              ) : null}
            </div>
            {dados.resumo_fiscal.sem_regra > 0 ? (
              <p className="text-amber-700 dark:text-amber-300 text-xs">
                {dados.resumo_fiscal.sem_regra} item(ns) sem classificação fiscal cadastrada. Cadastre em Regras Fiscais →
                Classificação de entrada ou valide com o fiscal.
              </p>
            ) : null}
          </div>
        </details>
      ) : null}

      {dados?.resumo_elegibilidade_estoque ? (
        <details
          className="erp-card mb-4 group"
          open={resumoElegibilidadeAberto}
          onToggle={(e) => setResumoElegibilidadeAberto(e.currentTarget.open)}
        >
          <summary className="cursor-pointer list-none px-4 py-3 flex flex-wrap items-center gap-2 border-b border-border/60">
            <span className="text-sm font-medium">Elegibilidade para estoque (checklist)</span>
            <span className="erp-badge-success text-[10px]">Aptos: {dados.resumo_elegibilidade_estoque.aptos}</span>
            <span className="erp-badge-warning text-[10px]">
              Com alerta: {dados.resumo_elegibilidade_estoque.aptos_com_alerta}
            </span>
            <span className="erp-badge-danger text-[10px]">
              Bloqueados: {dados.resumo_elegibilidade_estoque.bloqueados}
            </span>
            <span className="erp-badge-info text-[10px]">
              Não movimentam: {dados.resumo_elegibilidade_estoque.nao_movimentam}
            </span>
          </summary>
          <div className="px-4 py-3 text-sm space-y-2">
            <p className="text-xs text-muted-foreground">
              Este checklist indica elegibilidade para uma futura aplicação de estoque. Ainda não representa
              movimentação efetiva.
            </p>
            {dados.resumo_elegibilidade_estoque.bloqueados > 0 ? (
              <p className="text-xs text-destructive">
                Itens bloqueados no checklist podem coincidir com bloqueio fiscal; consulte também o resumo fiscal.
              </p>
            ) : null}
          </div>
        </details>
      ) : null}

      {erro && <div className="text-destructive text-sm mb-3 whitespace-pre-line">{erro}</div>}
      {dados && !dados.pedido_compra_id ? (
        <p className="text-xs text-muted-foreground mb-2 px-1">
          Selecione um pedido de compra se quiser comparar Pedido × NF. A conferência pode seguir sem pedido.
        </p>
      ) : null}
      <div className="erp-card overflow-x-auto">
        <table className="erp-table text-sm [&_td]:py-2 [&_th]:py-2">
          <thead>
            <tr>
              <th>Item</th>
              <th>Fornecedor</th>
              <th>NCM/CFOP</th>
              <th>Fiscal</th>
              <th>NF</th>
              <th>Item do pedido</th>
              <th>Produto cadastrado</th>
              <th>Corrida/Lote</th>
              <th>Estoque calc.</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {dados?.itens.map((it, idx) => (
              <tr key={it.id}>
                <td>
                  <div className="flex flex-col gap-1">
                    <span>{idx + 1}</span>
                    {it.item_pedido_compra_id ? (
                      <span className="erp-badge-success text-[10px] w-fit">Com pedido</span>
                    ) : (
                      <span className="erp-badge-warning text-[10px] w-fit">Sem pedido</span>
                    )}
                  </div>
                </td>
                <td>
                  <div>{it.dados_nf?.codigo_fornecedor || '—'}</div>
                  <div className="text-xs text-muted-foreground">{it.dados_nf?.descricao_fornecedor || '—'}</div>
                </td>
                <td className="text-xs whitespace-nowrap">
                  {it.dados_nf?.ncm || '—'} / {it.dados_nf?.cfop || '—'}
                </td>
                <td className="min-w-[11rem] max-w-[14rem]">
                  {(() => {
                    const rf = it.resultado_fiscal;
                    const trib = it.tributos_nf;
                    const cstLabel = [trib?.cst_icms, trib?.csosn].filter(Boolean).join(' / ') || '—';
                    const msg = mensagemFiscalEntrada(rf);
                    const criarRegraUrl = buildCriarRegraFiscalEntradaUrl(rf, dados.resumo_fiscal);
                    const cfopNf = (rf?.cfop_nf || it.dados_nf?.cfop || '').trim();
                    const cfopEntradaEsp = (rf?.cfop_entrada_esperado || '').trim();
                    const cenario =
                      (rf?.descricao_cenario || '').trim() || (rf?.regra_nome || '').trim() || 'Sem regra';
                    const tituloMatch = tituloMatchRegraFiscal(rf);
                    return (
                      <div className="space-y-1 text-[10px]">
                        <span
                          className={`${badgeClassStatusFiscalEntrada(rf?.status || 'SEM_REGRA')} inline-block`}
                        >
                          {labelStatusFiscalEntrada(rf?.status || 'SEM_REGRA')}
                        </span>
                        {cfopNf ? (
                          <div className="text-muted-foreground font-mono">
                            CFOP NF: {cfopNf}
                            {cfopEntradaEsp ? ` → Entrada esp.: ${cfopEntradaEsp}` : ''}
                          </div>
                        ) : null}
                        {(() => {
                          const impResumo = resumoImpostosLinha(rf?.impostos_nf);
                          return impResumo ? (
                            <div className="text-muted-foreground line-clamp-2" title={impResumo}>
                              {impResumo}
                            </div>
                          ) : (
                            <div className="text-muted-foreground">CST: {cstLabel}</div>
                          );
                        })()}
                        <div className="truncate font-medium" title={tituloMatch ? `${cenario}\n${tituloMatch}` : cenario}>
                          {cenario}
                        </div>
                        {(rf?.divergencias?.length ?? 0) > 0 ? (
                          <ul className="text-amber-700 dark:text-amber-300 space-y-0.5">
                            {divergenciasFiscaisResumo(rf, 3).map((d) => (
                              <li key={d} className="truncate" title={d}>
                                {d}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        {msg ? (
                          <div className="text-amber-700 dark:text-amber-300 line-clamp-3" title={msg}>
                            {msg}
                          </div>
                        ) : null}
                        {rf?.status === 'SEM_REGRA' ? (
                          <Link
                            to={criarRegraUrl}
                            className="text-primary underline block truncate"
                            title="Abrir cadastro de regra fiscal de entrada"
                          >
                            Criar regra fiscal de entrada
                          </Link>
                        ) : null}
                        {rf?.movimenta_estoque ? (
                          <span className="erp-badge-info text-[9px]">Mov. estoque</span>
                        ) : null}
                        {rf?.exige_certificado_fornecedor ? (
                          <span className="erp-badge-warning text-[9px]">Cert. fornec.</span>
                        ) : null}
                        {rf?.tem_reforma_configurada ? (
                          <span
                            className="erp-badge-secondary text-[9px]"
                            title="Reforma Tributária configurada na regra (sem comparação automática nesta fase)"
                          >
                            Reforma configurada
                          </span>
                        ) : null}
                        {it.elegibilidade_estoque ? (
                          <div className="pt-1 border-t border-border/50 space-y-0.5">
                            <span
                              className={`${badgeClassElegibilidadeEstoque(it.elegibilidade_estoque.status)} inline-block`}
                              title={(it.elegibilidade_estoque.mensagens || []).join('\n')}
                            >
                              {labelElegibilidadeEstoque(it.elegibilidade_estoque.status)}
                            </span>
                            {(it.elegibilidade_estoque.mensagens || []).length > 0 ? (
                              <p
                                className="text-[9px] text-muted-foreground line-clamp-2"
                                title={it.elegibilidade_estoque.mensagens.join(' ')}
                              >
                                {it.elegibilidade_estoque.mensagens[0]}
                              </p>
                            ) : null}
                            {it.produto_id &&
                            (it.elegibilidade_estoque.status === 'APTO' ||
                              it.elegibilidade_estoque.status === 'APTO_COM_ALERTA') &&
                            dados?.status === 'PREPARADA' ? (
                              <AtenderVendasPendentesBlock
                                itemConferenciaId={it.id}
                                onVinculado={() => void load()}
                              />
                            ) : null}
                          </div>
                        ) : null}
                        {(it.vinculos_atendimento ?? []).map((v) => (
                          <span key={v.linha_id} className="erp-badge-info text-[9px] inline-block mt-1">
                            Atende NF saída {v.numero_nf_saida}
                          </span>
                        ))}
                      </div>
                    );
                  })()}
                </td>
                <td>
                  {Number(it.quantidade_nf || 0).toFixed(3)} {it.unidade_nf}
                </td>
                <td>
                  {dados.pedido_compra_id && pedidoSelecionado ? (
                    <div className="space-y-1 min-w-[280px]">
                      {(() => {
                        const melhor = (it.sugestoes_item_pedido || [])[0];
                        const podeSugerir =
                          !it.item_pedido_compra_id &&
                          Boolean(melhor) &&
                          (melhor?.score ?? 0) >= SCORE_SUGESTAO_ITEM_PEDIDO_ALTO;
                        return podeSugerir ? (
                          <div className="text-xs text-muted-foreground">
                            <span>Sugestão: {labelSugestaoItemPedidoCurta(melhor)}</span>
                            <button
                              type="button"
                              className="erp-btn-outline erp-btn-sm ml-2 mt-1"
                              onClick={() => updateItem(it.id, { item_pedido_compra_id: melhor.id })}
                            >
                              Aplicar sugestão
                            </button>
                          </div>
                        ) : null;
                      })()}
                      {!it.item_pedido_compra_id && it.status !== 'IGNORADO' ? (
                        <p className="text-[10px] text-amber-700 dark:text-amber-300">
                          Linha sem item de pedido vinculado.
                        </p>
                      ) : null}
                      <select
                        className="erp-select w-full"
                        value={it.item_pedido_compra_id ?? ''}
                        onChange={(e) =>
                          updateItem(it.id, {
                            item_pedido_compra_id: e.target.value ? Number(e.target.value) : null,
                          })
                        }
                      >
                        <option value="">Não vinculado</option>
                        {(it.sugestoes_item_pedido || []).map((s) => (
                          <option key={`sug-pc-${s.id}`} value={s.id}>
                            ★ {labelSugestaoItemPedidoCurta(s)} · {Number(s.quantidade).toFixed(3)}{' '}
                            {s.unidade} · R$ {Number(s.valor_unitario).toFixed(2)}
                          </option>
                        ))}
                        {pedidoSelecionado.itens
                          .filter((ipc) => !(it.sugestoes_item_pedido || []).some((s) => s.id === ipc.id))
                          .map((ipc) => (
                            <option key={ipc.id} value={ipc.id}>
                              {labelItemPedidoCompraOption(ipc, produtosMap.get(ipc.produto_id)?.codigo_completo)}
                            </option>
                          ))}
                      </select>
                    </div>
                  ) : (
                    <span className="erp-badge-warning text-[10px]">Sem pedido</span>
                  )}
                </td>
                <td className="min-w-[260px]">
                  <div className="space-y-1 [&_input]:mt-0 [&_input]:h-8 [&_input]:text-xs [&_.erp-btn-outline]:text-[10px] [&_.erp-btn-outline]:py-0.5 [&_.erp-btn-outline]:mt-1">
                    {(it.sugestoes_produto || []).length > 0 && !it.produto_id ? (
                      <div className="flex flex-wrap gap-1">
                        {(it.sugestoes_produto || []).slice(0, 3).map((s) => (
                          <button
                            key={`sug-prod-${s.id}`}
                            type="button"
                            className="erp-btn-outline erp-btn-sm text-[10px] max-w-full truncate"
                            title={`${s.codigo} · ${s.descricao}`}
                            onClick={() => {
                              const stub = {
                                id: s.id,
                                codigo_completo: s.codigo,
                                descricao: s.descricao,
                              } as Produto;
                              setProdutoCache((m) => new Map(m).set(s.id, stub));
                              updateItem(it.id, { produto_id: s.id });
                            }}
                          >
                            ★ {s.codigo}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    <AsyncAutocomplete<Produto>
                      value={it.produto_id ?? null}
                      selectedOption={it.produto_id ? produtoCache.get(it.produto_id) ?? null : null}
                      placeholder="Buscar produto por código ou descrição..."
                      minChars={2}
                      limit={40}
                      search={buscarProdutos}
                      getOptionValue={(p) => p.id}
                      getOptionLabel={labelProdutoLinhaConferencia}
                      listBoxClassName="absolute z-50 mt-1 max-h-72 min-w-[min(100%,22rem)] w-max max-w-[min(100vw-2rem,32rem)] overflow-auto rounded-md border border-border bg-background shadow"
                      renderOption={(p) => (
                        <div className="space-y-0.5 py-0.5 text-left">
                          <div className="font-medium text-foreground break-words">
                            {(p.codigo_completo || '').trim() || '—'}
                          </div>
                          <div className="text-muted-foreground break-words text-xs">{p.descricao}</div>
                        </div>
                      )}
                      onChange={(val, opt) => {
                        if (opt) {
                          setProdutoCache((m) => new Map(m).set(opt.id, opt));
                        }
                        updateItem(it.id, { produto_id: val != null ? Number(val) : null });
                      }}
                    />
                  </div>
                </td>
                <td>
                  {it.status === 'IGNORADO' ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : itemUsaSplitCorrida(it) ? (
                    <div className="space-y-1">
                      <CorridaSplitEditor
                        qtyAlvo={qtyAlvoItemConferencia(it)}
                        unidade={
                          it.unidade_estoque_calculada
                          || produtosMap.get(it.produto_id || 0)?.unidade_estoque_efetiva
                          || it.unidade_nf
                          || 'UN'
                        }
                        splits={it.corridas_split || []}
                        disabled={estoqueJaAplicado}
                        onChange={(corridas_split) => updateItem(it.id, { corridas_split, corrida: '', lote: '' })}
                      />
                      {!estoqueJaAplicado ? (
                        <button
                          type="button"
                          className="text-[11px] text-primary hover:underline"
                          onClick={() => updateItem(it.id, { corridas_split: [], corrida: '', lote: '' })}
                        >
                          Usar corrida única
                        </button>
                      ) : null}
                    </div>
                  ) : (
                    <div className="space-y-1 min-w-[9rem]">
                      <div className="grid grid-cols-2 gap-1">
                        <input
                          className="erp-input h-8 text-xs"
                          placeholder="Corrida"
                          value={it.corrida || ''}
                          disabled={estoqueJaAplicado}
                          onChange={(e) => updateItem(it.id, { corrida: normalizeOperationalInput(e.target.value) })}
                        />
                        <input
                          className="erp-input h-8 text-xs"
                          placeholder="Lote"
                          value={it.lote || ''}
                          disabled={estoqueJaAplicado}
                          onChange={(e) => updateItem(it.id, { lote: normalizeOperationalInput(e.target.value) })}
                        />
                      </div>
                      {!estoqueJaAplicado ? (
                        <button
                          type="button"
                          className="text-[11px] text-primary hover:underline"
                          onClick={() =>
                            updateItem(it.id, {
                              corridas_split: criarSplitsIniciais(qtyAlvoItemConferencia(it)),
                              corrida: '',
                              lote: '',
                            })
                          }
                        >
                          Dividir por corrida
                        </button>
                      ) : null}
                    </div>
                  )}
                </td>
                <td>
                  {Number(it.quantidade_estoque_calculada || 0).toFixed(3)}{' '}
                  {it.unidade_estoque_calculada || produtosMap.get(it.produto_id || 0)?.unidade_estoque_efetiva || '—'}
                  {it.divergencias?.length ? (
                    <div className="text-xs text-amber-600 mt-1 space-y-0.5">
                      {it.divergencias.map((d) => (
                        <div key={d}>{labelDivergenciaConferencia(d)}</div>
                      ))}
                    </div>
                  ) : null}
                  {it.alertas?.length ? <div className="text-xs text-destructive">{it.alertas.join(', ')}</div> : null}
                </td>
                <td className="min-w-[9.5rem]">
                  <span className={`${badgeClassStatusConferencia(it.status)} text-[10px] mb-1 inline-block`}>
                    {labelStatusConferenciaItem(it.status)}
                  </span>
                  <select
                    className="erp-select h-8 text-xs w-full"
                    value={it.status}
                    onChange={(e) =>
                      updateItem(it.id, {
                        status: normalizeOperationalInput(e.target.value) as ItemConferenciaNFeEntrada['status'],
                      })
                    }
                  >
                    <option value="PENDENTE_PRODUTO">{labelStatusConferenciaItem('PENDENTE_PRODUTO')}</option>
                    <option value="PRODUTO_VINCULADO">{labelStatusConferenciaItem('PRODUTO_VINCULADO')}</option>
                    <option value="CONFERIDO">{labelStatusConferenciaItem('CONFERIDO')}</option>
                    <option value="DIVERGENTE">{labelStatusConferenciaItem('DIVERGENTE')}</option>
                    <option value="IGNORADO">{labelStatusConferenciaItem('IGNORADO')}</option>
                  </select>
                  {it.status === 'IGNORADO' ? (
                    <input
                      className="erp-input h-8 text-xs mt-1"
                      placeholder="Motivo para ignorar"
                      value={it.motivo_ignorado || ''}
                      onChange={(e) =>
                        updateItem(it.id, { motivo_ignorado: normalizeOperationalInput(e.target.value) })
                      }
                    />
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="erp-card p-4 mt-4">
        <label className="flex items-center gap-2 text-sm mb-2">
          <input
            type="checkbox"
            checked={Boolean(dados?.divergencias_aceitas)}
            onChange={(e) => dados && setDados({ ...dados, divergencias_aceitas: e.target.checked })}
          />
          Aceitar divergências
        </label>
        <textarea
          className="erp-input min-h-[88px]"
          placeholder="Observação das divergências"
          value={dados?.observacao_divergencias || ''}
          onChange={(e) =>
            dados && setDados({ ...dados, observacao_divergencias: normalizeOperationalInput(e.target.value) })
          }
        />
      </div>
      <div className="flex justify-end gap-2 mt-4 flex-wrap">
        {!embedded ? (
          <button type="button" className="erp-btn-outline" onClick={() => navigate('/nfe-entrada-historica-importada')}>
            Voltar
          </button>
        ) : onClose ? (
          <button type="button" className="erp-btn-outline" onClick={onClose}>
            Fechar
          </button>
        ) : null}
        <button type="button" className="erp-btn-outline" onClick={() => void salvar()} disabled={busy}>
          {dados?.financeiro?.possui_pendencias_operacionais
            ? 'Salvar conferência com pendências'
            : 'Salvar conferência'}
        </button>
        <button type="button" className="erp-btn-primary" onClick={() => void preparar()} disabled={busy}>
          Finalizar conferência
        </button>
        {podeAplicarEstoque ? (
          <button
            type="button"
            className="erp-btn-primary bg-emerald-700 hover:bg-emerald-800"
            onClick={() => void abrirModalAplicar()}
            disabled={busy}
          >
            Aplicar estoque físico
          </button>
        ) : null}
      </div>
      {estoqueJaAplicado ? (
        <p className="text-xs text-emerald-700 mt-3 max-w-3xl ml-auto text-right">
          Estoque físico aplicado em{' '}
          {dados.estoque_aplicado_em ? new Date(dados.estoque_aplicado_em).toLocaleString('pt-BR') : '—'}.
          Esta operação é idempotente e não deve ser repetida.
        </p>
      ) : (
        <p className="text-xs text-muted-foreground mt-3 max-w-3xl ml-auto text-right">
          &quot;Finalizar conferência&quot; valida e encerra a revisão fiscal da NF-e. &quot;Aplicar estoque físico&quot; incrementa{' '}
          <span className="font-mono">EstoqueCorrida</span> uma única vez por linha elegível.
        </p>
      )}
      {modalAplicarOpen && previewAplicar ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="erp-card max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <h2 className="text-lg font-semibold">Aplicar estoque físico</h2>
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3">
              Esta ação incrementa o estoque físico em EstoqueCorrida e não deve ser executada duas vezes.
            </p>
            {modalAplicarErro ? (
              <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">{modalAplicarErro}</p>
            ) : null}
            {previewAplicar.itens_aplicados.length > 0 ? (
              <div>
                <h3 className="text-sm font-medium mb-2">Itens que serão aplicados ({previewAplicar.itens_aplicados.length})</h3>
                <ul className="text-xs space-y-1 max-h-40 overflow-y-auto border rounded p-2">
                  {previewAplicar.itens_aplicados.map((it, idx) => (
                    <li key={`${it.item_conferencia_id}-${it.split_ordem ?? 0}-${idx}`}>
                      Item #{it.item_conferencia_id}
                      {it.split_ordem != null ? ` · split ${it.split_ordem}` : ''}
                      {' — produto '}
                      {it.produto_id}
                      {' — corrida '}
                      {it.corrida}
                      {' — qtd '}
                      {it.quantidade}
                      {it.lote ? ` — lote ${it.lote}` : ''}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {previewAplicar.itens_ignorados.length > 0 ? (
              <div>
                <h3 className="text-sm font-medium mb-2 text-muted-foreground">Não movimentam estoque</h3>
                <ul className="text-xs space-y-1 max-h-32 overflow-y-auto">
                  {previewAplicar.itens_ignorados.map((it) => (
                    <li key={it.item_conferencia_id ?? it.motivo}>
                      #{it.item_conferencia_id}: {it.motivo}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {previewAplicar.alertas.length > 0 ? (
              <div className="text-sm text-amber-800">
                <h3 className="font-medium mb-1">Alertas</h3>
                <ul className="list-disc pl-5 text-xs">
                  {previewAplicar.alertas.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
                <label className="flex items-center gap-2 mt-2 text-xs">
                  <input
                    type="checkbox"
                    checked={confirmarAlertasAplicar}
                    onChange={(e) => setConfirmarAlertasAplicar(e.target.checked)}
                  />
                  Confirmo a aplicação mesmo com alertas
                </label>
              </div>
            ) : null}
            {previewAplicar.pendencias.length > 0 ? (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">
                <h3 className="font-medium mb-1">Pendências bloqueantes</h3>
                <ul className="list-disc pl-5 text-xs">
                  {previewAplicar.pendencias.map((pend, i) => (
                    <li key={i}>
                      Item #{pend.item_conferencia_id}: {pend.motivo}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <label className="block text-xs">
              Observação (opcional)
              <textarea
                className="erp-input w-full mt-1 min-h-[60px]"
                value={obsAplicar}
                onChange={(e) => setObsAplicar(e.target.value)}
              />
            </label>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="erp-btn-outline"
                onClick={() => {
                  setModalAplicarOpen(false);
                  setPreviewAplicar(null);
                  setModalAplicarErro('');
                }}
                disabled={busy}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="erp-btn-primary bg-emerald-700 hover:bg-emerald-800"
                onClick={() => void confirmarAplicarEstoque()}
                disabled={
                  busy ||
                  previewAplicar.pendencias.length > 0 ||
                  (previewAplicar.alertas.length > 0 && !confirmarAlertasAplicar)
                }
              >
                Confirmar aplicação
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <GerarContasPagarNfeEntradaModal
        open={gerarCpOpen}
        nfeEntradaId={nfId}
        onClose={() => setGerarCpOpen(false)}
        onGenerated={({ titulo }) => {
          toast.success('Contas a pagar geradas com sucesso.');
          void load().catch(() => undefined);
          notifyUpdated();
          if (titulo?.id && !embedded) {
            navigate(`/financeiro/contas-pagar?titulo=${titulo.id}`);
          }
        }}
      />

    </div>
  );
}
