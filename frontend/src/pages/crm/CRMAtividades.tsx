import { useEffect, useState } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal, ModalFooterActions } from '@/components/Modal';
import { NexusCard } from '@/components/nexus/NexusCard';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { PaginationControls } from '@/components/list/PaginationControls';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { apiErrorMessage } from '@/services/api/config';
import {
  crmService,
  type CrmAtividade,
  type CrmAtividadeListParams,
  type CrmAtividadePayload,
  type CrmLead,
  type CrmOportunidade,
} from '@/services/api/crm';
import type { ListQueryParams } from '@/lib/apiList';

const activityTypes = [
  ['LIGACAO', 'Ligação'],
  ['EMAIL', 'E-mail'],
  ['WHATSAPP', 'WhatsApp'],
  ['REUNIAO', 'Reunião'],
  ['VISITA', 'Visita'],
  ['TAREFA', 'Tarefa'],
  ['NOTA', 'Nota'],
  ['OUTRA', 'Outra'],
] as const;

const activityTypeLabel = Object.fromEntries(activityTypes) as Record<string, string>;

const emptyForm = {
  titulo: '',
  tipo: 'TAREFA',
  status: 'PENDENTE',
  lead_id: '',
  oportunidade_id: '',
  agendada_para: '',
  descricao: '',
};

type ActivityForm = typeof emptyForm;

const fetchActivitiesPage = (params: ListQueryParams) =>
  crmService.atividades.listPaginated(params as CrmAtividadeListParams);

const formatDateTime = (value: string | null) => {
  if (!value) return 'Sem data';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

const toDateTimeInput = (value: string | null) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60 * 1000).toISOString().slice(0, 16);
};

