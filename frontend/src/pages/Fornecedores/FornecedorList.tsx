import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { fornecedoresService } from '@/services/api/fornecedores';
import type { Fornecedor } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';

const FornecedorList = () => {
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
  } = usePaginatedList<Fornecedor>({ fetchPage: fornecedoresService.listPaginated });

  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await fornecedoresService.delete(id);
      void reload();
    }
  };

  return (
    <div>
      <PageHeader
        title="Fornecedores"
        description="Cadastro de fornecedores e dados comerciais/fiscais para compras e entradas."
        onAdd={() => navigate('/fornecedores/novo')}
        addLabel="Novo fornecedor"
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
                <th>Telefone</th>
                <th>E-mail</th>
                <th>Status</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      message="Nenhum fornecedor encontrado."
                      actionLabel="Novo fornecedor"
                      onAction={() => navigate('/fornecedores/novo')}
                    />
                  </td>
                </tr>
              ) : (
                items.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium">{e.razao_social}</td>
                    <td>{e.cnpj}</td>
                    <td>{e.cidade && e.uf ? `${e.cidade}/${e.uf}` : e.cidade || e.uf || '—'}</td>
                    <td>{e.telefone || '—'}</td>
                    <td>{e.email || '—'}</td>
                    <td>
                      <StatusBadge status={e.ativo ? 'Ativo' : 'Inativo'} />
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => navigate(`/fornecedores/${e.id}/edit`)}
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

export default FornecedorList;
