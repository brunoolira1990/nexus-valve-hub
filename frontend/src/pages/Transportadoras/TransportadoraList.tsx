import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { transportadorasService } from '@/services/api/transportadoras';
import type { Transportadora } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';

const TransportadoraList = () => {
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
  } = usePaginatedList<Transportadora>({ fetchPage: transportadorasService.listPaginated });

  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await transportadorasService.delete(id);
      void reload();
    }
  };

  const placaExibicao = (t: Transportadora) => {
    const placa = [t.placa_padrao, t.uf_placa].filter(Boolean).join('/');
    return placa || '—';
  };

  return (
    <div>
      <PageHeader
        title="Transportadoras"
        description="Cadastro de transportadoras utilizadas em NF-e, expedição e logística."
        onAdd={() => navigate('/transportadoras/novo')}
        addLabel="Nova transportadora"
        searchValue={search}
        onSearch={setSearch}
      />
      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={7} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable>
            <thead>
              <tr>
                <th>Razão Social</th>
                <th>CNPJ</th>
                <th>Cidade/UF</th>
                <th>Placa</th>
                <th>Telefone</th>
                <th>Status</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      message="Nenhuma transportadora encontrada."
                      actionLabel="Nova transportadora"
                      onAction={() => navigate('/transportadoras/novo')}
                    />
                  </td>
                </tr>
              ) : (
                items.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium">{e.razao_social}</td>
                    <td>{e.cnpj}</td>
                    <td>{e.cidade && e.uf ? `${e.cidade}/${e.uf}` : e.cidade || e.uf || '—'}</td>
                    <td>{placaExibicao(e)}</td>
                    <td>{e.telefone || '—'}</td>
                    <td>
                      <StatusBadge status={e.ativo ? 'Ativo' : 'Inativo'} />
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => navigate(`/transportadoras/${e.id}/edit`)}
                          className="erp-btn-ghost erp-btn-sm"
                          title="Editar"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(e.id)}
                          className="erp-btn-ghost erp-btn-sm text-destructive"
                          title="Excluir"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
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

export default TransportadoraList;
