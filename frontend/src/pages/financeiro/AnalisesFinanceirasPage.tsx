import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState, LoadingState } from '@/components/list/ListStates';
import { AnaliseFinanceiraIndicadores } from '@/components/financeiro/AnaliseFinanceiraIndicadores';
import {
  analiseFinanceiraService,
  type AnaliseFinanceiraProposta,
} from '@/services/api/analiseFinanceira';
import { apiErrorMessage } from '@/services/api/config';
import { formatMoneyBRL } from '@/lib/money';
import { labelStatusAnaliseFinanceira } from '@/components/comercial/PropostaAnaliseFinanceiraPanel';

const FILTROS = [
  '',
  'PENDENTE',
  'EM_ANALISE',
  'APROVADA',
  'APROVADA_COM_AJUSTE',
  'DEVOLVIDA_PARA_AJUSTE',
  'NAO_APROVADA',
  'EXPIRADA',
];

export default function AnalisesFinanceirasPage() {
  const [status, setStatus] = useState('PENDENTE');
  const [items, setItems] = useState<AnaliseFinanceiraProposta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AnaliseFinanceiraProposta | null>(null);
  const [justificativa, setJustificativa] = useState('');
  const [diasAjuste, setDiasAjuste] = useState('0,30');
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await analiseFinanceiraService.list(status ? { status } : undefined);
      setItems(data.results || []);
    } catch (e) {
      setError(apiErrorMessage(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  const abrir = async (id: number) => {
    setActionError(null);
    try {
      setSelected(await analiseFinanceiraService.getById(id));
    } catch (e) {
      setActionError(apiErrorMessage(e));
    }
  };

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      await load();
      if (selected) setSelected(await analiseFinanceiraService.getById(selected.id));
    } catch (e) {
      setActionError(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const podeDecidir = Boolean(selected?.permissoes?.pode_decidir);

  return (
    <div>
      <PageHeader title="Análises Financeiras" />
      <p className="text-sm text-muted-foreground mb-4">
        Fila de liberação financeira de Propostas Comerciais. Não altera Cliente, Pedido ou Contas a Receber.
      </p>

      <div className="flex flex-wrap gap-2 mb-4" data-testid="analise-fin-fila-filtros">
        {FILTROS.map((f) => (
          <button
            key={f || 'todos'}
            type="button"
            className={status === f ? 'erp-btn-primary erp-btn-sm' : 'erp-btn-outline erp-btn-sm'}
            onClick={() => setStatus(f)}
          >
            {f ? labelStatusAnaliseFinanceira(f) : 'Todos'}
          </button>
        ))}
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!loading && !error && items.length === 0 ? <EmptyState message="Nenhuma análise neste filtro." /> : null}

      {!loading && items.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border mb-6" data-testid="analise-fin-fila">
          <table className="erp-table w-full text-sm" data-mobile-table-mode="cards">
            <thead>
              <tr>
                <th>Proposta</th>
                <th>Cliente</th>
                <th>Valor</th>
                <th>Condição</th>
                <th>Status</th>
                <th>Solicitada em</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td className="font-mono">{a.proposta_numero}</td>
                  <td>{a.cliente_nome}</td>
                  <td>{formatMoneyBRL(Number(a.valor_solicitado))}</td>
                  <td>{a.condicao_solicitada?.texto || '—'}</td>
                  <td>{labelStatusAnaliseFinanceira(a.status)}</td>
                  <td>{new Date(a.solicitada_em).toLocaleString('pt-BR')}</td>
                  <td>
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                      data-testid={`analise-fin-abrir-${a.id}`}
                      onClick={() => void abrir(a.id)}
                    >
                      Abrir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {selected ? (
        <div className="rounded-lg border border-border p-4 space-y-3" data-testid="analise-fin-detalhe">
          <div className="flex flex-col sm:flex-row sm:justify-between items-start sm:items-center gap-2">
            <h2 className="font-semibold">
              Análise #{selected.id} · Proposta{' '}
              <Link className="text-primary underline" to={`/propostas`}>
                {selected.proposta_numero}
              </Link>
            </h2>
            <button type="button" className="erp-btn-ghost erp-btn-sm w-full sm:w-auto" onClick={() => setSelected(null)}>
              Fechar
            </button>
          </div>
          <p className="text-sm">
            Status: {labelStatusAnaliseFinanceira(selected.status)} · Valor{' '}
            {formatMoneyBRL(Number(selected.valor_solicitado))} · Condição{' '}
            {selected.condicao_solicitada?.texto || '—'}
          </p>
          {selected.observacao_vendedor ? (
            <p className="text-sm text-muted-foreground">Obs. vendedor: {selected.observacao_vendedor}</p>
          ) : null}

          <AnaliseFinanceiraIndicadores
            snapshot={selected.snapshot_indicadores}
            analiseId={selected.id}
            podeVerProtestoManual={Boolean(selected.permissoes?.pode_ver_protesto_manual)}
            podeRegistrarProtestoManual={Boolean(selected.permissoes?.pode_registrar_protesto_manual)}
            negociacao={{
              proposta_numero: selected.proposta_numero,
              cliente_nome: selected.cliente_nome,
              valor_solicitado: selected.valor_solicitado,
              condicao: selected.condicao_solicitada?.texto,
              vendedor: (selected.snapshot_proposta as { vendedor?: string } | undefined)?.vendedor,
              solicitada_em: selected.solicitada_em,
              data_corte:
                (selected.snapshot_indicadores as { data_corte?: string } | undefined)?.data_corte ||
                (selected.snapshot_proposta as { data_corte?: string } | undefined)?.data_corte,
            }}
          />

          {actionError ? (
            <p className="text-sm text-destructive" role="alert" data-testid="analise-fin-action-error">
              {actionError}
            </p>
          ) : null}

          {podeDecidir && ['PENDENTE', 'EM_ANALISE'].includes(selected.status) ? (
            <div className="space-y-2 border-t border-border pt-3" data-testid="analise-fin-acoes">
              <textarea
                className="erp-input min-h-[70px] w-full"
                placeholder="Justificativa (obrigatória em ajuste / devolução / não aprovação)"
                value={justificativa}
                onChange={(e) => setJustificativa(e.target.value)}
                data-testid="analise-fin-justificativa"
              />
              <div className="flex flex-col sm:flex-row flex-wrap gap-2">
                {selected.status === 'PENDENTE' ? (
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                    disabled={busy}
                    data-testid="analise-fin-assumir"
                    onClick={() => void run(() => analiseFinanceiraService.iniciar(selected.id))}
                  >
                    Assumir
                  </button>
                ) : null}
                <button
                  type="button"
                  className="erp-btn-primary erp-btn-sm w-full sm:w-auto"
                  disabled={busy}
                  data-testid="analise-fin-aprovar"
                  onClick={() => void run(() => analiseFinanceiraService.aprovar(selected.id))}
                >
                  Aprovar como solicitado
                </button>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                  disabled={busy}
                  data-testid="analise-fin-aprovar-avista"
                  onClick={() =>
                    void run(() =>
                      analiseFinanceiraService.aprovarComAjuste(selected.id, {
                        dias_aprovados: [0],
                        justificativa: justificativa || 'Somente à vista',
                      }),
                    )
                  }
                >
                  Aprovar à vista
                </button>
                <input
                  className="erp-input w-full sm:w-28"
                  value={diasAjuste}
                  onChange={(e) => setDiasAjuste(e.target.value)}
                  title="Dias do ajuste, ex.: 0,30"
                  data-testid="analise-fin-dias-ajuste"
                />
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                  disabled={busy}
                  data-testid="analise-fin-aprovar-ajuste"
                  onClick={() =>
                    void run(() =>
                      analiseFinanceiraService.aprovarComAjuste(selected.id, {
                        dias_aprovados: diasAjuste.split(/[,\s/]+/).filter(Boolean).map(Number),
                        justificativa,
                      }),
                    )
                  }
                >
                  Aprovar com ajuste
                </button>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                  disabled={busy}
                  data-testid="analise-fin-devolver"
                  onClick={() => void run(() => analiseFinanceiraService.devolver(selected.id, justificativa))}
                >
                  Devolver
                </button>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm text-destructive w-full sm:w-auto"
                  disabled={busy}
                  data-testid="analise-fin-nao-aprovar"
                  onClick={() => void run(() => analiseFinanceiraService.naoAprovar(selected.id, justificativa))}
                >
                  Não aprovar
                </button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
