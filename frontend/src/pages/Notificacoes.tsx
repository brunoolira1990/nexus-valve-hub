import { Archive, Check, ExternalLink, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { NexusCard } from '@/components/nexus/NexusCard';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { PaginationControls } from '@/components/list/PaginationControls';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { apiErrorMessage } from '@/services/api/config';
import {
  notificacoesService,
  type Notificacao,
  type NotificacaoListParams,
} from '@/services/api/notificacoes';
import type { ListQueryParams } from '@/lib/apiList';

const modules = [
  ['CRM', 'CRM'],
  ['COMERCIAL', 'Comercial'],
  ['FINANCEIRO', 'Financeiro'],
  ['ESTOQUE', 'Estoque'],
  ['QUALIDADE', 'Qualidade'],
  ['COMPRAS', 'Compras'],
  ['FISCAL', 'Fiscal'],
  ['SISTEMA', 'Sistema'],
] as const;

const priorities = [
  ['CRITICA', 'Crítica'],
  ['ALTA', 'Alta'],
  ['NORMAL', 'Normal'],
  ['BAIXA', 'Baixa'],
] as const;

const priorityClass: Record<string, string> = {
  CRITICA: 'bg-destructive/10 text-destructive',
  ALTA: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  NORMAL: 'bg-primary/10 text-primary',
  BAIXA: 'bg-muted text-muted-foreground',
};

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

const fetchNotificationsPage = (params: ListQueryParams) =>
  notificacoesService.listPaginated(params as NotificacaoListParams);

const Notificacoes = () => {
  const navigate = useNavigate();
  const [actionError, setActionError] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);
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
  } = usePaginatedList<Notificacao>({ fetchPage: fetchNotificationsPage });

  const markRead = async (item: Notificacao) => {
    if (item.lida) return;
    setActionError(null);
    try {
      await notificacoesService.marcarLida(item.id);
      void reload();
    } catch (err) {
      setActionError(apiErrorMessage(err, { fallback: 'Não foi possível marcar a notificação como lida.' }));
    }
  };

  const archive = async (item: Notificacao) => {
    setActionError(null);
    try {
      await notificacoesService.arquivar(item.id);
      void reload();
    } catch (err) {
      setActionError(apiErrorMessage(err, { fallback: 'Não foi possível arquivar a notificação.' }));
    }
  };

  const markAllRead = async () => {
    setActionError(null);
    setMarkingAll(true);
    try {
      await notificacoesService.marcarTodasLidas();
      void reload();
    } catch (err) {
      setActionError(apiErrorMessage(err, { fallback: 'Não foi possível marcar todas as notificações.' }));
    } finally {
      setMarkingAll(false);
    }
  };

  const openNotification = async (item: Notificacao) => {
    await markRead(item);
    if (item.url_destino) navigate(item.url_destino);
  };

  return (
    <div>
      <PageHeader
        title="Notificações"
        description="Acompanhe pendências, eventos e ações importantes dos módulos do ERP."
        searchValue={search}
        onSearch={setSearch}
      />

      <NexusCard className="mb-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <select
              className="erp-select h-9 w-full text-sm sm:w-auto sm:min-w-[10rem]"
              value={filters.modulo || ''}
              onChange={(event) => setFilter('modulo', event.target.value)}
              aria-label="Filtrar por módulo"
            >
              <option value="">Todos os módulos</option>
              {modules.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <select
              className="erp-select h-9 w-full text-sm sm:w-auto sm:min-w-[10rem]"
              value={filters.prioridade || ''}
              onChange={(event) => setFilter('prioridade', event.target.value)}
              aria-label="Filtrar por prioridade"
            >
              <option value="">Todas as prioridades</option>
              {priorities.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <select
              className="erp-select h-9 w-full text-sm sm:w-auto sm:min-w-[10rem]"
              value={filters.lida || ''}
              onChange={(event) => setFilter('lida', event.target.value)}
              aria-label="Filtrar por leitura"
            >
              <option value="">Todas</option>
              <option value="false">Não lidas</option>
              <option value="true">Lidas</option>
            </select>
            <label className="inline-flex h-9 items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={filters.incluir_arquivadas === 'true'}
                onChange={(event) => setFilter('incluir_arquivadas', event.target.checked ? 'true' : '')}
              />
              Incluir arquivadas
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="erp-btn-secondary erp-btn-sm" onClick={() => void reload()} title="Atualizar">
              <RefreshCw className="h-4 w-4" /> Atualizar
            </button>
            <button type="button" className="erp-btn-primary erp-btn-sm" onClick={() => void markAllRead()} disabled={markingAll}>
              <Check className="h-4 w-4" /> {markingAll ? 'Marcando...' : 'Marcar todas como lidas'}
            </button>
          </div>
        </div>
      </NexusCard>

      {actionError ? <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{actionError}</p> : null}
      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={7} cols={6} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable mobileMode="cards">
            <thead>
              <tr>
                <th>Notificação</th>
                <th>Módulo</th>
                <th>Prioridade</th>
                <th>Data</th>
                <th>Status</th>
                <th className="w-28">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <EmptyState message="Nenhuma notificação encontrada para os filtros selecionados." />
                  </td>
                </tr>
              ) : items.map((item) => (
                <tr key={item.id} className={item.lida ? '' : 'bg-primary/[0.025]'}>
                  <td>
                    <button type="button" className="max-w-[34rem] text-left" onClick={() => void openNotification(item)}>
                      <div className="font-medium text-foreground hover:text-primary">{item.titulo}</div>
                      <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.mensagem}</div>
                    </button>
                  </td>
                  <td>
                    <div className="font-medium">{item.modulo_label}</div>
                    <div className="text-xs text-muted-foreground">{item.tipo_label}</div>
                  </td>
                  <td>
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${priorityClass[item.prioridade] || priorityClass.NORMAL}`}>
                      {item.prioridade_label}
                    </span>
                  </td>
                  <td className="whitespace-nowrap text-sm">{formatDateTime(item.criado_em)}</td>
                  <td><StatusBadge status={item.lida ? 'LIDA' : 'NAO_LIDA'} /></td>
                  <td>
                    <div className="flex gap-1">
                      {!item.lida ? (
                        <button type="button" className="erp-btn-ghost erp-btn-sm" title="Marcar como lida" onClick={() => void markRead(item)}>
                          <Check className="h-4 w-4" />
                        </button>
                      ) : null}
                      {!item.arquivada ? (
                        <button type="button" className="erp-btn-ghost erp-btn-sm" title="Arquivar" onClick={() => void archive(item)}>
                          <Archive className="h-4 w-4" />
                        </button>
                      ) : null}
                      {item.url_destino ? (
                        <button type="button" className="erp-btn-ghost erp-btn-sm" title="Abrir" onClick={() => void openNotification(item)}>
                          <ExternalLink className="h-4 w-4" />
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
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

export default Notificacoes;
