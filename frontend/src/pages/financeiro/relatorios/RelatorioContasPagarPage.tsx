import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { RelatorioFiltrosPanel } from '@/components/financeiro/relatorios/RelatorioFiltrosPanel';
import { RelatorioMetricCards, type RelatorioCardItem } from '@/components/financeiro/relatorios/RelatorioMetricCards';
import { RelatorioTitulosTable } from '@/components/financeiro/relatorios/RelatorioTitulosTable';
import { TituloFinanceiroBaixaModal } from '@/components/financeiro/TituloFinanceiroBaixaModal';
import { TituloFinanceiroDetalheDrawer } from '@/components/financeiro/TituloFinanceiroDetalheDrawer';
import { formatMoneyBRL } from '@/lib/money';
import { RelatorioAvisoHistorico } from '@/components/financeiro/relatorios/RelatorioAvisoHistorico';
import { RelatorioPdfActions } from '@/components/financeiro/relatorios/RelatorioPdfActions';
import { useRelatorioFinanceiro } from '@/hooks/useRelatorioFinanceiro';
import { EMPTY_STATE_RELATORIO } from '@/lib/relatorioFinanceiro';
import {
  financeiroService,
  type RelatorioContasReceberPagar,
  type RelatorioLinhaTitulo,
  type TituloFinanceiro,
} from '@/services/api/financeiro';

export default function RelatorioContasPagarPage() {
  const fetcher = useCallback(
    (q: Record<string, string>) => financeiroService.relatorioContasPagar(q),
    [],
  );
  const { data, loading, error, filtros, aplicarFiltros, reload } =
    useRelatorioFinanceiro<RelatorioContasReceberPagar>(fetcher);

  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
  const [centros, setCentros] = useState<{ id: number; nome: string }[]>([]);
  const [contas, setContas] = useState<{ id: number; nome: string }[]>([]);
  const [detalheId, setDetalheId] = useState<number | null>(null);
  const [baixaTitulo, setBaixaTitulo] = useState<TituloFinanceiro | null>(null);

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
        { titulo: 'Total em aberto', metrica: data.cards.total_aberto, tone: 'pagar' },
        { titulo: 'Total vencido', metrica: data.cards.total_vencido, tone: 'alerta' },
        { titulo: 'Pago no período', metrica: data.cards.pago_periodo, tone: 'neutro' },
        { titulo: 'Parcialmente pago', metrica: data.cards.total_parcial, tone: 'neutro' },
        {
          titulo: 'Tributos em aberto',
          metrica: data.cards.total_tributos,
          tone: 'alerta',
        },
        {
          titulo: 'Quantidade de títulos',
          valor: String(data.cards.quantidade_titulos),
        },
      ]
    : [];

  const abrirBaixa = async (ln: RelatorioLinhaTitulo) => {
    const titulo = await financeiroService.getContaPagar(ln.id);
    setBaixaTitulo(titulo);
  };

  return (
    <div>
      <PageHeader
        title="Relatório — Contas a Pagar"
        description="Despesas, tributos e pagamentos previstos com totais por vencimento."
        actions={
          <div className="flex flex-wrap gap-2 items-center">
            <RelatorioPdfActions endpoint="contas-pagar" filtros={filtros} className="flex gap-2 mb-0" />
            <Link to="/financeiro/relatorios" className="erp-btn-outline erp-btn-sm">
              Voltar aos relatórios
            </Link>
          </div>
        }
      />

      <RelatorioFiltrosPanel
        modo="PAGAR"
        filtros={filtros}
        onChange={aplicarFiltros}
        categorias={categorias}
        centros={centros}
        contas={contas}
        showAgrupamento
      />

      {data?.aviso_historico ? <RelatorioAvisoHistorico mensagem={data.aviso_historico} /> : null}

      {loading ? <TableSkeleton rows={6} /> : null}
      {!loading && error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {!loading && !error && data ? (
        <>
          <RelatorioMetricCards cards={cards} />
          {data.agrupamentos.length > 0 ? (
            <div className="erp-card p-4 mb-6">
              <h3 className="font-semibold text-sm mb-3">Agrupamento</h3>
              <ul className="space-y-2 text-sm">
                {data.agrupamentos.map((g) => (
                  <li key={g.chave} className="flex justify-between gap-4 border-b border-border/40 pb-2">
                    <span>
                      {g.titulo} ({g.quantidade})
                    </span>
                    <span className="tabular-nums font-medium">{formatMoneyBRL(g.saldo)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {data.linhas.length > 0 ? (
            <RelatorioTitulosTable
              linhas={data.linhas}
              modo="PAGAR"
              onAbrir={setDetalheId}
              onBaixar={(ln) => void abrirBaixa(ln)}
            />
          ) : (
            <EmptyState message={EMPTY_STATE_RELATORIO['contas-pagar']} />
          )}
        </>
      ) : null}

      <TituloFinanceiroDetalheDrawer
        open={detalheId != null}
        tituloId={detalheId}
        modo="PAGAR"
        onClose={() => setDetalheId(null)}
        onUpdated={() => void reload()}
      />
      <TituloFinanceiroBaixaModal
        open={baixaTitulo != null}
        modo="PAGAR"
        titulo={baixaTitulo}
        onClose={() => setBaixaTitulo(null)}
        onSuccess={() => {
          setBaixaTitulo(null);
          void reload();
        }}
      />
    </div>
  );
}
