import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { RelatorioFiltrosPanel } from '@/components/financeiro/relatorios/RelatorioFiltrosPanel';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/money';
import { RelatorioAvisoHistorico } from '@/components/financeiro/relatorios/RelatorioAvisoHistorico';
import { RelatorioPdfActions } from '@/components/financeiro/relatorios/RelatorioPdfActions';
import { useRelatorioFinanceiro } from '@/hooks/useRelatorioFinanceiro';
import { EMPTY_STATE_RELATORIO, linkVerTitulosRelatorio } from '@/lib/relatorioFinanceiro';
import {
  financeiroService,
  type RelatorioClientes,
} from '@/services/api/financeiro';

export default function RelatorioClientesPage() {
  const fetcher = useCallback(
    (q: Record<string, string>) => financeiroService.relatorioClientes(q),
    [],
  );
  const { data, loading, error, filtros, aplicarFiltros, reload } =
    useRelatorioFinanceiro<RelatorioClientes>(fetcher);

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

  return (
    <div>
      <PageHeader
        title="Relatório por cliente"
        description="Cobrança e acompanhamento de recebíveis agrupados por cliente."
        actions={
          <div className="flex flex-wrap gap-2 items-center">
            <RelatorioPdfActions endpoint="clientes" filtros={filtros} className="flex gap-2 mb-0" />
            <Link to="/financeiro/relatorios" className="erp-btn-outline erp-btn-sm">
              Voltar aos relatórios
            </Link>
          </div>
        }
      />

      <RelatorioFiltrosPanel
        modo="CLIENTES"
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
          {data.resumo.length > 0 ? (
            <div className="erp-card overflow-x-auto mb-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="p-3 font-medium">Cliente</th>
                    <th className="p-3 font-medium text-right">Em aberto</th>
                    <th className="p-3 font-medium text-right">Vencido</th>
                    <th className="p-3 font-medium text-right">Recebido no período</th>
                    <th className="p-3 font-medium text-right">Títulos</th>
                    <th className="p-3 font-medium">Último recebimento</th>
                    <th className="p-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {data.resumo.map((row) => (
                    <tr key={row.cliente_id ?? row.cliente_nome} className="border-b border-border/50">
                      <td className="p-3 font-medium">{row.cliente_nome}</td>
                      <td className="p-3 text-right tabular-nums">{formatMoneyBRL(row.total_aberto)}</td>
                      <td className="p-3 text-right tabular-nums">{formatMoneyBRL(row.total_vencido)}</td>
                      <td className="p-3 text-right tabular-nums">
                        {formatMoneyBRL(row.recebido_periodo ?? '0')}
                      </td>
                      <td className="p-3 text-right">{row.quantidade_titulos}</td>
                      <td className="p-3 text-xs">
                        {row.ultimo_recebimento ? formatDateBr(row.ultimo_recebimento) : '—'}
                      </td>
                      <td className="p-3">
                        {row.cliente_id ? (
                          <Link
                            to={linkVerTitulosRelatorio('receber', filtros, row.cliente_id)}
                            className="text-xs text-primary hover:underline"
                          >
                            Ver títulos
                          </Link>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {data.resumo.length === 0 ? (
            <EmptyState message={EMPTY_STATE_RELATORIO.clientes} />
          ) : null}
        </>
      ) : null}

    </div>
  );
}
