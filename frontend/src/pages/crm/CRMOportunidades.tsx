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
  type CrmLead,
  type CrmOportunidade,
  type CrmOportunidadeListParams,
  type CrmOportunidadePayload,
} from '@/services/api/crm';
import { clientesService } from '@/services/api/clientes';
import type { Cliente } from '@/types';
import type { ListQueryParams } from '@/lib/apiList';

type OpportunityForm = {
  titulo: string;
  status: string;
  etapa: string;
  lead_id: string;
  cliente_id: string;
  valor_estimado: string;
  probabilidade: string;
  previsao_fechamento: string;
  proxima_acao: string;
  motivo_perda: string;
  observacoes: string;
};

const emptyForm: OpportunityForm = {
  titulo: '',
  status: 'ABERTA',
  etapa: 'QUALIFICACAO',
  lead_id: '',
  cliente_id: '',
  valor_estimado: '0',
  probabilidade: '0',
  previsao_fechamento: '',
  proxima_acao: '',
  motivo_perda: '',
  observacoes: '',
};

const fetchOpportunitiesPage = (params: ListQueryParams) =>
  crmService.oportunidades.listPaginated(params as CrmOportunidadeListParams);

const CRMOportunidades = () => {
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
  } = usePaginatedList<CrmOportunidade>({ fetchPage: fetchOpportunitiesPage });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CrmOportunidade | null>(null);
  const [form, setForm] = useState<OpportunityForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [leads, setLeads] = useState<CrmLead[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);

  useEffect(() => {
    let active = true;
    Promise.all([crmService.leads.getAll({ limit: 100 }), clientesService.getAll({ limit: 100 })])
      .then(([loadedLeads, loadedClientes]) => {
        if (!active) return;
        setLeads(loadedLeads);
        setClientes(loadedClientes);
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

  const openEdit = (opportunity: CrmOportunidade) => {
    setEditing(opportunity);
    setForm({
      titulo: opportunity.titulo,
      status: opportunity.status,
      etapa: opportunity.etapa,
      lead_id: opportunity.lead_id ? String(opportunity.lead_id) : '',
      cliente_id: opportunity.cliente_id ? String(opportunity.cliente_id) : '',
      valor_estimado: opportunity.valor_estimado || '0',
      probabilidade: String(opportunity.probabilidade ?? 0),
      previsao_fechamento: opportunity.previsao_fechamento || '',
      proxima_acao: opportunity.proxima_acao || '',
      motivo_perda: opportunity.motivo_perda || '',
      observacoes: opportunity.observacoes || '',
    });
    setFormError(null);
    setModalOpen(true);
  };

  const save = async () => {
    if (!form.titulo.trim()) {
      setFormError('Informe o título da oportunidade.');
      return;
    }
    if (!form.lead_id && !form.cliente_id) {
      setFormError('Vincule um lead ou um cliente.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const payload: CrmOportunidadePayload = {
        titulo: form.titulo.trim(),
        status: form.status,
        etapa: form.etapa,
        lead_id: form.lead_id ? Number(form.lead_id) : null,
        cliente_id: form.cliente_id ? Number(form.cliente_id) : null,
        valor_estimado: form.valor_estimado || '0',
        probabilidade: Math.max(0, Math.min(100, Number(form.probabilidade) || 0)),
        previsao_fechamento: form.previsao_fechamento || null,
        proxima_acao: form.proxima_acao || null,
        motivo_perda: form.motivo_perda.trim(),
        observacoes: form.observacoes.trim(),
      };
      if (editing) await crmService.oportunidades.update(editing.id, payload);
      else await crmService.oportunidades.create(payload);
      setModalOpen(false);
      void reload();
    } catch (err) {
      setFormError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (opportunity: CrmOportunidade) => {
    if (!confirm(`Excluir a oportunidade "${opportunity.titulo}"?`)) return;
    try {
      await crmService.oportunidades.delete(opportunity.id);
      void reload();
    } catch (err) {
      alert(apiErrorMessage(err));
    }
  };

  const field = (key: keyof OpportunityForm, value: string) =>
    setForm((previous) => ({ ...previous, [key]: value }));

  return (
    <div>
      <PageHeader
        title="Oportunidades"
        description="Acompanhe negociações, previsão de fechamento e valor potencial."
        onAdd={openNew}
        addLabel="Nova oportunidade"
        searchValue={search}
        onSearch={setSearch}
      />

      <NexusCard className="mb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <select className="erp-select h-9 w-full text-sm sm:w-auto sm:min-w-[10rem]" value={filters.status || ''} onChange={(event) => setFilter('status', event.target.value)}>
            <option value="">Todos os status</option>
            <option value="ABERTA">Abertas</option>
            <option value="GANHA">Ganhas</option>
            <option value="PERDIDA">Perdidas</option>
          </select>
          <select className="erp-select h-9 w-full text-sm sm:w-auto sm:min-w-[12rem]" value={filters.etapa || ''} onChange={(event) => setFilter('etapa', event.target.value)}>
            <option value="">Todas as etapas</option>
            <option value="QUALIFICACAO">Qualificação</option>
            <option value="ESPECIFICACAO">Especificação técnica</option>
            <option value="PROPOSTA">Proposta</option>
            <option value="NEGOCIACAO">Negociação</option>
            <option value="FECHAMENTO">Fechamento</option>
          </select>
        </div>
      </NexusCard>

      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={7} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable mobileMode="cards">
            <thead>
              <tr>
                <th>Oportunidade</th>
                <th>Cliente/Lead</th>
                <th>Etapa</th>
                <th>Valor estimado</th>
                <th>Previsão</th>
                <th>Status</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState message="Nenhuma oportunidade encontrada." actionLabel="Nova oportunidade" onAction={openNew} />
                  </td>
                </tr>
              ) : (
                items.map((opportunity) => (
                  <tr key={opportunity.id}>
                    <td>
                      <div className="font-medium">{opportunity.titulo}</div>
                      <div className="text-xs text-muted-foreground">{opportunity.responsavel_nome || 'Sem responsável'}</div>
                    </td>
                    <td>{opportunity.cliente_nome || opportunity.lead_nome || '—'}</td>
                    <td>{opportunity.etapa || '—'}</td>
                    <td className="tabular-nums">R$ {Number(opportunity.valor_estimado || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                    <td>{opportunity.previsao_fechamento ? new Date(`${opportunity.previsao_fechamento}T12:00:00`).toLocaleDateString('pt-BR') : '—'}</td>
                    <td><StatusBadge status={opportunity.status || 'Aberta'} /></td>
                    <td>
                      <div className="flex gap-1">
                        <button type="button" onClick={() => openEdit(opportunity)} className="erp-btn-ghost erp-btn-sm" title="Editar">
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button type="button" onClick={() => void remove(opportunity)} className="erp-btn-ghost erp-btn-sm text-destructive" title="Excluir">
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
            <PaginationControls page={page} pageSize={pageSize} count={count} totalPages={totalPages} onPageChange={setPage} onPageSizeChange={setPageSize} />
          ) : null}
        </DataTableShell>
      ) : null}

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar oportunidade' : 'Nova oportunidade'}
        size="lg"
        footer={<ModalFooterActions onCancel={() => setModalOpen(false)} onSave={() => void save()} saving={saving} />}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="sm:col-span-2 text-sm font-medium">Título *
            <input className="erp-input mt-1 w-full" value={form.titulo} onChange={(event) => field('titulo', event.target.value)} />
          </label>
          <label className="text-sm font-medium">Lead
            <select className="erp-select mt-1 w-full" value={form.lead_id} onChange={(event) => field('lead_id', event.target.value)}>
              <option value="">Nenhum lead</option>
              {leads.map((lead) => <option key={lead.id} value={lead.id}>{lead.nome}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">Cliente
            <select className="erp-select mt-1 w-full" value={form.cliente_id} onChange={(event) => field('cliente_id', event.target.value)}>
              <option value="">Nenhum cliente</option>
              {clientes.map((cliente) => <option key={cliente.id} value={cliente.id}>{cliente.razao_social}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">Etapa
            <select className="erp-select mt-1 w-full" value={form.etapa} onChange={(event) => field('etapa', event.target.value)}>
              <option value="QUALIFICACAO">Qualificação</option>
              <option value="ESPECIFICACAO">Especificação técnica</option>
              <option value="PROPOSTA">Proposta</option>
              <option value="NEGOCIACAO">Negociação</option>
              <option value="FECHAMENTO">Fechamento</option>
            </select>
          </label>
          <label className="text-sm font-medium">Status
            <select className="erp-select mt-1 w-full" value={form.status} onChange={(event) => field('status', event.target.value)}>
              <option value="ABERTA">Aberta</option>
              <option value="GANHA">Ganha</option>
              <option value="PERDIDA">Perdida</option>
            </select>
          </label>
          <label className="text-sm font-medium">Valor estimado
            <input type="number" min="0" step="0.01" className="erp-input mt-1 w-full" value={form.valor_estimado} onChange={(event) => field('valor_estimado', event.target.value)} />
          </label>
          <label className="text-sm font-medium">Probabilidade (%)
            <input type="number" min="0" max="100" className="erp-input mt-1 w-full" value={form.probabilidade} onChange={(event) => field('probabilidade', event.target.value)} />
          </label>
          <label className="text-sm font-medium">Previsão de fechamento
            <input type="date" className="erp-input mt-1 w-full" value={form.previsao_fechamento} onChange={(event) => field('previsao_fechamento', event.target.value)} />
          </label>
          <label className="text-sm font-medium">Próxima ação
            <input type="date" className="erp-input mt-1 w-full" value={form.proxima_acao} onChange={(event) => field('proxima_acao', event.target.value)} />
          </label>
          <label className="sm:col-span-2 text-sm font-medium">Motivo da perda
            <input className="erp-input mt-1 w-full" value={form.motivo_perda} onChange={(event) => field('motivo_perda', event.target.value)} />
          </label>
          <label className="sm:col-span-2 text-sm font-medium">Observações
            <textarea className="erp-input mt-1 min-h-24 w-full" value={form.observacoes} onChange={(event) => field('observacoes', event.target.value)} />
          </label>
        </div>
        {formError ? <p className="mt-4 text-sm text-destructive">{formError}</p> : null}
      </Modal>
    </div>
  );
};

export default CRMOportunidades;
