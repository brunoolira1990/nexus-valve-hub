import { useCallback, useMemo, useState } from 'react';
import { Ban, MoreHorizontal, Pencil, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import { ExpedicaoFormModal } from '@/components/expedicao/ExpedicaoFormModal';
import { Modal } from '@/components/Modal';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { EmptyState } from '@/components/nexus/EmptyState';
import { NexusCard } from '@/components/nexus/NexusCard';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { PaginationControls } from '@/components/list/PaginationControls';
import { ErrorState } from '@/components/list/ListStates';
import { expedicaoService } from '@/services/api/expedicao';
import { apiErrorMessage } from '@/services/api/config';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import type { ExpedicaoItem, ExpedicaoResumo, StatusExpedicao } from '@/types/expedicao';
import { STATUS_EXPEDICAO, TIPOS_OPERACAO_EXPEDICAO } from '@/types/expedicao';
import {
  fmtDataBr,
  fmtDateTimeBr,
  LABEL_STATUS_EXPEDICAO,
  LABEL_TIPO_OPERACAO,
  vinculosResumo,
} from '@/lib/expedicaoUi';

const KPI_CARDS: { key: keyof ExpedicaoResumo; label: string; filter?: { status: StatusExpedicao } }[] = [
  { key: 'total', label: 'Total' },
  { key: 'aguardando_separacao', label: 'Aguard. separação', filter: { status: 'AGUARDANDO_SEPARACAO' } },
  { key: 'aguardando_retirada_fornecedor', label: 'Aguard. retirada fornec.', filter: { status: 'AGUARDANDO_RETIRADA_FORNECEDOR' } },
  { key: 'motorista_enviado', label: 'Motorista enviado', filter: { status: 'MOTORISTA_ENVIADO' } },
  { key: 'em_transito', label: 'Em trânsito', filter: { status: 'EM_TRANSITO' } },
  { key: 'entregue_cliente', label: 'Entregue cliente', filter: { status: 'ENTREGUE_CLIENTE' } },
  { key: 'ocorrencia', label: 'Ocorrências', filter: { status: 'OCORRENCIA' } },
  { key: 'cancelado', label: 'Canceladas', filter: { status: 'CANCELADO' } },
];

const Expedicao = () => {
  const [resumo, setResumo] = useState<ExpedicaoResumo | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [statusModal, setStatusModal] = useState<ExpedicaoItem | null>(null);
  const [novoStatus, setNovoStatus] = useState<StatusExpedicao>('AGUARDANDO_SEPARACAO');
  const [ocorrenciaDesc, setOcorrenciaDesc] = useState('');
  const [cancelModal, setCancelModal] = useState<ExpedicaoItem | null>(null);
  const [cancelMotivo, setCancelMotivo] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

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
    setFilters,
    loading,
    error,
    reload,
  } = usePaginatedList<ExpedicaoItem>({
    fetchPage: async (params) => {
      const data = await expedicaoService.listPaginated(params);
      if (data.resumo) setResumo(data.resumo);
      return data;
    },
  });

  const filterParams = useMemo(
    () => ({
      search: filters.search || search || '',
      status: filters.status || '',
      tipo_operacao: filters.tipo_operacao || '',
    }),
    [filters, search],
  );

  const applyKpiFilter = (filter?: { status: StatusExpedicao }) => {
    if (!filter) {
      setFilters({ status: '', tipo_operacao: '' });
      return;
    }
    setFilters({ status: filter.status, tipo_operacao: '' });
  };

  const openCreate = () => {
    setEditId(null);
    setFormOpen(true);
  };

  const openEdit = (item: ExpedicaoItem) => {
    setEditId(item.id);
    setFormOpen(true);
  };

  const handleDelete = async (item: ExpedicaoItem) => {
    if (!confirm(`Excluir expedição ${item.codigo}? Somente rascunhos podem ser excluídos.`)) return;
    try {
      await expedicaoService.delete(item.id);
      toast.success('Expedição excluída.');
      void reload();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível excluir.' }));
    }
  };

  const handleAlterarStatus = async () => {
    if (!statusModal) return;
    setActionLoading(true);
    try {
      await expedicaoService.alterarStatus(statusModal.id, {
        status: novoStatus,
        ocorrencia_descricao: novoStatus === 'OCORRENCIA' ? ocorrenciaDesc : undefined,
      });
      toast.success('Status atualizado.');
      setStatusModal(null);
      void reload();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível alterar o status.' }));
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelar = async () => {
    if (!cancelModal) return;
    setActionLoading(true);
    try {
      await expedicaoService.cancelar(cancelModal.id, cancelMotivo);
      toast.success('Expedição cancelada.');
      setCancelModal(null);
      setCancelMotivo('');
      void reload();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível cancelar.' }));
    } finally {
      setActionLoading(false);
    }
  };

  const openStatusModal = useCallback((item: ExpedicaoItem) => {
    setStatusModal(item);
    setNovoStatus(item.status === 'RASCUNHO' ? 'AGUARDANDO_SEPARACAO' : item.status);
    setOcorrenciaDesc(item.ocorrencia_descricao || '');
  }, []);

  return (
    <div>
      <PageHeader
        title="Expedição / Logística"
        description="Controle operacional manual de entregas, retiradas, motorista e transportadora. Vínculos referenciais apenas — sem movimentação de estoque, financeiro ou fiscal."
        onAdd={openCreate}
        addLabel="Nova expedição"
        searchValue={search}
        onSearch={setSearch}
      />

      {resumo ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 mb-4">
          {KPI_CARDS.map((card) => (
            <button
              key={card.key}
              type="button"
              className="text-left rounded-lg border border-border bg-card px-3 py-2 hover:bg-muted/50 transition-colors"
              onClick={() => applyKpiFilter(card.filter)}
            >
              <div className="text-2xl font-semibold tabular-nums">{resumo[card.key] ?? 0}</div>
              <div className="text-xs text-muted-foreground leading-snug">{card.label}</div>
            </button>
          ))}
        </div>
      ) : null}

      <NexusCard className="p-4 mb-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="erp-label">Status</label>
            <select
              className="erp-select mt-1 w-full"
              value={filterParams.status}
              onChange={(e) => setFilter('status', e.target.value)}
            >
              <option value="">Todos</option>
              {STATUS_EXPEDICAO.map((s) => (
                <option key={s} value={s}>
                  {LABEL_STATUS_EXPEDICAO[s]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Tipo de operação</label>
            <select
              className="erp-select mt-1 w-full"
              value={filterParams.tipo_operacao}
              onChange={(e) => setFilter('tipo_operacao', e.target.value)}
            >
              <option value="">Todos</option>
              {TIPOS_OPERACAO_EXPEDICAO.map((t) => (
                <option key={t} value={t}>
                  {LABEL_TIPO_OPERACAO[t]}
                </option>
              ))}
            </select>
          </div>
        </div>
      </NexusCard>

      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={8} cols={8} /> : null}

      {!loading && !error ? (
        <DataTableShell>
          <DataTable mobileMode="cards">
            <thead>
              <tr>
                <th>Código</th>
                <th>Tipo</th>
                <th>Status</th>
                <th>Cliente / Fornecedor</th>
                <th>Transportadora / Motorista</th>
                <th>Prev. entrega</th>
                <th>Vínculos</th>
                <th className="w-28">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <EmptyState message="Nenhuma expedição encontrada." actionLabel="Nova expedição" onAction={openCreate} />
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id}>
                    <td className="font-medium tabular-nums">{item.codigo}</td>
                    <td className="text-sm">{item.tipo_operacao_label || LABEL_TIPO_OPERACAO[item.tipo_operacao]}</td>
                    <td>
                      <StatusBadge status={item.status_label || LABEL_STATUS_EXPEDICAO[item.status]} />
                    </td>
                    <td className="text-sm">
                      <div>{item.cliente_nome || '—'}</div>
                      {item.fornecedor_nome ? (
                        <div className="text-xs text-muted-foreground">{item.fornecedor_nome}</div>
                      ) : null}
                    </td>
                    <td className="text-sm">
                      <div>{item.transportadora_nome || '—'}</div>
                      {item.motorista_nome ? (
                        <div className="text-xs text-muted-foreground">{item.motorista_nome}</div>
                      ) : null}
                    </td>
                    <td className="text-sm tabular-nums">{fmtDataBr(item.data_prevista_entrega)}</td>
                    <td className="text-xs text-muted-foreground max-w-[180px] truncate" title={vinculosResumo(item)}>
                      {vinculosResumo(item)}
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        <button type="button" className="erp-btn-ghost erp-btn-sm" title="Editar" onClick={() => openEdit(item)}>
                          <Pencil className="h-4 w-4" />
                        </button>
                        {item.status !== 'CANCELADO' ? (
                          <button
                            type="button"
                            className="erp-btn-ghost erp-btn-sm"
                            title="Alterar status"
                            onClick={() => openStatusModal(item)}
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </button>
                        ) : null}
                        {item.status !== 'CANCELADO' ? (
                          <button
                            type="button"
                            className="erp-btn-ghost erp-btn-sm text-destructive"
                            title="Cancelar"
                            onClick={() => setCancelModal(item)}
                          >
                            <Ban className="h-4 w-4" />
                          </button>
                        ) : null}
                        {item.status === 'RASCUNHO' ? (
                          <button
                            type="button"
                            className="erp-btn-ghost erp-btn-sm text-destructive"
                            title="Excluir rascunho"
                            onClick={() => void handleDelete(item)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        ) : null}
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

      <ExpedicaoFormModal
        expedicaoId={editId}
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={() => void reload()}
      />

      <Modal
        isOpen={!!statusModal}
        onClose={() => setStatusModal(null)}
        title={statusModal ? `Alterar status — ${statusModal.codigo}` : 'Alterar status'}
        size="sm"
        footer={
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 p-4">
            <button type="button" className="erp-btn-secondary" onClick={() => setStatusModal(null)} disabled={actionLoading}>
              Fechar
            </button>
            <button type="button" className="erp-btn-primary" onClick={() => void handleAlterarStatus()} disabled={actionLoading}>
              {actionLoading ? 'Salvando…' : 'Confirmar'}
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="erp-label">Novo status</label>
            <select
              className="erp-select mt-1 w-full"
              value={novoStatus}
              onChange={(e) => setNovoStatus(e.target.value as StatusExpedicao)}
            >
              {STATUS_EXPEDICAO.filter((s) => s !== 'RASCUNHO').map((s) => (
                <option key={s} value={s}>
                  {LABEL_STATUS_EXPEDICAO[s]}
                </option>
              ))}
            </select>
          </div>
          {novoStatus === 'OCORRENCIA' ? (
            <div>
              <label className="erp-label">Descrição da ocorrência</label>
              <textarea
                className="erp-input mt-1 w-full min-h-[80px]"
                value={ocorrenciaDesc}
                onChange={(e) => setOcorrenciaDesc(e.target.value)}
              />
            </div>
          ) : null}
          {statusModal?.data_hora_entrega_real ? (
            <p className="text-xs text-muted-foreground">
              Entrega real registrada: {fmtDateTimeBr(statusModal.data_hora_entrega_real)}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        isOpen={!!cancelModal}
        onClose={() => setCancelModal(null)}
        title={cancelModal ? `Cancelar — ${cancelModal.codigo}` : 'Cancelar expedição'}
        size="sm"
        footer={
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 p-4">
            <button type="button" className="erp-btn-secondary" onClick={() => setCancelModal(null)} disabled={actionLoading}>
              Voltar
            </button>
            <button type="button" className="erp-btn-destructive" onClick={() => void handleCancelar()} disabled={actionLoading}>
              {actionLoading ? 'Cancelando…' : 'Confirmar cancelamento'}
            </button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            O cancelamento é operacional e não reverte estoque, financeiro ou documentos fiscais.
          </p>
          <div>
            <label className="erp-label">Motivo (opcional)</label>
            <textarea
              className="erp-input mt-1 w-full min-h-[80px]"
              value={cancelMotivo}
              onChange={(e) => setCancelMotivo(e.target.value)}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Expedicao;
