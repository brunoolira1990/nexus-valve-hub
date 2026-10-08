import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock, ShieldAlert } from 'lucide-react';
import {
  analiseFinanceiraService,
  type AnaliseFinanceiraProposta,
  type SituacaoAnaliseFinanceira,
} from '@/services/api/analiseFinanceira';
import { apiErrorMessage } from '@/services/api/config';
import { formatMoneyBRL } from '@/lib/money';

const STATUS_LABEL: Record<string, string> = {
  PENDENTE: 'Aguardando análise',
  EM_ANALISE: 'Em análise',
  APROVADA: 'Aprovada',
  APROVADA_COM_AJUSTE: 'Aprovada com ajuste',
  DEVOLVIDA_PARA_AJUSTE: 'Devolvida',
  NAO_APROVADA: 'Não aprovada',
  EXPIRADA: 'Expirada',
  SUBSTITUIDA: 'Substituída',
};

type Props = {
  propostaId?: number | null;
  enabled?: boolean;
};

export function PropostaAnaliseFinanceiraPanel({ propostaId, enabled = true }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SituacaoAnaliseFinanceira | null>(null);
  const [obs, setObs] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!propostaId || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      setData(await analiseFinanceiraService.situacaoProposta(propostaId));
    } catch (e) {
      setError(apiErrorMessage(e, { fallback: 'Não foi possível carregar a análise financeira.' }));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [propostaId, enabled]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!propostaId) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="analise-fin-sem-proposta">
        Salve a proposta para solicitar análise financeira.
      </p>
    );
  }

  const situacao = data?.situacao;
  const ultima = data?.ultima as AnaliseFinanceiraProposta | null;
  const statusTxt = ultima ? STATUS_LABEL[ultima.status] || ultima.status : 'Não solicitada';
  const podeSolicitar = Boolean(situacao?.permissoes?.pode_solicitar);

  const solicitar = async () => {
    setSaving(true);
    setError(null);
    try {
      await analiseFinanceiraService.solicitar(propostaId, obs);
      setObs('');
      await load();
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-md border border-border p-3 space-y-3" data-testid="analise-fin-panel">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <ShieldAlert className="h-4 w-4" />
            Liberação financeira
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Obrigatória apenas para converter proposta com pagamento futuro em Pedido de Venda.
          </p>
        </div>
        <span className="text-xs font-medium px-2 py-1 rounded bg-muted" data-testid="analise-fin-status">
          {statusTxt}
        </span>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Carregando…</p> : null}
      {error ? (
        <p className="text-sm text-destructive" role="alert" data-testid="analise-fin-erro">
          {error}
        </p>
      ) : null}

      {situacao?.avaliacao?.a_vista ? (
        <p className="text-sm flex items-center gap-2 text-emerald-700">
          <CheckCircle2 className="h-4 w-4" /> À vista — conversão sem análise neste MVP.
        </p>
      ) : null}

      {situacao?.reanalise_necessaria ? (
        <p className="text-sm flex items-center gap-2 text-amber-800" data-testid="analise-fin-reanalise">
          <AlertTriangle className="h-4 w-4" />
          {situacao.avaliacao.motivo}
        </p>
      ) : null}

      {situacao?.avaliacao?.valida && !situacao.avaliacao.a_vista ? (
        <p className="text-sm flex items-center gap-2 text-emerald-700">
          <CheckCircle2 className="h-4 w-4" /> Liberação válida para a condição e valor atuais.
        </p>
      ) : null}

      {ultima ? (
        <div className="text-sm space-y-1 bg-muted/30 rounded p-2" data-testid="analise-fin-resumo">
          <p>
            Solicitada: {ultima.condicao_solicitada?.texto || '—'} ·{' '}
            {formatMoneyBRL(Number(ultima.valor_solicitado))}
          </p>
          {ultima.condicao_aprovada?.dias?.length ? (
            <p>
              Aprovada: {ultima.condicao_aprovada.texto} · máx.{' '}
              {ultima.valor_maximo_aprovado != null
                ? formatMoneyBRL(Number(ultima.valor_maximo_aprovado))
                : '—'}
              {ultima.valida_ate
                ? ` · válida até ${new Date(`${ultima.valida_ate}T12:00:00`).toLocaleDateString('pt-BR')}`
                : ''}
            </p>
          ) : null}
          {ultima.justificativa_decisao ? (
            <p className="text-muted-foreground">Justificativa: {ultima.justificativa_decisao}</p>
          ) : null}
        </div>
      ) : null}

      {!loading && data && podeSolicitar ? (
        <div className="space-y-2">
          <label className="erp-label">Observação comercial (opcional)</label>
          <textarea
            className="erp-input min-h-[70px]"
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            placeholder="Contexto para o Financeiro…"
          />
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
            disabled={saving || loading}
            onClick={() => void solicitar()}
            data-testid="analise-fin-solicitar"
          >
            <Clock className="h-3.5 w-3.5" />
            {saving ? 'Solicitando…' : 'Solicitar análise financeira'}
          </button>
        </div>
      ) : null}
      {!loading && data && !podeSolicitar ? (
        <p className="text-sm text-muted-foreground" data-testid="analise-fin-sem-permissao-solicitar">
          Sem permissão para solicitar análise financeira.
        </p>
      ) : null}
    </section>
  );
}

export function labelStatusAnaliseFinanceira(status: string): string {
  return STATUS_LABEL[status] || status;
}
