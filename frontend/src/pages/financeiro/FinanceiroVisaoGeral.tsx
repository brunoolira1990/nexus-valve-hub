import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowDownCircle,
  ArrowUpCircle,
  Calendar,
  Coins,
  Scale,
  Wallet,
} from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/list/ListStates';
import { formatMoneyBRL } from '@/lib/money';
import { formatDateBr } from '@/lib/dateBr';
import {
  financeiroService,
  type FinanceiroResumo,
  type FinanceiroResumoMetrica,
} from '@/services/api/financeiro';
import { apiErrorMessage } from '@/services/api/config';

type Periodo = 'mes' | 'hoje' | 'semana' | 'proximos_7' | 'proximos_30';

function linkListagem(modo: 'receber' | 'pagar', params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  const base = modo === 'receber' ? '/financeiro/contas-receber' : '/financeiro/contas-pagar';
  return q ? `${base}?${q}` : base;
}

function ResumoCard({
  titulo,
  metrica,
  icon: Icon,
  tone,
  to,
  acao,
}: {
  titulo: string;
  metrica: FinanceiroResumoMetrica;
  icon: React.ElementType;
  tone: 'receber' | 'pagar' | 'neutro' | 'alerta';
  to?: string;
  acao?: string;
}) {
  const toneClass =
    tone === 'receber'
      ? 'border-emerald-200 bg-emerald-50/80 dark:bg-emerald-950/20'
      : tone === 'pagar'
        ? 'border-rose-200 bg-rose-50/80 dark:bg-rose-950/20'
        : tone === 'alerta'
          ? 'border-amber-200 bg-amber-50/80 dark:bg-amber-950/20'
          : 'border-border bg-card';
  const inner = (
    <div className={`erp-card p-4 border ${toneClass} h-full flex flex-col`}>
      <div className="flex items-start justify-between gap-2 flex-1">
        <div>
          <p className="text-sm text-muted-foreground">{titulo}</p>
          <p className="text-2xl font-bold mt-1 tabular-nums">{formatMoneyBRL(metrica.valor)}</p>
          {metrica.quantidade > 0 ? (
            <p className="text-xs text-muted-foreground mt-1">{metrica.quantidade} título(s)</p>
          ) : null}
        </div>
        <Icon className="h-5 w-5 text-muted-foreground shrink-0" />
      </div>
      {acao && to ? (
        <span className="text-xs text-primary mt-3 inline-block">{acao} →</span>
      ) : null}
    </div>
  );
  if (to) {
    return (
      <Link to={to} className="block hover:opacity-95 transition-opacity">
        {inner}
      </Link>
    );
  }
  return inner;
}

