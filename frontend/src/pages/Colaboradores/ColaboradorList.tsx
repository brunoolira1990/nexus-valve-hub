import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import type { Colaborador, ColaboradorFuncao } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { NexusCard } from '@/components/nexus/NexusCard';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { badgeAcessoListagem, acessoColaboradorTooltip, badgeAcessoVariant } from '@/lib/colaboradorAcesso';
import type { ListQueryParams } from '@/lib/apiList';
import { Pencil, Trash2 } from 'lucide-react';

function colaboradorToForm(c: Colaborador) {
  return {
    nome: c.nome ?? '',
    codigo: c.codigo ?? '',
    email: c.email ?? '',
    telefone: c.telefone ?? '',
    cargo: c.cargo ?? '',
    departamento: c.departamento ?? '',
    ativo: Boolean(c.ativo),
    observacoes: c.observacoes ?? '',
    eh_vendedor: Boolean(c.eh_vendedor),
    eh_comprador: Boolean(c.eh_comprador),
    eh_responsavel_fiscal: Boolean(c.eh_responsavel_fiscal),
    eh_responsavel_financeiro: Boolean(c.eh_responsavel_financeiro),
    eh_responsavel_estoque: Boolean(c.eh_responsavel_estoque),
    eh_responsavel_qualidade: Boolean(c.eh_responsavel_qualidade),
    eh_administrador: Boolean(c.eh_administrador),
  };
}

function badgesFuncoes(c: Colaborador): { label: string; badgeClass: string }[] {
  const FUNCAO_CAMPOS: { key: keyof ColaboradorForm; label: string; badgeClass: string }[] = [
    { key: 'eh_vendedor', label: 'Vendedor', badgeClass: 'bg-emerald-600/15 text-emerald-800 dark:text-emerald-200' },
    { key: 'eh_comprador', label: 'Comprador', badgeClass: 'bg-blue-600/15 text-blue-800 dark:text-blue-200' },
    { key: 'eh_responsavel_fiscal', label: 'Fiscal', badgeClass: 'bg-violet-600/15 text-violet-800 dark:text-violet-200' },
    { key: 'eh_responsavel_financeiro', label: 'Financeiro', badgeClass: 'bg-amber-600/15 text-amber-900 dark:text-amber-100' },
    { key: 'eh_responsavel_estoque', label: 'Estoque', badgeClass: 'bg-cyan-600/15 text-cyan-900 dark:text-cyan-100' },
    { key: 'eh_responsavel_qualidade', label: 'Qualidade', badgeClass: 'bg-pink-600/15 text-pink-900 dark:text-pink-100' },
    { key: 'eh_administrador', label: 'Admin', badgeClass: 'bg-slate-600/15 text-slate-800 dark:text-slate-200' },
  ];
  return FUNCAO_CAMPOS.filter((f) => Boolean(c[f.key as keyof Colaborador])).map((f) => ({
    label: f.label,
    badgeClass: f.badgeClass,
  }));
}

const FILTRO_FUNCAO: { value: ColaboradorFuncao | ''; label: string }[] = [
  { value: '', label: 'Todas as funções' },
  { value: 'vendedor', label: 'Vendedor' },
  { value: 'comprador', label: 'Comprador' },
  { value: 'fiscal', label: 'Fiscal' },
  { value: 'financeiro', label: 'Financeiro' },
  { value: 'estoque', label: 'Estoque' },
  { value: 'qualidade', label: 'Qualidade' },
  { value: 'administrador', label: 'Administrador' },
];

const fetchColaboradoresPage = (params: ListQueryParams) => {
  const { funcao, ativo, ...rest } = params;
  const listParams: import('@/services/api/colaboradores').ColaboradorListParams = { ...rest };
  if (funcao) listParams.funcao = funcao as ColaboradorFuncao;
  if (ativo === 'true') listParams.ativo = true;
  else if (ativo === 'false') listParams.ativo = false;
  else listParams.ativo = 'all';
  return colaboradoresService.listPaginated(listParams);
};

