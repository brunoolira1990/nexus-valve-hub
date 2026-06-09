import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { RelatorioFiltrosPanel } from '@/components/financeiro/relatorios/RelatorioFiltrosPanel';
import { RelatorioPdfActions } from '@/components/financeiro/relatorios/RelatorioPdfActions';
import { RelatorioMetricCards, type RelatorioCardItem } from '@/components/financeiro/relatorios/RelatorioMetricCards';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/money';
import { useRelatorioFinanceiro } from '@/hooks/useRelatorioFinanceiro';
import { EMPTY_STATE_RELATORIO } from '@/lib/relatorioFinanceiro';
import { financeiroService, type RelatorioFluxoPrevisto } from '@/services/api/financeiro';

export default function RelatorioFluxoPrevistoPage() {
  const fetcher = useCallback((q: Record<string, string>) => {
    const periodo = q.periodo || 'proximos_30';
    return financeiroService.relatorioFluxoPrevisto({ ...q, periodo });
  }, []);
  const { data, loading, error, filtros, aplicarFiltros, reload } =
    useRelatorioFinanceiro<RelatorioFluxoPrevisto>(fetcher);

  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
  const [centros, setCentros] = useState<{ id: number; nome: string }[]>([]);
  const [contas, setContas] = useState<{ id: number; nome: string }[]>([]);

  useEffect(() => {
    void Promise.all([
      financeiroService.listCategorias({ limit: 200 }),
      financeiroService.listCentrosCusto({ limit: 200 }),
      financeiroService.listContasAtivas(),
    ]).then(([cat, cc, cts]) => {
      setCategorias((cat.results ?? []).filter((c) => c.ativo).map((c) => ({ id: c.id, nome: c.nome })));
      setCentros((cc.results ?? []).filter((c) => c.ativo).map((c) => ({ id: c.id, nome: c.nome })));
      setContas(cts.map((c) => ({ id: c.id, nome: c.nome })));
    });
  }, []);

  const cards: RelatorioCardItem[] = data
    ? [
        { titulo: 'A receber no período', metrica: data.cards.total_receber, tone: 'receber' },
        { titulo: 'A pagar no período', metrica: data.cards.total_pagar, tone: 'pagar' },
        { titulo: 'Saldo previsto', metrica: data.cards.saldo_previsto, tone: 'neutro' },
        {
          titulo: 'Maior entrada',
          metrica: data.cards.maior_entrada,
          subtitulo: data.cards.maior_entrada.data
            ? formatDateBr(data.cards.maior_entrada.data)
            : undefined,
        },
        {
          titulo: 'Maior saída',
          metrica: data.cards.maior_saida,
          subtitulo: data.cards.maior_saida.data ? formatDateBr(data.cards.maior_saida.data) : undefined,
        },
      ]
    : [];

  return (
    <div>
      <PageHeader
        title="Fluxo financeiro previsto"
        description="Previsão de entradas e saídas por data com base em títulos em aberto. Não é conciliação bancária."
        actions={
          <div className="flex flex-wrap gap-2 items-center">
            <RelatorioPdfActions endpoint="fluxo-previsto" filtros={filtros} className="flex gap-2 mb-0" />
            <Link to="/financeiro/relatorios" className="erp-btn-outline erp-btn-sm">
              Voltar aos relatórios
            </Link>
          </div>
        }
      />

      {data?.nota ? (
        <p className="text-xs text-muted-foreground mb-3 px-1" role="note">
          {data.nota}
        </p>
      ) : null}

      <RelatorioFiltrosPanel
        modo="FLUXO"
        filtros={filtros}
        onChange={aplicarFiltros}
        categorias={categorias}
        centros={centros}
        contas={contas}
      />

      {loading ? <TableSkeleton rows={8} /> : null}
      {!loading && error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {!loading && !error && data ? (
        <>
          <RelatorioMetricCards cards={cards} />
          {data.linhas.length > 0 ? (
            <div className="erp-card overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="p-3 font-medium">Data</th>
                    <th className="p-3 font-medium text-right">A receber</th>
                    <th className="p-3 font-medium text-right">A pagar</th>
                    <th className="p-3 font-medium text-right">Saldo do dia</th>
                    <th className="p-3 font-medium text-right">Saldo acumulado</th>
                  </tr>
                </thead>
                <tbody>
                  {data.linhas.map((ln) => (
                    <tr key={ln.data} className="border-b border-border/50">
                      <td className="p-3">{formatDateBr(ln.data)}</td>
                      <td className="p-3 text-right tabular-nums text-emerald-700 dark:text-emerald-400">
                        {formatMoneyBRL(ln.a_receber)}
                      </td>
                      <td className="p-3 text-right tabular-nums text-rose-700 dark:text-rose-400">
                        {formatMoneyBRL(ln.a_pagar)}
                      </td>
                      <td className="p-3 text-right tabular-nums">{formatMoneyBRL(ln.saldo_dia)}</td>
                      <td className="p-3 text-right tabular-nums font-medium">
                        {formatMoneyBRL(ln.saldo_acumulado)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message={EMPTY_STATE_RELATORIO['fluxo-previsto']} />
          )}
        </>
      ) : null}
    </div>
  );
}
