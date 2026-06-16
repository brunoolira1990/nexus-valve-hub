import { useCallback, useEffect, useState } from 'react';
import { History, Loader2, RefreshCw, Scale, ShieldAlert } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { apiErrorMessage } from '@/services/api/config';
import {
  nfeSaidasService,
  type NFeSaidaEfeitosEmissaoResponse,
  type NFeSaidaEfeitosEvento,
} from '@/services/api/fiscal';
import {
  badgeNfeSaidaStatus,
  formatDateTimeBr,
  labelTipoEventoNFe,
  resumoEventoCurto,
} from '@/lib/nfeSaidaUi';
import { eventoCceEstaVigente, obterCceVigenteDosEventos } from '@/lib/nfeCartaCorrecaoPreview';

type Props = {
  nfeSaidaId: number;
  nfeNumero?: string;
  nfeStatus?: string;
  /** Carrega política/eventos ao montar (ex.: modal NF-e aberto). */
  autoLoad?: boolean;
  compact?: boolean;
  /** Layout simplificado na aba Histórico do modal de conferência. */
  conferenciaLayout?: boolean;
  onNfeAtualizada?: () => void | Promise<void>;
};

export function NFeSaidaEfeitosPanel({
  nfeSaidaId,
  nfeNumero,
  nfeStatus,
  autoLoad = false,
  compact = false,
  conferenciaLayout = false,
  onNfeAtualizada,
}: Props) {
  const [efeitos, setEfeitos] = useState<NFeSaidaEfeitosEmissaoResponse | null>(null);
  const [eventos, setEventos] = useState<NFeSaidaEfeitosEvento[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [motivoCancelamento, setMotivoCancelamento] = useState('');

  const carregar = useCallback(async () => {
    if (!nfeSaidaId) return;
    setLoading(true);
    setError(null);
    try {
      const [pol, ev] = await Promise.all([
        nfeSaidasService.efeitosEmissao(nfeSaidaId),
        nfeSaidasService.eventosNFeSaida(nfeSaidaId),
      ]);
      setEfeitos(pol);
      setEventos(ev.eventos);
    } catch (err) {
      setEfeitos(null);
      setEventos([]);
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [nfeSaidaId]);

  useEffect(() => {
    if (autoLoad && nfeSaidaId) void carregar();
  }, [autoLoad, nfeSaidaId, carregar]);

  const statusExib = efeitos?.status || nfeStatus || '';
  const badge = badgeNfeSaidaStatus(statusExib);
  const canceladaInterna = statusExib.toUpperCase().includes('CANCELADA');
  const autorizadaInterna =
    statusExib.toUpperCase() === 'AUTORIZADA_INTERNA' || Boolean(efeitos && !efeitos.pode_aplicar_autorizacao);

  const handleAutorizacao = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await nfeSaidasService.aplicarEfeitosAutorizacaoInterna(
        nfeSaidaId,
        'Simulação interna dos efeitos da autorização.',
      );
      setAuthModalOpen(false);
      await carregar();
      await onNfeAtualizada?.();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelamento = async () => {
    const motivo = motivoCancelamento.trim();
    if (!motivo) {
      setError('Informe o motivo do cancelamento interno.');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await nfeSaidasService.cancelarInterno(nfeSaidaId, motivo);
      setCancelModalOpen(false);
      setMotivoCancelamento('');
      await carregar();
      await onNfeAtualizada?.();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className={`space-y-3 ${compact ? 'text-sm' : ''}`}>
      {!conferenciaLayout ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium text-sm flex items-center gap-1.5">
            <Scale className="h-4 w-4" />
            Efeitos e histórico
          </h3>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              disabled={loading}
              onClick={() => void carregar()}
            >
              {loading ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1 inline" />
              ) : (
                <RefreshCw className="h-3 w-3 mr-1 inline" />
              )}
              Atualizar efeitos
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm"
          disabled={loading}
          onClick={() => void carregar()}
        >
          {loading ? <Loader2 className="h-3 w-3 animate-spin mr-1 inline" /> : <RefreshCw className="h-3 w-3 mr-1 inline" />}
          Atualizar histórico
        </button>
      )}

      <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
        {conferenciaLayout
          ? 'Simulação interna — sem SEFAZ, protocolo, estoque ou financeiro real.'
          : 'Simulação operacional pré-SEFAZ. Não transmite para a SEFAZ, não gera protocolo, não movimenta estoque nem financeiro nesta fase.'}
      </p>

      {error ? (
        <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}

      {!efeitos && !loading ? (
        <p className="text-xs text-muted-foreground">Clique em «Atualizar efeitos» para carregar a política e o histórico.</p>
      ) : null}

      {loading && !efeitos ? (
        <p className="text-xs text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Carregando…
        </p>
      ) : null}

      {efeitos ? (
        <>
          <div className="rounded-md border border-border p-3 space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status operacional</h4>
            <div className="flex flex-wrap items-center gap-2">
              <span className={badge.className}>{badge.label}</span>
              {nfeNumero ? <span className="text-sm font-medium">{nfeNumero}</span> : null}
            </div>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <div>
                <dt className="text-muted-foreground">Pedido vinculado</dt>
                <dd>{efeitos.pedido_id ? `#${efeitos.pedido_id}` : '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Faturamento vinculado</dt>
                <dd>{efeitos.faturamento_id ? `#${efeitos.faturamento_id}` : '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Autorização interna</dt>
                <dd>{autorizadaInterna ? 'Efeitos aplicados' : 'Pendente (simulação)'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Cancelamento interno</dt>
                <dd>{canceladaInterna ? 'Cancelada — saldo do pedido pode ter sido liberado' : 'Não cancelada'}</dd>
              </div>
            </dl>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="rounded-md border border-border p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide mb-2">Na autorização</h4>
              <ul className="space-y-1 text-xs list-disc pl-4 text-muted-foreground">
                {efeitos.efeitos_autorizacao.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-md border border-border p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide mb-2">No cancelamento</h4>
              <ul className="space-y-1 text-xs list-disc pl-4 text-muted-foreground">
                {efeitos.efeitos_cancelamento.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Estoque: {efeitos.estoque.mensagem} · Financeiro: {efeitos.financeiro.mensagem}
          </p>

          {efeitos.alertas?.length ? (
            <ul className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 list-disc pl-5">
              {efeitos.alertas.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          ) : null}

          {(efeitos.pode_aplicar_autorizacao || efeitos.pode_cancelar) && (
            <div className="flex flex-wrap gap-2 pt-1 border-t border-border">
              {efeitos.pode_aplicar_autorizacao ? (
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm border-amber-500/50 text-amber-900 dark:text-amber-100"
                  disabled={actionLoading}
                  onClick={() => setAuthModalOpen(true)}
                >
                  Aplicar autorização interna
                </button>
              ) : null}
              {efeitos.pode_cancelar ? (
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm border-destructive/40 text-destructive"
                  disabled={actionLoading}
                  onClick={() => setCancelModalOpen(true)}
                >
                  Cancelar interno
                </button>
              ) : null}
            </div>
          )}

          <div className="rounded-md border border-border p-3">
            <h4 className="text-xs font-semibold uppercase tracking-wide mb-2 flex items-center gap-1">
              <History className="h-3.5 w-3.5" />
              Histórico de eventos ({eventos.length})
            </h4>
            <p className="text-xs text-muted-foreground mb-2">Ordem: mais recente primeiro.</p>
            {(() => {
              const cceVigente = obterCceVigenteDosEventos(eventos);
              if (!cceVigente) return null;
              const seq = cceVigente.resumo?.sequencia_evento ?? cceVigente.resumo?.n_seq_evento;
              return (
                <div className="mb-3 rounded-md border border-emerald-600/40 bg-emerald-600/5 p-2 text-xs">
                  <p className="font-medium text-emerald-800 dark:text-emerald-200 flex flex-wrap items-center gap-1.5">
                    CC-e vigente
                    <span className="erp-badge-success text-[10px]">Autorizada</span>
                    {seq ? <span className="text-muted-foreground font-normal">· Seq. {String(seq)}</span> : null}
                  </p>
                  {cceVigente.resumo?.texto_correcao ? (
                    <p className="text-muted-foreground mt-1 whitespace-pre-wrap line-clamp-3">
                      {String(cceVigente.resumo.texto_correcao)}
                    </p>
                  ) : null}
                </div>
              );
            })()}
            {eventos.length === 0 ? (
              <p className="text-xs text-muted-foreground">Nenhum evento registrado ainda.</p>
            ) : (
              <ul className="space-y-2 max-h-48 overflow-y-auto">
                {eventos.map((ev) => (
                  <li key={ev.id} className="text-xs border-b border-border/50 pb-2 last:border-0">
                    <div className="font-medium flex flex-wrap items-center gap-1.5">
                      {labelTipoEventoNFe(ev.tipo_evento)}
                      {ev.tipo_evento === 'CARTA_CORRECAO_EMITIDA' && eventoCceEstaVigente(ev, eventos) ? (
                        <span className="erp-badge-success text-[10px]">Vigente</span>
                      ) : null}
                    </div>
                    <div className="text-muted-foreground">
                      {formatDateTimeBr(ev.criado_em)}
                      {ev.criado_por_nome ? ` · ${ev.criado_por_nome}` : ''}
                    </div>
                    {(ev.status_anterior || ev.status_novo) && (
                      <div>
                        {ev.status_anterior || '—'} → {ev.status_novo || '—'}
                      </div>
                    )}
                    {ev.observacao ? <div className="mt-0.5">{ev.observacao}</div> : null}
                    {resumoEventoCurto(ev.resumo) ? (
                      <div className="text-muted-foreground">{resumoEventoCurto(ev.resumo)}</div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : null}

      <Modal
        isOpen={authModalOpen}
        onClose={() => !actionLoading && setAuthModalOpen(false)}
        title="Autorização interna (simulação)"
        size="md"
      >
        <div className="space-y-3 text-sm">
          <p className="flex gap-2 text-amber-800 dark:text-amber-200">
            <ShieldAlert className="h-5 w-5 shrink-0" />
            Esta ação simula internamente os efeitos de uma autorização. Ela não transmite para a SEFAZ e não gera
            protocolo fiscal.
          </p>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="erp-btn-outline"
              disabled={actionLoading}
              onClick={() => setAuthModalOpen(false)}
            >
              Voltar
            </button>
            <button
              type="button"
              className="erp-btn-primary"
              disabled={actionLoading}
              onClick={() => void handleAutorizacao()}
            >
              {actionLoading ? 'Aplicando…' : 'Confirmar simulação'}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={cancelModalOpen}
        onClose={() => !actionLoading && setCancelModalOpen(false)}
        title="Cancelamento interno (simulação)"
        size="md"
      >
        <div className="space-y-3 text-sm">
          <p className="text-amber-800 dark:text-amber-200">
            Esta ação cancela internamente a NF-e e estorna o faturamento vinculado no pedido. Não cancela na SEFAZ.
          </p>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Motivo (obrigatório)</label>
            <textarea
              className="erp-input w-full min-h-[80px] text-sm"
              value={motivoCancelamento}
              onChange={(e) => setMotivoCancelamento(e.target.value)}
              placeholder="Ex.: Nota emitida com dados incorretos."
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="erp-btn-outline"
              disabled={actionLoading}
              onClick={() => setCancelModalOpen(false)}
            >
              Voltar
            </button>
            <button
              type="button"
              className="erp-btn-primary bg-destructive hover:bg-destructive/90"
              disabled={actionLoading}
              onClick={() => void handleCancelamento()}
            >
              {actionLoading ? 'Cancelando…' : 'Confirmar cancelamento interno'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
