import { useNavigate } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { DfeClassificacaoBadges } from '@/components/fiscal/DfeClassificacaoBadges';
import { PageHeader } from '@/components/PageHeader';
import { NexusButton } from '@/components/nexus';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { cteEntradasService } from '@/services/api/fiscal';
import type { CTeEntrada } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { formatDateBr } from '@/lib/dateBr';

const BASE_CTE_IMPORTADA_PATH = '/cte-historico-importado';

const CTeEntrada = () => {
  const navigate = useNavigate();
  const {
    items,
    count,
    page,
    pageSize,
    totalPages,
    search,
    setSearch,
    setPage,
    setPageSize,
    loading,
    error,
    reload,
  } = usePaginatedList<CTeEntrada>({ fetchPage: cteEntradasService.listPaginated });

  return (
    <div>
      <PageHeader
        title="CT-e Entrada"
        description="Conhecimentos de transporte conferidos para uso operacional. A conferência não gera financeiro, expedição ou rateio automaticamente."
        searchValue={search}
        onSearch={setSearch}
        actions={
          <NexusButton type="button" variant="outline" onClick={() => navigate(BASE_CTE_IMPORTADA_PATH)}>
            <ExternalLink className="h-4 w-4" />
            Ir para Base CT-e Importada
          </NexusButton>
        }
      />
      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={7} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable>
            <thead>
              <tr>
                <th>Número</th>
                <th>Transportadora</th>
                <th>Tomador</th>
                <th>Valor Frete</th>
                <th>Data</th>
                <th>Status</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <div className="py-10 px-4 text-center">
                      <p className="text-sm font-medium text-foreground">Nenhum CT-e operacional encontrado.</p>
                      <p className="text-sm text-muted-foreground mt-2 max-w-xl mx-auto">
                        Importe XMLs na Base CT-e Importada e confira os documentos para uso operacional. A conferência
                        não gera contas a pagar, expedição ou rateio.
                      </p>
                      <NexusButton
                        type="button"
                        className="mt-4"
                        onClick={() => navigate(BASE_CTE_IMPORTADA_PATH)}
                      >
                        <ExternalLink className="h-4 w-4" />
                        Ir para Base CT-e Importada
                      </NexusButton>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium">
                      {e.numero}
                      {e.serie ? `/${e.serie}` : ''}
                    </td>
                    <td>{e.transportadora_nome}</td>
                    <td>{e.tomador_nome}</td>
                    <td className="nexus-numeric">R$ {Number(e.valor_frete ?? 0).toFixed(2)}</td>
                    <td>{e.data ? formatDateBr(e.data) : '—'}</td>
                    <td>
                      <div className="flex flex-col gap-1 items-start">
                        {e.status_conferencia ? (
                          <StatusBadge status={e.status_conferencia.toLowerCase()} />
                        ) : (
                          <StatusBadge status="conferido" />
                        )}
                        <DfeClassificacaoBadges classificacao={e.classificacao_dfe} max={4} />
                      </div>
                    </td>
                    <td>
                      <NexusButton
                        type="button"
                        variant="outline"
                        className="erp-btn-sm"
                        onClick={() => navigate(BASE_CTE_IMPORTADA_PATH)}
                      >
                        Detalhes
                      </NexusButton>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </DataTable>
          {count > 0 ? (
            <PaginationControls
              page={page}
              pageSize={pageSize}
              count={count}
              totalPages={totalPages}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          ) : null}
        </DataTableShell>
      ) : null}
    </div>
  );
};

export default CTeEntrada;
