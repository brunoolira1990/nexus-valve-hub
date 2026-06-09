import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink, RotateCcw } from 'lucide-react';
import { AlocacaoAtendimentoGerenciarSection } from '@/components/comercial/AlocacaoAtendimentoGerenciarPanel';
import { AtendimentoOperacionalResumo } from '@/components/comercial/AtendimentoOperacionalResumo';
import { pedidosVendaService } from '@/services/api/comercial';
import { apiErrorMessage } from '@/services/api/config';
import type { ItemPedido, ResumoFaturamentoPedido } from '@/types';
import { formatCurrencyBRL } from '@/lib/formatBr';
import {
  getFaturamentoStatusLabel,
  getNFeFiscalBadgeTokens,
  linhaFaturamentoNfeAmigavel,
  mensagemNfeFaturamentoInconsistencia,
  MSG_ALERTA_FATURAMENTO_SEM_ATENDIMENTO,
  pedidoComercialFaturado,
  pedidoFaturadoSemAtendimento,
  resumoBloqueiaGeracaoNfe,
  tituloResumoNfePedido,
} from '@/lib/pedidoVendaModalUi';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { MotivoAcaoDestrutivaModal } from '@/components/comercial/MotivoAcaoDestrutivaModal';
import { toast } from 'sonner';

const MSG_ETAPA =
  'Esta etapa prepara o faturamento. A emissão da NF-e será feita em fase posterior.';

const MSG_GERAR_NFE =
  'Esta ação cria uma NF-e Saída em rascunho. A transmissão para SEFAZ será feita em fase posterior.';

type Props = {
  pedidoId: number;
  itens?: ItemPedido[];
  onAtualizado?: () => void;
  /** Sem borda/margem externa — uso dentro de aba do modal de pedido. */
  embedded?: boolean;
};

