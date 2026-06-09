import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { RelatorioAvisoHistorico } from '@/components/financeiro/relatorios/RelatorioAvisoHistorico';
import { RelatorioPdfActions } from '@/components/financeiro/relatorios/RelatorioPdfActions';
import { RelatorioFiltrosPanel } from '@/components/financeiro/relatorios/RelatorioFiltrosPanel';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/money';
import { useRelatorioFinanceiro } from '@/hooks/useRelatorioFinanceiro';
import { EMPTY_STATE_RELATORIO, linkVerTitulosRelatorio } from '@/lib/relatorioFinanceiro';
import { financeiroService, type RelatorioFornecedores } from '@/services/api/financeiro';

export default function RelatorioFornecedoresPage() {
  const fetcher = useCallback(
    (q: Record<string, string>) => financeiroService.relatorioFornecedores(q),
    [],
  );
  const { data, loading, error, filtros, aplicarFiltros, reload } =
    useRelatorioFinanceiro<RelatorioFornecedores>(fetcher);

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
        title="Relatório por fornecedor"
        description="Pagamentos e despesas agrupados por fornecedor."
        actions={
          <div className="flex flex-wrap gap-2 items-center">
            <RelatorioPdfActions endpoint="fornecedores" filtros={filtros} className="flex gap-2 mb-0" />
            <Link to="/financeiro/relatorios" className="erp-btn-outline erp-btn-sm">
              Voltar aos relatórios
            </Link>
          </div>
        }
      />

      <RelatorioFiltrosPanel
        modo="FORNECEDORES"
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
                    <th className="p-3 font-medium">Fornecedor</th>
                    <th className="p-3 font-medium text-right">Em aberto</th>
                    <th className="p-3 font-medium text-right">Vencido</th>
                    <th className="p-3 font-medium text-right">Pago no período</th>
                    <th className="p-3 font-medium text-right">Títulos</th>
                    <th className="p-3 font-medium">Último pagamento</th>
                    <th className="p-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {data.resumo.map((row) => (
                    <tr key={row.fornecedor_id ?? row.fornecedor_nome} className="border-b border-border/50">
                      <td className="p-3 font-medium">{row.fornecedor_nome}</td>
                      <td className="p-3 text-right tabular-nums">{formatMoneyBRL(row.total_aberto)}</td>
                      <td className="p-3 text-right tabular-nums">{formatMoneyBRL(row.total_vencido)}</td>
                      <td className="p-3 text-right tabular-nums">
                        {formatMoneyBRL(row.pago_periodo ?? '0')}
                      </td>
                      <td className="p-3 text-right">{row.quantidade_titulos}</td>
                      <td className="p-3 text-xs">
                        {row.ultimo_pagamento ? formatDateBr(row.ultimo_pagamento) : '—'}
                      </td>
                      <td className="p-3">
                        {row.fornecedor_id ? (
                          <Link
                            to={linkVerTitulosRelatorio('pagar', filtros, row.fornecedor_id)}
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
            <EmptyState message={EMPTY_STATE_RELATORIO.fornecedores} />
          ) : null}
        </>
      ) : null}

    </div>
  );
}
