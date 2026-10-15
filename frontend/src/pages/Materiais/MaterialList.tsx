import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2, FlaskConical } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { materiaisService } from '@/services/api/materiais';
import { apiErrorMessage } from '@/services/api/config';
import type { Material, MaterialCategoria } from '@/types/material';
import { MATERIAL_CATEGORIA_LABELS, MATERIAL_CATEGORIA_OPTIONS } from '@/types/material';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState, LoadingState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

/** Mapa de cores por categoria para os badges. */
const CATEGORIA_BADGE: Record<MaterialCategoria, string> = {
  ACO_CARBONO:   'bg-amber-100 text-amber-800 border-amber-200',
  ACO_INOX:      'bg-sky-100 text-sky-800 border-sky-200',
  FERRO_FUNDIDO: 'bg-zinc-100 text-zinc-700 border-zinc-200',
  ACO_LIGA:      'bg-purple-100 text-purple-800 border-purple-200',
  NAO_FERROSO:   'bg-emerald-100 text-emerald-800 border-emerald-200',
  POLIMERO:      'bg-rose-100 text-rose-800 border-rose-200',
  OUTRO:         'bg-slate-100 text-slate-600 border-slate-200',
};

const MaterialList = () => {
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
    filters,
    setFilter,
    loading,
    error,
    reload,
  } = usePaginatedList<Material>({
    fetchPage: materiaisService.listPaginated,
  });

  const handleDelete = async (id: number, nome: string) => {
    if (!confirm(`Excluir o material "${nome}"?\nEsta ação não pode ser desfeita.`)) return;
    try {
      await materiaisService.delete(id);
      void reload();
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível excluir o material.' }));
    }
  };

  return (
    <div>
      <PageHeader
        title="Materiais"
        description="Catálogo de materiais de engenharia (aços, polímeros, não-ferrosos…)."
        onAdd={() => navigate('/materiais/novo')}
        addLabel="Novo material"
        searchValue={search}
        onSearch={setSearch}
        searchPlaceholder="Buscar por nome, código ou alias…"
      />

      {/* Filtro de categoria */}
      <div className="px-0 pb-3 flex gap-3 flex-wrap">
        <div className="w-56">
          <Select
            value={filters.categoria ?? ''}
            onValueChange={(v) => setFilter('categoria', v)}
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue placeholder="Todas as categorias" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Todas as categorias</SelectItem>
              {MATERIAL_CATEGORIA_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-44">
          <Select
            value={filters.ativo ?? ''}
            onValueChange={(v) => setFilter('ativo', v)}
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue placeholder="Ativos e inativos" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Ativos e inativos</SelectItem>
              <SelectItem value="true">Somente ativos</SelectItem>
              <SelectItem value="false">Somente inativos</SelectItem>
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
                <th>Curto</th>
                <th>Categoria</th>
                <th>Norma / Spec.</th>
                <th>NCM sugerido</th>
                <th>Aliases</th>
                <th>Ordem</th>
                <th>Status</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={10}>
                    <EmptyState
                      message="Nenhum material encontrado."
                      actionLabel="Novo material"
                      onAction={() => navigate('/materiais/novo')}
                    />
                  </td>
                </tr>
              ) : (
                items.map((m) => (
                  <tr key={m.id}>
                    <td className="font-mono text-xs">{m.codigo}</td>
                    <td className="font-medium">{m.nome}</td>
                    <td className="text-sm text-muted-foreground">{m.nome_curto}</td>
                    <td>
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${CATEGORIA_BADGE[m.categoria]}`}
                      >
                        {MATERIAL_CATEGORIA_LABELS[m.categoria] ?? m.categoria}
                      </span>
                    </td>
                    <td className="text-sm text-muted-foreground max-w-[160px] truncate">
                      {m.norma_astm || '—'}
                    </td>
                    <td className="font-mono text-xs">{m.ncm_sugerido || '—'}</td>
                    <td>
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {m.aliases.slice(0, 3).map((a) => (
                          <Badge key={a} variant="outline" className="text-xs px-1.5 py-0">
                            {a}
                          </Badge>
                        ))}
                        {m.aliases.length > 3 && (
                          <Badge variant="outline" className="text-xs px-1.5 py-0 text-muted-foreground">
                            +{m.aliases.length - 3}
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="text-sm tabular-nums text-muted-foreground">{m.ordem}</td>
                    <td>
                      <Badge variant={m.ativo ? 'default' : 'secondary'}>
                        {m.ativo ? 'Ativo' : 'Inativo'}
                      </Badge>
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          title="Editar"
                          onClick={() => navigate(`/materiais/${m.id}/editar`)}
                          className="erp-btn-ghost erp-btn-sm"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          title="Excluir"
                          onClick={() => handleDelete(m.id, m.nome)}
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

export default MaterialList;