export function PedidoFaturamentoPanel({ pedidoId, itens = [], onAtualizado, embedded = false }: Props) {
  const navigate = useNavigate();
  const [resumo, setResumo] = useState<ResumoFaturamentoPedido | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [observacao, setObservacao] = useState('');
  const [qtyFat, setQtyFat] = useState<Record<number, string>>({});
  const [estornoModal, setEstornoModal] = useState<{ faturamentoId: number; label: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await pedidosVendaService.resumoFaturamento(pedidoId);
      setResumo(r);
      const next: Record<number, string> = {};
      for (const it of r.itens) {
        if (parseFloat(it.quantidade_disponivel) > 0) {
          next[it.item_pedido_id] = it.quantidade_disponivel;
        }
      }
      setQtyFat(next);
    } catch (e) {
      setError(apiErrorMessage(e, { fallback: 'Não foi possível carregar o resumo de faturamento.' }));
    } finally {
      setLoading(false);
    }
  }, [pedidoId]);

  useEffect(() => {
    void load();
  }, [load]);

  const statusBadge = (status: string) => {
    const s = status.toUpperCase();
    if (s === 'FATURADO') return 'erp-badge-success';
    if (s === 'PARCIALMENTE_FATURADO' || s === 'PARCIAL') return 'erp-badge-warning';
    if (s === 'EM_FATURAMENTO') return 'erp-badge-warning';
    if (s === 'CANCELADO') return 'erp-badge-danger';
    return 'erp-badge-warning';
  };

  const criarFaturamento = async () => {
    if (!resumo?.pode_faturar) return;
    const itens = resumo.itens
      .map((it) => ({
        item_pedido_id: it.item_pedido_id,
        quantidade: (qtyFat[it.item_pedido_id] || '').trim(),
      }))
      .filter((x) => x.quantidade && parseFloat(x.quantidade) > 0);
    if (!itens.length) {
      setError('Informe a quantidade a faturar em ao menos um item.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await pedidosVendaService.criarFaturamento(pedidoId, { observacao, itens });
      alert(r.mensagens?.join('\n') || MSG_ETAPA);
      setObservacao('');
      await load();
      onAtualizado?.();
    } catch (e) {
      setError(apiErrorMessage(e, { fallback: 'Não foi possível criar o faturamento.' }));
    } finally {
      setLoading(false);
    }
  };

  const confirmar = async (faturamentoId: number) => {
    if (!confirm('Confirmar este faturamento? As quantidades faturadas do pedido serão atualizadas.')) return;
    setLoading(true);
    setError(null);
    try {
      const r = await pedidosVendaService.confirmarFaturamento(pedidoId, faturamentoId);
      alert(r.mensagens?.join('\n') || 'Faturamento confirmado.');
      await load();
      onAtualizado?.();
    } catch (e) {
      setError(apiErrorMessage(e, { fallback: 'Não foi possível confirmar o faturamento.' }));
    } finally {
      setLoading(false);
    }
  };

  const gerarNfe = async (faturamentoId: number) => {
    if (!confirm(MSG_GERAR_NFE)) return;
    setLoading(true);
    setError(null);
    try {
      const r = await pedidosVendaService.gerarNfeSaidaFaturamento(pedidoId, faturamentoId, {
        observacao: observacao || undefined,
      });
      const msg = r.mensagens?.join('\n') || MSG_GERAR_NFE;
      alert(msg);
      await load();
      onAtualizado?.();
      if (r.nfe_saida_id && confirm('Deseja abrir a NF-e Saída agora?')) {
        navigate(`/nfe-saida?nfe=${r.nfe_saida_id}`);
      }
    } catch (e) {
      setError(apiErrorMessage(e, { fallback: 'Não foi possível gerar a NF-e Saída.' }));
    } finally {
      setLoading(false);
    }
  };

  const cancelarRascunho = async (faturamentoId: number) => {
    if (!confirm('Cancelar este rascunho de faturamento?')) return;
    setLoading(true);
    setError(null);
    try {
      const r = await pedidosVendaService.cancelarFaturamento(pedidoId, faturamentoId);
      alert(r.mensagens?.join('\n') || 'Rascunho cancelado.');
      await load();
      onAtualizado?.();
    } catch (e) {
      setError(apiErrorMessage(e, { fallback: 'Não foi possível cancelar o rascunho.' }));
    } finally {
      setLoading(false);
    }
  };

  const estornarFaturamento = async (faturamentoId: number, motivo: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await pedidosVendaService.estornarFaturamento(pedidoId, faturamentoId, { motivo });
      toast.success(r.mensagens?.[0] || 'Faturamento estornado. Pedido reaberto para edição.');
      await load();
      onAtualizado?.();
    } catch (e) {
      const msg = apiErrorMessage(e, { fallback: 'Não foi possível estornar o faturamento.' });
      setError(msg);
      toast.error(msg);
      throw e;
    } finally {
      setLoading(false);
    }
  };

  const repararVinculoNfe = async (faturamentoId: number) => {
    setLoading(true);
    setError(null);
    try {
      const r = await pedidosVendaService.repararVinculoNfeFaturamento(pedidoId, faturamentoId);
      alert(r.mensagens?.join('\n') || 'Vínculo reparado.');
      await load();
      onAtualizado?.();
    } catch (e) {
      setError(apiErrorMessage(e, { fallback: 'Não foi possível reparar o vínculo NF-e.' }));
    } finally {
      setLoading(false);
    }
  };

  if (loading && !resumo) {
    return <p className="text-sm text-muted-foreground py-4">Carregando faturamento…</p>;
  }

  if (!resumo) {
    return error ? <p className="text-sm text-destructive">{error}</p> : null;
  }

  const totalmenteFaturado = pedidoComercialFaturado(resumo.status);
  const alertaSemAtendimento = pedidoFaturadoSemAtendimento(
    resumo.status,
    resumo.resumo_atendimento_operacional,
  );
  const faturamentosNfe = resumo.faturamentos_nfe ?? [];
  const linhaEstorno = faturamentosNfe.find((f) => f.pode_estornar_pre_autorizacao !== false);
  const bloqueiaGeracaoNfe = resumoBloqueiaGeracaoNfe(resumo);
  const avisoTotalDesatualizado = (resumo.inconsistencias ?? []).some(
    (i) => i.codigo === 'valor_total_pedido_desatualizado',
  );

  const recalcularTotaisPedido = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await pedidosVendaService.recalcularTotaisPedido(pedidoId);
      setResumo(r);
      toast.success('Total do pedido atualizado conforme a soma dos itens.');
      onAtualizado?.();
    } catch (e) {
      setError(apiErrorMessage(e, { fallback: 'Não foi possível recalcular o total do pedido.' }));
    } finally {
      setLoading(false);
    }
  };

  const shellClass = embedded
    ? 'space-y-4'
    : 'mt-6 rounded-md border border-border bg-muted/20 p-4 space-y-4';

  return (
    <div className={shellClass}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-medium text-sm">Faturamento do pedido</h3>
        <span className={statusBadge(resumo.status)}>{resumo.status || '—'}</span>
      </div>
      <p className="text-xs text-muted-foreground">{MSG_ETAPA}</p>
      {totalmenteFaturado ? <StatusBadge status="faturado" /> : null}
      {alertaSemAtendimento ? (
        <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 w-full">
          {MSG_ALERTA_FATURAMENTO_SEM_ATENDIMENTO}
        </p>
      ) : null}
      {!resumo.pode_faturar && resumo.motivo_bloqueio ? (
        <p className="text-xs text-amber-800 dark:text-amber-200">{resumo.motivo_bloqueio}</p>
      ) : null}
      {!resumo.pode_faturar &&
      faturamentosNfe.some((f) => f.status === 'PRONTO_PARA_NFE' && !f.nfe_saida_id) ? (
        <p className="text-xs text-muted-foreground">
          Já existe faturamento confirmado aguardando NF-e. Use <strong>Gerar NF-e rascunho</strong> na lista abaixo
          (não é necessário criar outro faturamento).
        </p>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {resumo.inconsistencias?.length ? (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 space-y-2">
          <p className="text-xs font-medium text-amber-900 dark:text-amber-100">Inconsistências detectadas</p>
          {resumo.inconsistencias.map((inc, idx) => (
            <p key={`${inc.codigo}-${idx}`} className="text-xs text-amber-800 dark:text-amber-200">
              {inc.mensagem}
            </p>
          ))}
          {avisoTotalDesatualizado ? (
            <button
              type="button"
              className="erp-btn-primary erp-btn-sm"
              disabled={loading}
              onClick={() => void recalcularTotaisPedido()}
            >
              Atualizar total do pedido (R$ {resumo.valor_total_pedido})
            </button>
          ) : null}
        </div>
      ) : null}

      {linhaEstorno ? (
        <div className="rounded-md border border-destructive/50 bg-destructive/5 px-4 py-3 space-y-2">
          <p className="text-sm font-medium text-foreground">Estorno antes da autorização SEFAZ</p>
          <p className="text-xs text-muted-foreground">
            O pedido está faturado, mas a NF-e vinculada ainda não foi autorizada. Estorne o faturamento para
            reabrir o pedido para edição. Nenhum evento será enviado à SEFAZ.
          </p>
          <div className="flex flex-wrap gap-2 items-center">
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm text-destructive border-destructive/50 inline-flex items-center gap-1"
              disabled={loading}
              onClick={() =>
                setEstornoModal({
                  faturamentoId: linhaEstorno.faturamento_id,
                  label: linhaFaturamentoNfeAmigavel(linhaEstorno),
                })
              }
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              Estornar faturamento e reabrir pedido
            </button>
            {linhaEstorno.nfe_saida_id ? (
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                onClick={() => navigate(`/nfe-saida?nfe=${linhaEstorno.nfe_saida_id}`)}
              >
                <ExternalLink className="h-3 w-3" aria-hidden />
                Abrir NF-e ({tituloResumoNfePedido(linhaEstorno)})
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {faturamentosNfe.length > 0 ? (
        <div className="rounded border border-border p-3 space-y-2">
          <p className="text-xs font-medium">Faturamentos e NF-e</p>
          {faturamentosNfe.map((f) => {
            const inconsistencia = mensagemNfeFaturamentoInconsistencia(f);
            return (
              <div
                key={f.faturamento_id}
                className="flex flex-col gap-1 text-sm border-b border-border/60 pb-2 last:border-0"
              >
                <div className="flex flex-wrap gap-2 items-center">
                  <span className="font-medium">
                    {linhaFaturamentoNfeAmigavel(f)}
                    {f.itens_count ? ` (${f.itens_count} itens)` : ''}
                  </span>
                  {f.nfe_saida_id ? (
                    <>
                      <span className="text-xs text-muted-foreground">{tituloResumoNfePedido(f)}</span>
                      {getNFeFiscalBadgeTokens(f).map((tok) => (
                        <StatusBadge key={tok} status={tok} />
                      ))}
                      {f.nfe_cstat ? (
                        <span className="text-xs text-muted-foreground">cStat {f.nfe_cstat}</span>
                      ) : null}
                      <button
                        type="button"
                        className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                        onClick={() => navigate(`/nfe-saida?nfe=${f.nfe_saida_id}`)}
                      >
                        <ExternalLink className="h-3 w-3" />
                        Abrir NF-e
                      </button>
                    </>
                  ) : f.status === 'PRONTO_PARA_NFE' ? (
                    <>
                      <button
                        type="button"
                        className="erp-btn-primary erp-btn-sm"
                        disabled={loading || bloqueiaGeracaoNfe}
                        title={
                          bloqueiaGeracaoNfe
                            ? 'Resolva as inconsistências bloqueantes antes de gerar a NF-e.'
                            : avisoTotalDesatualizado
                              ? 'O total salvo do pedido está desatualizado; a NF-e usará os itens do faturamento.'
                              : undefined
                        }
                        onClick={() => void gerarNfe(f.faturamento_id)}
                      >
                        Gerar NF-e rascunho
                      </button>
                      {f.pode_estornar_pre_autorizacao !== false ? (
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm text-destructive border-destructive/40"
                          disabled={loading}
                          onClick={() =>
                            setEstornoModal({
                              faturamentoId: f.faturamento_id,
                              label: linhaFaturamentoNfeAmigavel(f),
                            })
                          }
                        >
                          Estornar faturamento
                        </button>
                      ) : f.motivo_bloqueio_estorno ? (
                        <span className="text-xs text-muted-foreground">{f.motivo_bloqueio_estorno}</span>
                      ) : null}
                    </>
                  ) : f.status === 'GERADO_NFE' && !f.nfe_saida_id ? (
                    <>
                      <span className="text-xs text-amber-800 dark:text-amber-200">
                        {getFaturamentoStatusLabel(f.status)}
                      </span>
                      <button
                        type="button"
                        className="erp-btn-outline erp-btn-sm"
                        disabled={loading}
                        onClick={() => void repararVinculoNfe(f.faturamento_id)}
                      >
                        Reparar vínculo NF-e
                      </button>
                      {f.pode_estornar_pre_autorizacao !== false ? (
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm text-destructive border-destructive/40"
                          disabled={loading}
                          onClick={() =>
                            setEstornoModal({
                              faturamentoId: f.faturamento_id,
                              label: linhaFaturamentoNfeAmigavel(f),
                            })
                          }
                        >
                          Estornar faturamento
                        </button>
                      ) : null}
                    </>
                  ) : f.status === 'GERADO_NFE' ? (
                    <>
                      <span className="text-xs text-muted-foreground">{getFaturamentoStatusLabel(f.status)}</span>
                      {f.pode_estornar_pre_autorizacao !== false ? (
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm text-destructive border-destructive/40"
                          disabled={loading}
                          onClick={() =>
                            setEstornoModal({
                              faturamentoId: f.faturamento_id,
                              label: linhaFaturamentoNfeAmigavel(f),
                            })
                          }
                        >
                          Estornar faturamento
                        </button>
                      ) : (
                        <span className="text-xs text-amber-800 dark:text-amber-200">
                          {f.motivo_bloqueio_estorno ||
                            'NF-e autorizada — use fluxo fiscal de cancelamento (em preparação).'}
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="text-xs text-muted-foreground">{getFaturamentoStatusLabel(f.status)}</span>
                  )}
                </div>
                {inconsistencia ? (
                  <p className="text-xs text-amber-800 dark:text-amber-200">{inconsistencia}</p>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      <AtendimentoOperacionalResumo
        resumo={resumo.resumo_atendimento_operacional}
        compacto
      />

      <AlocacaoAtendimentoGerenciarSection
        pedidoVendaId={pedidoId}
        itens={itens}
        resumoInicial={resumo.resumo_atendimento_operacional}
        compacto
        onResumoAtualizado={() => void load()}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>
          <div className="text-xs text-muted-foreground">Valor pedido</div>
          <div className="font-medium">{formatCurrencyBRL(resumo.valor_total_pedido)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Valor faturado</div>
          <div className="font-medium">{formatCurrencyBRL(resumo.valor_faturado)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Valor pendente</div>
          <div className="font-medium">{formatCurrencyBRL(resumo.valor_pendente)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Itens (pend. / parc. / fat.)</div>
          <div className="font-medium">
            {resumo.itens_pendentes} / {resumo.itens_parciais} / {resumo.itens_faturados}
          </div>
        </div>
      </div>

      {resumo.faturamentos_rascunho.length > 0 ? (
        <div className="rounded border border-border p-3 space-y-2">
          <p className="text-xs font-medium">Rascunhos de faturamento</p>
          {resumo.faturamentos_rascunho.map((f) => (
            <div key={f.faturamento_id} className="flex flex-wrap gap-2 items-center text-sm">
              <span>
                #{f.faturamento_id} — {f.itens_count} item(ns)
                {f.observacao ? ` — ${f.observacao}` : ''}
              </span>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm"
                disabled={loading}
                onClick={() => void confirmar(f.faturamento_id)}
              >
                Confirmar faturamento
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                disabled={loading}
                onClick={() => void cancelarRascunho(f.faturamento_id)}
              >
                Cancelar rascunho
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {resumo.pode_faturar ? (
        <>
          <div>
            <label className="erp-label text-xs">Observação (opcional)</label>
            <input
              className="erp-input mt-1 w-full"
              value={observacao}
              onChange={(e) => setObservacao(e.target.value)}
              placeholder="Ex.: Faturamento parcial — lote 1"
            />
          </div>
          <div className="overflow-x-auto">
            <table className="erp-table text-sm">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Pedida</th>
                  <th>Faturada</th>
                  <th>Pendente</th>
                  <th>Status</th>
                  <th>Qtd. a faturar</th>
                </tr>
              </thead>
              <tbody>
                {resumo.itens.map((it) => (
                  <tr key={it.item_pedido_id}>
                    <td>
                      <span className="font-medium">{it.produto_codigo}</span>
                      <span className="block text-xs text-muted-foreground truncate max-w-[200px]">{it.descricao}</span>
                    </td>
                    <td>{it.quantidade_pedida}</td>
                    <td>{it.quantidade_faturada}</td>
                    <td>{it.quantidade_pendente}</td>
                    <td>
                      <span className={statusBadge(it.status_item)}>{it.status_item}</span>
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.001"
                        min={0}
                        max={parseFloat(it.quantidade_disponivel) || undefined}
                        className="erp-input h-8 w-24"
                        disabled={parseFloat(it.quantidade_disponivel) <= 0}
                        value={qtyFat[it.item_pedido_id] ?? ''}
                        onChange={(e) =>
                          setQtyFat((p) => ({ ...p, [it.item_pedido_id]: e.target.value }))
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2">
            <button type="button" className="erp-btn-primary" disabled={loading} onClick={() => void criarFaturamento()}>
              Criar faturamento
            </button>
            <button type="button" className="erp-btn-outline" disabled={loading} onClick={() => void load()}>
              Atualizar resumo
            </button>
          </div>
        </>
      ) : null}
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
        loading={loading}
        onConfirm={async (motivo) => {
          if (!estornoModal) return;
          await estornarFaturamento(estornoModal.faturamentoId, motivo);
          setEstornoModal(null);
        }}
      />
    </div>
  );
}
