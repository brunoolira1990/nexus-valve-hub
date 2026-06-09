import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { clientesService } from '@/services/api/clientes';
import { apiErrorMessage } from '@/services/api/config';
import type { Cliente } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState, LoadingState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';

const ClienteList = () => {
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
  } = usePaginatedList<Cliente>({ fetchPage: clientesService.listPaginated });

  const handleDelete = async (id: number) => {
    if (!confirm('Excluir este cliente?')) return;
    try {
      await clientesService.delete(id);
      void reload();
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível excluir o cliente.' }));
    }
  };

  return (
    <div>
      <PageHeader
        title="Clientes"
        description="Cadastro de clientes e dados comerciais."
        onAdd={() => navigate('/clientes/novo')}
        addLabel="Novo cliente"
        searchValue={search}
        onSearch={setSearch}
      />
      <DataTableShell>
        {error ? <ErrorState onRetry={() => void reload()} /> : null}
        {loading ? <LoadingState /> : null}
        {!loading && !error ? (
          <DataTable>
            <thead>
              <tr>
                <th>Razão Social</th>
                <th>CNPJ</th>
                <th>Telefone</th>
                <th>Contato</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <EmptyState
                      message="Nenhum cliente encontrado."
                      actionLabel="Novo cliente"
                      onAction={() => navigate('/clientes/novo')}
                    />
                  </td>
                </tr>
              ) : (
                items.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium">{e.razao_social}</td>
                    <td>{e.cnpj}</td>
                    <td>{e.telefone}</td>
                    <td>{e.contato_responsavel}</td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => navigate(`/clientes/${e.id}/edit`)}
                          className="erp-btn-ghost erp-btn-sm"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(e.id)}
                          className="erp-btn-ghost erp-btn-sm text-destructive"
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
        ) : null}
        {!loading && !error && count > 0 ? (
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
    </div>
  );
};

export default ClienteList;
