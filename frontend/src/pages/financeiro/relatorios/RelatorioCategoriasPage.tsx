import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { RelatorioFiltrosPanel } from '@/components/financeiro/relatorios/RelatorioFiltrosPanel';
import { RelatorioMetricCards, type RelatorioCardItem } from '@/components/financeiro/relatorios/RelatorioMetricCards';
import { formatMoneyBRL } from '@/lib/money';
import { RelatorioAvisoHistorico } from '@/components/financeiro/relatorios/RelatorioAvisoHistorico';
import { RelatorioPdfActions } from '@/components/financeiro/relatorios/RelatorioPdfActions';
import { useRelatorioFinanceiro } from '@/hooks/useRelatorioFinanceiro';
import { EMPTY_STATE_RELATORIO } from '@/lib/relatorioFinanceiro';
import { financeiroService, type RelatorioCategorias } from '@/services/api/financeiro';

export default function RelatorioCategoriasPage() {
  const fetcher = useCallback((q: Record<string, string>) => {
    const periodo = q.periodo || q.periodo_baixa || 'mes';
    return financeiroService.relatorioCategorias({ ...q, periodo });
  }, []);
  const { data, loading, error, filtros, aplicarFiltros, reload } =
    useRelatorioFinanceiro<RelatorioCategorias>(fetcher);

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
        { titulo: 'Total de receitas', metrica: data.cards.total_receitas, tone: 'receber' },
        { titulo: 'Total de despesas', metrica: data.cards.total_despesas, tone: 'pagar' },
        { titulo: 'Diferença prevista', metrica: data.cards.diferenca_prevista, tone: 'neutro' },
        {
          titulo: 'Sem classificação',
          valor: `${data.cards.sem_classificacao.receitas} rec. / ${data.cards.sem_classificacao.despesas} desp.`,
        },
      ]
    : [];

  return (
    <div>
      <PageHeader
        title="Receitas e despesas por categoria"
        description="Composição de receitas e despesas por classificação financeira (não é DRE contábil)."
        actions={
          <div className="flex flex-wrap gap-2 items-center">
            <RelatorioPdfActions endpoint="categorias" filtros={filtros} className="flex gap-2 mb-0" />
            <Link to="/financeiro/relatorios" className="erp-btn-outline erp-btn-sm">
              Voltar aos relatórios
            </Link>
          </div>
        }
      />

      <RelatorioFiltrosPanel
        modo="CATEGORIAS"
        filtros={filtros}
        onChange={aplicarFiltros}
        categorias={categorias}
        centros={centros}
        contas={contas}
      />

      {data?.aviso_historico ? <RelatorioAvisoHistorico mensagem={data.aviso_historico} /> : null}

      {loading ? <TableSkeleton rows={6} /> : null}
      {!loading && error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {!loading && !error && data ? (
        <>
          <RelatorioMetricCards cards={cards} />
          {data.linhas.length > 0 ? (
            <div className="erp-card overflow-x-auto">
              <p className="text-xs text-muted-foreground p-3 pb-0">
                Original: soma dos títulos filtrados. Em aberto: saldo pendente. Baixado: recebido/pago no
                período. Total: valor considerado no relatório conforme filtros.
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="p-3 font-medium">Categoria</th>
                    <th className="p-3 font-medium">Tipo</th>
                    <th className="p-3 font-medium text-right">Qtd.</th>
                    <th className="p-3 font-medium text-right" title="Soma dos valores originais dos títulos filtrados">
                      Original
                    </th>
                    <th className="p-3 font-medium text-right" title="Saldo ainda pendente (não quitado/cancelado)">
                      Em aberto
                    </th>
                    <th className="p-3 font-medium text-right" title="Valor recebido ou pago no período">
                      Baixado
                    </th>
                    <th className="p-3 font-medium text-right" title="Valor considerado no relatório conforme filtros">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.linhas.map((ln, i) => (
                    <tr key={`${ln.categoria_nome}-${ln.tipo}-${i}`} className="border-b border-border/50">
                      <td className="p-3">{ln.categoria_nome}</td>
                      <td className="p-3">{ln.tipo}</td>
                      <td className="p-3 text-right">{ln.quantidade}</td>
                      <td className="p-3 text-right tabular-nums">
                        {formatMoneyBRL(ln.valor_original)}
                      </td>
                      <td className="p-3 text-right tabular-nums">{formatMoneyBRL(ln.em_aberto)}</td>
                      <td className="p-3 text-right tabular-nums">
                        {formatMoneyBRL(ln.baixado_periodo ?? ln.baixado)}
                      </td>
                      <td className="p-3 text-right tabular-nums font-medium">
                        {formatMoneyBRL(ln.total_considerado ?? ln.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message={EMPTY_STATE_RELATORIO.categorias} />
          )}
        </>
      ) : null}
    </div>
  );
}
