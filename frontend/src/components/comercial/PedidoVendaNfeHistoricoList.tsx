import { ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PedidoVendaFiscalNfeAcoes } from '@/components/comercial/PedidoVendaFiscalNfeAcoes';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { formatDateBr } from '@/lib/dateBr';
import { formatCurrencyBRL } from '@/lib/formatBr';
import { formatDateTimeBr } from '@/lib/nfeSaidaUi';
import {
  badgeHistoricoNfe,
  getHistoricoNfePapelBadge,
  historicoNfeTitulo,
  isNfeCanceladaOperacional,
} from '@/lib/pedidoVendaModalUi';
import type { HistoricoNfeSaidaPedido } from '@/types';

type Props = {
  historico: HistoricoNfeSaidaPedido[];
  /** Texto introdutório opcional. */
  intro?: string;
  compacto?: boolean;
};

export function PedidoVendaNfeHistoricoList({ historico, intro, compacto = false }: Props) {
  const navigate = useNavigate();

  if (!historico.length) {
    return (
      <p className="text-xs text-muted-foreground py-2">
        Nenhuma NF-e gerada para este pedido ainda.
      </p>
    );
  }

  return (
    <div className={compacto ? 'space-y-2' : 'space-y-3'}>
      {intro ? <p className="text-xs text-muted-foreground">{intro}</p> : null}
      <ul className="space-y-3">
        {historico.map((h) => {
          const badge = badgeHistoricoNfe(h);
          const cancelada = isNfeCanceladaOperacional({ nfe_saida_status: h.status });
          const papelBadge = getHistoricoNfePapelBadge(h.papel_fiscal);
          const saldoLiberado = Boolean(h.efeitos_cancelamento_aplicados_em);

          return (
            <li
              key={h.nfe_saida_id}
              className={`rounded-md border p-3 space-y-2 ${
                h.papel_fiscal === 'ativa'
                  ? 'border-emerald-500/40 bg-emerald-500/5'
                  : h.papel_fiscal === 'historico'
                    ? 'border-destructive/30 bg-destructive/5'
                    : 'border-border/80'
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="space-y-1.5 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-sm">{historicoNfeTitulo(h)}</span>
                    <span className={badge.className}>{badge.label}</span>
                    {papelBadge ? <StatusBadge status={papelBadge} /> : null}
                    {cancelada ? <StatusBadge status="cancelada" /> : null}
                  </div>
                  {h.mensagem_papel_fiscal ? (
                    <p className="text-xs text-muted-foreground">{h.mensagem_papel_fiscal}</p>
                  ) : null}
                </div>
                <span className="text-xs text-muted-foreground shrink-0">
                  {formatDateBr(h.data)} · {formatCurrencyBRL(h.valor_total)}
                </span>
              </div>

              <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-1 text-xs">
                {h.numero_fiscal ? (
                  <>
                    <dt className="text-muted-foreground">Número</dt>
                    <dd className="text-foreground">{h.numero_fiscal}</dd>
                  </>
                ) : null}
                {h.serie_fiscal ? (
                  <>
                    <dt className="text-muted-foreground">Série</dt>
                    <dd className="text-foreground">{h.serie_fiscal}</dd>
                  </>
                ) : null}
                {h.status_fiscal_label ? (
                  <>
                    <dt className="text-muted-foreground">Status fiscal</dt>
                    <dd className="text-foreground">{h.status_fiscal_label}</dd>
                  </>
                ) : null}
                {h.ambiente_label ? (
                  <>
                    <dt className="text-muted-foreground">Ambiente</dt>
                    <dd className="text-foreground">{h.ambiente_label}</dd>
                  </>
                ) : null}
                {h.chave_acesso_resumida ? (
                  <>
                    <dt className="text-muted-foreground">Chave</dt>
                    <dd className="text-foreground font-mono">{h.chave_acesso_resumida}</dd>
                  </>
                ) : null}
                {h.protocolo_autorizacao ? (
                  <>
                    <dt className="text-muted-foreground">Protocolo autorização</dt>
                    <dd className="text-foreground">{h.protocolo_autorizacao}</dd>
                  </>
                ) : null}
                {h.cstat_autorizacao ? (
                  <>
                    <dt className="text-muted-foreground">cStat</dt>
                    <dd className="text-foreground">{h.cstat_autorizacao}</dd>
                  </>
                ) : null}
                {h.faturamento_id ? (
                  <>
                    <dt className="text-muted-foreground">Faturamento</dt>
                    <dd className="text-foreground">
                      {h.numero_faturamento ? `${h.numero_faturamento} (#${h.faturamento_id})` : `#${h.faturamento_id}`}
                    </dd>
                  </>
                ) : null}
                {h.numero_interno ? (
                  <>
                    <dt className="text-muted-foreground">Ref. interna</dt>
                    <dd className="text-foreground">{h.numero_interno}</dd>
                  </>
                ) : null}
                {h.protocolo_cancelamento ? (
                  <>
                    <dt className="text-muted-foreground">Protocolo cancelamento</dt>
                    <dd className="text-foreground">{h.protocolo_cancelamento}</dd>
                  </>
                ) : null}
                {h.cancelada_em ? (
                  <>
                    <dt className="text-muted-foreground">Cancelada em</dt>
                    <dd className="text-foreground">{formatDateTimeBr(h.cancelada_em)}</dd>
                  </>
                ) : null}
                {h.motivo_cancelamento ? (
                  <>
                    <dt className="text-muted-foreground sm:col-span-1">Motivo cancelamento</dt>
                    <dd className="text-foreground sm:col-span-2">{h.motivo_cancelamento}</dd>
                  </>
                ) : null}
              </dl>

              {saldoLiberado && cancelada ? (
                <p className="text-xs text-emerald-800 dark:text-emerald-200 rounded-md bg-emerald-600/10 px-2 py-1.5">
                  Saldo comercial liberado — pedido apto para nova emissão fiscal pelo fluxo normal.
                </p>
              ) : null}

              <div className="flex flex-wrap gap-2 pt-1">
                <PedidoVendaFiscalNfeAcoes
                  nfeSaidaId={h.nfe_saida_id}
                  nfeStatusEmissaoSefaz={h.status_emissao_sefaz}
                  nfeSaidaStatus={h.status}
                />
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                  onClick={() => navigate(`/nfe-saida?nfe=${h.nfe_saida_id}`)}
                >
                  <ExternalLink className="h-3 w-3" aria-hidden />
                  Ver histórico fiscal
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