const CRMAtividades = () => {
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
  } = usePaginatedList<CrmAtividade>({ fetchPage: fetchActivitiesPage });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CrmAtividade | null>(null);
  const [form, setForm] = useState<ActivityForm>({ ...emptyForm });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [leads, setLeads] = useState<CrmLead[]>([]);
  const [oportunidades, setOportunidades] = useState<CrmOportunidade[]>([]);

  useEffect(() => {
    let active = true;
    Promise.all([
      crmService.leads.getAll({ limit: 200 }),
      crmService.oportunidades.getAll({ limit: 200 }),
    ])
      .then(([loadedLeads, loadedOportunidades]) => {
        if (!active) return;
        setLeads(loadedLeads);
        setOportunidades(loadedOportunidades);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (atividade: CrmAtividade) => {
    setEditing(atividade);
    setForm({
      titulo: atividade.titulo,
      tipo: atividade.tipo || 'TAREFA',
      status: atividade.status || 'PENDENTE',
      lead_id: atividade.lead_id ? String(atividade.lead_id) : '',
      oportunidade_id: atividade.oportunidade_id ? String(atividade.oportunidade_id) : '',
      agendada_para: toDateTimeInput(atividade.agendada_para),
      descricao: atividade.descricao || '',
    });
    setFormError(null);
    setModalOpen(true);
  };

  const field = (key: keyof ActivityForm, value: string) =>
    setForm((previous) => ({ ...previous, [key]: value }));

  const save = async () => {
    if (!form.titulo.trim()) {
      setFormError('Informe o título da atividade.');
      return;
    }
    if (!form.lead_id && !form.oportunidade_id) {
      setFormError('Vincule a atividade a um Lead ou a uma Oportunidade.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const payload: CrmAtividadePayload = {
        titulo: form.titulo.trim(),
        tipo: form.tipo,
        status: form.status,
        lead_id: form.lead_id ? Number(form.lead_id) : null,
        oportunidade_id: form.oportunidade_id ? Number(form.oportunidade_id) : null,
        agendada_para: form.agendada_para || null,
        descricao: form.descricao.trim(),
      };
      if (editing) await crmService.atividades.update(editing.id, payload);
      else await crmService.atividades.create(payload);
      setModalOpen(false);
      void reload();
    } catch (err) {
      setFormError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (atividade: CrmAtividade) => {
    if (!confirm(`Excluir a atividade "${atividade.titulo}"?`)) return;
    try {
      await crmService.atividades.delete(atividade.id);
      void reload();
    } catch (err) {
      alert(apiErrorMessage(err));
    }
  };

  const filteredOportunidades = form.lead_id
    ? oportunidades.filter((oportunidade) => !oportunidade.lead_id || String(oportunidade.lead_id) === form.lead_id)
    : oportunidades;

  return (
    <div>
      <PageHeader
        title="Atividades"
        description="Próximas ações, contatos e tarefas do relacionamento comercial."
        onAdd={openNew}
        addLabel="Nova atividade"
        searchValue={search}
        onSearch={setSearch}
      />

      <NexusCard className="mb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <select
            className="erp-select h-9 w-full text-sm sm:w-auto sm:min-w-[10rem]"
            value={filters.status || ''}
            onChange={(event) => setFilter('status', event.target.value)}
          >
            <option value="">Todos os status</option>
            <option value="PENDENTE">Pendentes</option>
            <option value="CONCLUIDA">Concluídas</option>
            <option value="CANCELADA">Canceladas</option>
          </select>
          <select
            className="erp-select h-9 w-full text-sm sm:w-auto sm:min-w-[10rem]"
            value={filters.tipo || ''}
            onChange={(event) => setFilter('tipo', event.target.value)}
          >
            <option value="">Todos os tipos</option>
            {activityTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
      </NexusCard>

      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={6} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable mobileMode="cards">
            <thead>
              <tr>
                <th>Atividade</th>
                <th>Vínculo</th>
                <th>Tipo</th>
                <th>Agendamento</th>
                <th>Status</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <EmptyState message="Nenhuma atividade encontrada." actionLabel="Nova atividade" onAction={openNew} />
                  </td>
                </tr>
              ) : (
                items.map((atividade) => (
                  <tr key={atividade.id}>
                    <td>
                      <div className="font-medium">{atividade.titulo}</div>
                      <div className="max-w-[20rem] truncate text-xs text-muted-foreground">{atividade.descricao || 'Sem descrição'}</div>
                    </td>
                    <td>
                      <div>{atividade.lead_nome || 'Sem Lead'}</div>
                      <div className="text-xs text-muted-foreground">{atividade.oportunidade_titulo || 'Sem oportunidade'}</div>
                    </td>
                    <td>{activityTypeLabel[atividade.tipo] || atividade.tipo || 'Outra'}</td>
                    <td>{formatDateTime(atividade.agendada_para)}</td>
                    <td><StatusBadge status={atividade.status || 'PENDENTE'} /></td>
                    <td>
                      <div className="flex gap-1">
                        <button type="button" onClick={() => openEdit(atividade)} className="erp-btn-ghost erp-btn-sm" title="Editar">
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button type="button" onClick={() => void remove(atividade)} className="erp-btn-ghost erp-btn-sm text-destructive" title="Excluir">
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

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar atividade' : 'Nova atividade'}
        size="lg"
        footer={<ModalFooterActions onCancel={() => setModalOpen(false)} onSave={() => void save()} saving={saving} />}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="sm:col-span-2 text-sm font-medium">Título *
            <input className="erp-input mt-1 w-full" value={form.titulo} onChange={(event) => field('titulo', event.target.value)} />
          </label>
          <label className="text-sm font-medium">Tipo
            <select className="erp-select mt-1 w-full" value={form.tipo} onChange={(event) => field('tipo', event.target.value)}>
              {activityTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">Status
            <select className="erp-select mt-1 w-full" value={form.status} onChange={(event) => field('status', event.target.value)}>
              <option value="PENDENTE">Pendente</option>
              <option value="CONCLUIDA">Concluída</option>
              <option value="CANCELADA">Cancelada</option>
            </select>
          </label>
          <label className="text-sm font-medium">Lead
            <select className="erp-select mt-1 w-full" value={form.lead_id} onChange={(event) => field('lead_id', event.target.value)}>
              <option value="">Selecionar Lead</option>
              {leads.map((lead) => <option key={lead.id} value={lead.id}>{lead.nome}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">Oportunidade
            <select className="erp-select mt-1 w-full" value={form.oportunidade_id} onChange={(event) => field('oportunidade_id', event.target.value)}>
              <option value="">Selecionar oportunidade</option>
              {filteredOportunidades.map((oportunidade) => <option key={oportunidade.id} value={oportunidade.id}>{oportunidade.titulo}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">Agendada para
            <input type="datetime-local" className="erp-input mt-1 w-full" value={form.agendada_para} onChange={(event) => field('agendada_para', event.target.value)} />
          </label>
          <label className="sm:col-span-2 text-sm font-medium">Descrição
            <textarea className="erp-input mt-1 min-h-24 w-full" value={form.descricao} onChange={(event) => field('descricao', event.target.value)} />
          </label>
        </div>
        {formError ? <p className="mt-4 text-sm text-destructive">{formError}</p> : null}
      </Modal>
    </div>
  );
};

export default CRMAtividades;