export default function ColaboradorList() {
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
  } = usePaginatedList<Colaborador>({ fetchPage: fetchColaboradoresPage });
  const [confirmandoId, setConfirmandoId] = useState<number | null>(null);
  const filtroFuncao = filters.funcao || '';
  const filtroAtivo =
    filters.ativo === 'true' ? 'active' : filters.ativo === 'false' ? 'inactive' : 'all';

  const openNew = () => {
    void navigate('/colaboradores/novo');
  };

  const openEdit = async (c: Colaborador) => {
    void navigate(`/colaboradores/${c.id}`);
  };

  const handleDeleteConfirm = async (c: Colaborador) => {
    setConfirmandoId(null);
    try {
      await colaboradoresService.delete(c.id);
      void reload();
    } catch (e) {
      // toast.error(apiErrorMessage(e));
      console.error(e);
    }
  };

  return (
    <div>
      <PageHeader
        title="Colaboradores"
        description="Cadastro de colaboradores, funções internas e acesso ao sistema."
        onAdd={openNew}
        addLabel="Novo colaborador"
        searchValue={search}
        onSearch={setSearch}
      />

      <NexusCard className="mb-4">
        <div className="flex flex-col sm:flex-row sm:flex-wrap gap-3">
          <select
            className="erp-select h-9 text-sm w-full sm:w-auto sm:min-w-[10rem]"
            value={filtroFuncao}
            onChange={(e) => setFilter('funcao', e.target.value)}
          >
            {FILTRO_FUNCAO.map((o) => (
              <option key={o.value || 'all'} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            className="erp-select h-9 text-sm w-full sm:w-auto sm:min-w-[8rem]"
            value={filtroAtivo}
            onChange={(e) => {
              const v = e.target.value;
              setFilter('ativo', v === 'active' ? 'true' : v === 'inactive' ? 'false' : '');
            }}
          >
            <option value="all">Todos</option>
            <option value="active">Ativos</option>
            <option value="inactive">Inativos</option>
          </select>
        </div>
      </NexusCard>

      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={8} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable mobileMode="cards">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Código</th>
                <th>E-mail</th>
                <th>Funções</th>
                <th>Acesso</th>
                <th>Status</th>
                <th className="w-28">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      message="Nenhum colaborador encontrado."
                      actionLabel="Novo colaborador"
                      onAction={openNew}
                    />
                  </td>
                </tr>
              ) : (
                items.map((c) => {
                  const badges = badgesFuncoes(c);
                  const acessoBadge = badgeAcessoListagem(c);
                  const acessoVariant = badgeAcessoVariant(c);
                  return (
                    <tr
                      key={c.id}
                      className={!c.ativo ? 'opacity-60' : undefined}
                    >
                      <td className="font-medium">{c.nome}</td>
                      <td className="tabular-nums">{c.codigo || '—'}</td>
                      <td>{c.email || '—'}</td>
                      <td>
                        <div className="flex flex-wrap gap-1 max-w-md">
                          {badges.length ? (
                            badges.map((b) => (
                              <span
                                key={b.label}
                                className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${b.badgeClass}`}
                              >
                                {b.label}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="space-y-1">
                          <span
                            className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${
                              acessoVariant === 'destructive'
                                ? 'bg-destructive/15 text-destructive'
                                : acessoVariant === 'warning'
                                  ? 'bg-amber-500/15 text-amber-900 dark:text-amber-100'
                                  : acessoVariant === 'muted'
                                    ? 'bg-muted text-muted-foreground'
                                    : 'bg-primary/10 text-primary'
                            }`}
                            title={acessoColaboradorTooltip(c)}
                          >
                            {acessoBadge}
                          </span>
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={c.ativo ? 'Ativo' : 'Inativo'} />
                      </td>
                      <td>
    {confirmandoId === c.id ? (
      <div className="flex items-center gap-1 text-xs">
        <span className="text-destructive font-medium whitespace-nowrap">Excluir?</span>
        <button
          type="button"
          className="erp-btn-destructive erp-btn-sm"
          onClick={(e) => { e.stopPropagation(); void handleDeleteConfirm(c); }}
        >
          Sim
        </button>
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm"
          onClick={(e) => { e.stopPropagation(); setConfirmandoId(null); }}
        >
          Não
        </button>
      </div>
    ) : (
      <div className="flex gap-1">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); openEdit(c); }}
          className="erp-btn-ghost erp-btn-sm text-foreground/70 hover:text-primary"
          title="Editar colaborador"
          aria-label="Editar colaborador"
        >
          <Pencil className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setConfirmandoId(c.id); }}
          className="erp-btn-ghost erp-btn-sm text-foreground/70 hover:text-destructive"
          title="Excluir colaborador"
          aria-label="Excluir colaborador"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    )}
  </td>
                    </tr>
                  );
                })
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
}