import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pencil, Power, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { familiasProdutoService } from '@/services/api/produtos';
import { apiErrorMessage } from '@/services/api/config';
import type { FamiliaProduto } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { DEFAULT_PAGE_SIZE, type ListQueryParams, type PaginatedResponse } from '@/lib/apiList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState, LoadingState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const TODOS_STATUS = '__all__';

/**
 * O endpoint de famílias devolve a coleção completa (não é paginado),
 * então a paginação e o filtro de inativas acontecem no cliente.
 */
async function fetchFamiliasPaginado(params: ListQueryParams): Promise<PaginatedResponse<FamiliaProduto>> {
  const busca = typeof params.search === 'string' ? params.search : '';
  const status = typeof params.ativo === 'string' ? params.ativo : '';

  let rows = await familiasProdutoService.getAll({ search: busca || undefined });
  if (status === 'true') rows = rows.filter((f) => f.ativo);
  if (status === 'false') rows = rows.filter((f) => !f.ativo);

  const pageSize = Number(params.page_size) || DEFAULT_PAGE_SIZE;
  const page = Number(params.page) || 1;
  const start = (page - 1) * pageSize;
  return {
    count: rows.length,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(rows.length / pageSize),
    next: null,
    previous: null,
    results: rows.slice(start, start + pageSize),
  };
}

const FamiliaList = () => {
  const navigate = useNavigate();
  const [ativoSelect, setAtivoSelect] = useState<string>(TODOS_STATUS);

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
    setFilter,
    loading,
    error,
    reload,
  } = usePaginatedList<FamiliaProduto>({ fetchPage: fetchFamiliasPaginado });

  const handleAtivoChange = (v: string) => {
    setAtivoSelect(v);
    setFilter('ativo', v === TODOS_STATUS ? '' : v);
  };

  const rotulo = (f: FamiliaProduto) => `${f.codigo_figura} — ${f.descricao_base}`;

  const handleToggleAtivo = async (f: FamiliaProduto) => {
    const acao = f.ativo ? 'inativar' : 'reativar';
    if (!confirm(`Deseja ${acao} a família "${rotulo(f)}"?`)) return;
    try {
      await familiasProdutoService.update(f.id, { ativo: !f.ativo });
      void reload();
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: `Não foi possível ${acao} a família.` }));
    }
  };

  const handleDelete = async (f: FamiliaProduto) => {
    if (!confirm(`Excluir a família "${rotulo(f)}"?\nEsta ação não pode ser desfeita.`)) return;
    try {
      await familiasProdutoService.delete(f.id);
      void reload();
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível excluir a família.' }));
    }
  };

  return (
    <div>
      <PageHeader
        title="Famílias / Figuras"
        description="Modelos de produto: regra de código, classificação técnica e padrões herdados pelos produtos."
        onAdd={() => navigate('/familias/nova')}
        addLabel="Nova família"
        searchValue={search}
        onSearch={setSearch}
        searchPlaceholder="Buscar por código ou descrição…"
      />

      <div className="px-0 pb-3 flex gap-3 flex-wrap">
        <div className="w-44">
          <Select value={ativoSelect} onValueChange={handleAtivoChange}>
            <SelectTrigger className="h-9 text-sm">
              <SelectValue placeholder="Ativas e inativas" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODOS_STATUS}>Ativas e inativas</SelectItem>
              <SelectItem value="true">Somente ativas</SelectItem>
              <SelectItem value="false">Somente inativas</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <DataTableShell>
        {error ? <ErrorState onRetry={() => void reload()} /> : null}
        {loading ? <LoadingState /> : null}

        {!loading && !error ? (
          <DataTable>
            <thead>
              <tr>
                <th>Código</th>
                <th>Nome</th>
                <th>Tipo Peça</th>
                <th>Material Base</th>
                <th>Status</th>
                <th className="w-28">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <EmptyState
                      message="Nenhuma família encontrada."
                      actionLabel="Nova família"
                      onAction={() => navigate('/familias/nova')}
                    />
                  </td>
                </tr>
              ) : (
                items.map((f) => (
                  <tr key={f.id}>
                    <td className="font-mono text-xs font-medium">{f.codigo_figura}</td>
                    <td className="max-w-[280px] truncate" title={f.descricao_base}>
                      {f.descricao_base}
                    </td>
                    <td className="text-sm">{f.tipo_peca || '—'}</td>
                    <td className="text-sm">
                      {f.material_base_ref_detalhes?.nome ?? f.material_base ?? '—'}
                    </td>
                    <td>
                      <Badge variant={f.ativo ? 'default' : 'secondary'}>
                        {f.ativo ? 'Ativa' : 'Inativa'}
                      </Badge>
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          title="Editar"
                          onClick={() => navigate(`/familias/${f.id}/editar`)}
                          className="erp-btn-ghost erp-btn-sm"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          title={f.ativo ? 'Inativar' : 'Reativar'}
                          onClick={() => void handleToggleAtivo(f)}
                          className="erp-btn-ghost erp-btn-sm"
                        >
                          <Power className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          title="Excluir"
                          onClick={() => void handleDelete(f)}
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

export default FamiliaList;