const FinanceiroVisaoGeral = () => {
  const [resumo, setResumo] = useState<FinanceiroResumo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [periodo, setPeriodo] = useState<Periodo>('mes');

  const carregar = useCallback(() => {
    setLoading(true);
    setError(null);
    void financeiroService
      .getResumo({ periodo })
      .then(setResumo)
      .catch((e) => setError(apiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [periodo]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const alertaLinks = (
    acao: string,
  ): { label: string; to: string }[] | undefined => {
    switch (acao) {
      case 'ver_vencidos':
        return [
          { label: 'Ver a receber', to: linkListagem('receber', { vencimento: 'vencidos' }) },
          { label: 'Ver a pagar', to: linkListagem('pagar', { vencimento: 'vencidos' }) },
        ];
      case 'ver_hoje':
        return [
          { label: 'Ver a receber', to: linkListagem('receber', { vencimento: 'hoje' }) },
          { label: 'Ver a pagar', to: linkListagem('pagar', { vencimento: 'hoje' }) },
        ];
      case 'ver_origem_cancelada':
        return [
          {
            label: 'Ver a receber',
            to: linkListagem('receber', { origem_fiscal_cancelada: '1' }),
          },
          { label: 'Ver a pagar', to: linkListagem('pagar', { origem_fiscal_cancelada: '1' }) },
        ];
      case 'ver_sem_categoria':
        return [
          { label: 'Ver a receber', to: linkListagem('receber', { sem_categoria: '1' }) },
          { label: 'Ver a pagar', to: linkListagem('pagar', { sem_categoria: '1' }) },
        ];
      case 'ver_sem_conta':
        return [
          { label: 'Ver a receber', to: linkListagem('receber', { sem_conta_prevista: '1' }) },
          { label: 'Ver a pagar', to: linkListagem('pagar', { sem_conta_prevista: '1' }) },
        ];
      case 'ver_creditos':
        return [{ label: 'Ver créditos', to: '/financeiro/creditos' }];
      default:
        return undefined;
    }
  };

  return (
    <div>
      <PageHeader
        title="Financeiro"
        description="Acompanhe recebimentos, pagamentos, vencimentos e alertas."
      />

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <label className="text-sm flex flex-col sm:flex-row sm:items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          Período
          <select
            className="erp-input erp-input-sm w-full sm:w-auto"
            value={periodo}
            onChange={(e) => setPeriodo(e.target.value as Periodo)}
          >
            <option value="mes">Este mês</option>
            <option value="hoje">Hoje</option>
            <option value="semana">Esta semana</option>
            <option value="proximos_7">Próximos 7 dias</option>
            <option value="proximos_30">Próximos 30 dias</option>
          </select>
        </label>
        {resumo?.referencia_data ? (
          <span className="text-xs text-muted-foreground">
            Referência: {formatDateBr(resumo.referencia_data)}
          </span>
        ) : null}
      </div>

      {error ? <p className="text-sm text-destructive mb-4">{error}</p> : null}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="erp-card h-28 animate-pulse bg-muted/30" />
          ))}
        </div>
      ) : resumo ? (
        <div className="space-y-8">
          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
              Contas a Receber
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
              <ResumoCard
                titulo="A receber hoje"
                metrica={resumo.receber.hoje}
                icon={ArrowDownCircle}
                tone="receber"
                to={linkListagem('receber', { vencimento: 'hoje' })}
                acao="Ver títulos"
              />
              <ResumoCard
                titulo="A receber vencido"
                metrica={resumo.receber.vencido}
                icon={AlertTriangle}
                tone="alerta"
                to={linkListagem('receber', { vencimento: 'vencidos' })}
                acao="Ver vencidos"
              />
              <ResumoCard
                titulo="A receber — 7 dias"
                metrica={resumo.receber.proximos_7_dias}
                icon={Calendar}
                tone="receber"
                to={linkListagem('receber', { vencimento: 'proximos_7' })}
                acao="Ver títulos"
              />
              <ResumoCard
                titulo="Total em aberto"
                metrica={resumo.receber.em_aberto}
                icon={Wallet}
                tone="receber"
                to={linkListagem('receber', { com_saldo_aberto: '1' })}
                acao="Ver títulos"
              />
              <ResumoCard
                titulo="Recebido no período"
                metrica={resumo.receber.recebido_periodo}
                icon={ArrowDownCircle}
                tone="neutro"
              />
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
              Contas a Pagar
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
              <ResumoCard
                titulo="A pagar hoje"
                metrica={resumo.pagar.hoje}
                icon={ArrowUpCircle}
                tone="pagar"
                to={linkListagem('pagar', { vencimento: 'hoje' })}
                acao="Ver títulos"
              />
              <ResumoCard
                titulo="A pagar vencido"
                metrica={resumo.pagar.vencido}
                icon={AlertTriangle}
                tone="alerta"
                to={linkListagem('pagar', { vencimento: 'vencidos' })}
                acao="Ver vencidos"
              />
              <ResumoCard
                titulo="A pagar — 7 dias"
                metrica={resumo.pagar.proximos_7_dias}
                icon={Calendar}
                tone="pagar"
                to={linkListagem('pagar', { vencimento: 'proximos_7' })}
                acao="Ver títulos"
              />
              <ResumoCard
                titulo="Total em aberto"
                metrica={resumo.pagar.em_aberto}
                icon={Wallet}
                tone="pagar"
                to={linkListagem('pagar', { com_saldo_aberto: '1' })}
                acao="Ver títulos"
              />
              <ResumoCard
                titulo="Pago no período"
                metrica={resumo.pagar.pago_periodo}
                icon={ArrowUpCircle}
                tone="neutro"
              />
            </div>
          </section>

          <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ResumoCard
              titulo="Saldo previsto em aberto"
              metrica={{
                valor: resumo.saldo_previsto.em_aberto,
                quantidade: 0,
              }}
              icon={Scale}
              tone="neutro"
            />
            <ResumoCard
              titulo="Saldo previsto — 7 dias"
              metrica={{
                valor: resumo.saldo_previsto.proximos_7_dias,
                quantidade: 0,
              }}
              icon={Scale}
              tone="neutro"
            />
          </section>

          {resumo.alertas.length > 0 ? (
            <section className="erp-card p-4">
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Alertas
              </h2>
              <ul className="space-y-2">
                {resumo.alertas.map((a) => {
                  const links = alertaLinks(a.acao);
                  return (
                    <li
                      key={a.codigo}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-sm border-b border-border/40 pb-2 last:border-0"
                    >
                      <span>
                        {a.mensagem}
                        {a.quantidade > 0 ? (
                          <span className="text-muted-foreground ml-1">({a.quantidade})</span>
                        ) : null}
                      </span>
                      {links?.length ? (
                        <span className="flex flex-col sm:flex-row flex-wrap gap-2">
                          {links.map((l) => (
                            <Link
                              key={l.to}
                              to={l.to}
                              className="text-xs text-primary whitespace-nowrap"
                            >
                              {l.label} →
                            </Link>
                          ))}
                        </span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="erp-card p-4">
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <Coins className="h-4 w-4" />
                Créditos disponíveis
              </h2>
              <dl className="text-sm space-y-2">
                <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                  <dt className="text-muted-foreground">Clientes</dt>
                  <dd>
                    {resumo.creditos.clientes.quantidade} · {formatMoneyBRL(resumo.creditos.clientes.valor_disponivel)}
                  </dd>
                </div>
                <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                  <dt className="text-muted-foreground">Fornecedores</dt>
                  <dd>
                    {resumo.creditos.fornecedores.quantidade} ·{' '}
                    {formatMoneyBRL(resumo.creditos.fornecedores.valor_disponivel)}
                  </dd>
                </div>
                <div className="flex justify-between font-medium pt-2 border-t">
                  <dt>Total</dt>
                  <dd>{formatMoneyBRL(resumo.creditos.total_disponivel)}</dd>
                </div>
              </dl>
              <Link to="/financeiro/creditos" className="erp-btn-outline erp-btn-sm mt-3 inline-block w-full sm:w-auto">
                Ver créditos
              </Link>
            </div>

            <div className="erp-card p-4">
              <h2 className="font-semibold mb-3">Acesso rápido</h2>
              <div className="flex flex-col sm:flex-row flex-wrap gap-2">
                <Link to="/financeiro/contas-receber" className="erp-btn-outline erp-btn-sm w-full sm:w-auto">
                  Contas a Receber
                </Link>
                <Link to="/financeiro/contas-pagar" className="erp-btn-outline erp-btn-sm w-full sm:w-auto">
                  Contas a Pagar
                </Link>
                <Link to="/financeiro/cadastros" className="erp-btn-outline erp-btn-sm w-full sm:w-auto">
                  Cadastros financeiros
                </Link>
              </div>
            </div>
          </section>

          {resumo.por_conta.length > 0 ? (
            <section className="erp-card p-4">
              <h2 className="font-semibold mb-3">Resumo por conta / caixa prevista</h2>
              <div className="overflow-x-auto">
                <table className="erp-table text-sm w-full" data-mobile-table-mode="cards">
                  <thead>
                    <tr>
                      <th>Conta</th>
                      <th>A receber</th>
                      <th>A pagar</th>
                      <th>Saldo previsto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resumo.por_conta.map((c) => (
                      <tr key={c.conta_id}>
                        <td>{c.conta_nome}</td>
                        <td>{formatMoneyBRL(c.a_receber_em_aberto)}</td>
                        <td>{formatMoneyBRL(c.a_pagar_em_aberto)}</td>
                        <td>{formatMoneyBRL(c.saldo_previsto)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          {(resumo.por_categoria.receitas.length > 0 || resumo.por_categoria.despesas.length > 0) ? (
            <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="erp-card p-4">
                <h2 className="font-semibold mb-3">Receitas por categoria</h2>
                {resumo.por_categoria.receitas.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Sem dados no período.</p>
                ) : (
                  <ul className="text-sm space-y-1">
                    {resumo.por_categoria.receitas.map((c) => (
                      <li key={`r-${c.categoria_id}-${c.categoria_nome}`} className="flex flex-col sm:flex-row sm:justify-between gap-1">
                        <span>{c.categoria_nome}</span>
                        <span>{formatMoneyBRL(c.valor)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="erp-card p-4">
                <h2 className="font-semibold mb-3">Despesas por categoria</h2>
                {resumo.por_categoria.despesas.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Sem dados no período.</p>
                ) : (
                  <ul className="text-sm space-y-1">
                    {resumo.por_categoria.despesas.map((c) => (
                      <li key={`d-${c.categoria_id}-${c.categoria_nome}`} className="flex flex-col sm:flex-row sm:justify-between gap-1">
                        <span>{c.categoria_nome}</span>
                        <span>{formatMoneyBRL(c.valor)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          ) : null}
        </div>
      ) : (
        <EmptyState message="Não foi possível carregar o resumo financeiro." onAction={carregar} actionLabel="Tentar novamente" />
      )}
    </div>
  );
};

export default FinanceiroVisaoGeral;
