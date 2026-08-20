import { useState } from 'react';
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
  type CrmLeadListParams,
  type CrmLeadPayload,
} from '@/services/api/crm';
import type { ListQueryParams } from '@/lib/apiList';

const emptyForm: CrmLeadPayload = {
  nome: '',
  cnpj: '',
  nome_contato: '',
  email: '',
  telefone: '',
  cidade: '',
  uf: '',
  origem: 'OUTRA',
  observacoes: '',
};

const fetchLeadsPage = (params: ListQueryParams) =>
  crmService.leads.listPaginated(params as CrmLeadListParams);

const CRMLeads = () => {
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
  } = usePaginatedList<CrmLead>({ fetchPage: fetchLeadsPage });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CrmLead | null>(null);
  const [form, setForm] = useState<CrmLeadPayload>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (lead: CrmLead) => {
    setEditing(lead);
    setForm({
      nome: lead.nome,
      cnpj: lead.cnpj,
      nome_contato: lead.nome_contato,
      email: lead.email,
      telefone: lead.telefone,
      cidade: lead.cidade,
      uf: lead.uf,
      origem: lead.origem,
      status: lead.status,
      observacoes: lead.observacoes,
    });
    setFormError(null);
    setModalOpen(true);
  };

  const save = async () => {
    if (!String(form.nome || '').trim()) {
      setFormError('Informe o nome do lead.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const payload: CrmLeadPayload = {
        ...form,
        nome: String(form.nome || '').trim(),
        cnpj: String(form.cnpj || '').trim(),
        nome_contato: String(form.nome_contato || '').trim(),
        email: String(form.email || '').trim(),
        telefone: String(form.telefone || '').trim(),
        cidade: String(form.cidade || '').trim(),
        uf: String(form.uf || '').trim().toUpperCase(),
        observacoes: String(form.observacoes || '').trim(),
      };
      if (editing) await crmService.leads.update(editing.id, payload);
      else await crmService.leads.create(payload);
      setModalOpen(false);
      void reload();
    } catch (err) {
      setFormError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (lead: CrmLead) => {
    if (!confirm(`Excluir o lead "${lead.nome}"?`)) return;
    try {
      await crmService.leads.delete(lead.id);
      void reload();
    } catch (err) {
      alert(apiErrorMessage(err));
    }
  };

  const field = (key: keyof CrmLeadPayload, value: string) =>
    setForm((previous) => ({ ...previous, [key]: value }));

  return (
    <div>
      <PageHeader
        title="Leads"
        description="Prospects, origens de contato e próximos potenciais clientes."
        onAdd={openNew}
        addLabel="Novo lead"
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
            <option value="NOVO">Novos</option>
            <option value="QUALIFICANDO">Em qualificação</option>
            <option value="CONVERTIDO">Convertidos</option>
            <option value="DESCARTADO">Descartados</option>
          </select>
          <select
            className="erp-select h-9 w-full text-sm sm:w-auto sm:min-w-[10rem]"
            value={filters.origem || ''}
            onChange={(event) => setFilter('origem', event.target.value)}
          >
            <option value="">Todas as origens</option>
            <option value="INDICACAO">Indicação</option>
            <option value="SITE">Site</option>
            <option value="WHATSAPP">WhatsApp</option>
            <option value="TELEFONE">Telefone</option>
            <option value="EVENTO">Evento</option>
            <option value="OUTRA">Outra</option>
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
                <th>Lead</th>
                <th>Contato</th>
                <th>Cidade/UF</th>
                <th>Origem</th>
                <th>Status</th>
                <th>Responsável</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState message="Nenhum lead encontrado." actionLabel="Novo lead" onAction={openNew} />
                  </td>
                </tr>
              ) : (
                items.map((lead) => (
                  <tr key={lead.id}>
                    <td>
                      <div className="font-medium">{lead.nome}</div>
                      <div className="text-xs text-muted-foreground">{lead.cnpj || 'CNPJ não informado'}</div>
                    </td>
                    <td>
                      <div>{lead.nome_contato || '—'}</div>
                      <div className="text-xs text-muted-foreground">{lead.email || lead.telefone || '—'}</div>
                    </td>
                    <td>{lead.cidade && lead.uf ? `${lead.cidade}/${lead.uf}` : lead.cidade || lead.uf || '—'}</td>
                    <td>{lead.origem || '—'}</td>
                    <td><StatusBadge status={lead.status || 'Novo'} /></td>
                    <td>{lead.responsavel_nome || 'Não atribuído'}</td>
                    <td>
                      <div className="flex gap-1">
                        <button type="button" onClick={() => openEdit(lead)} className="erp-btn-ghost erp-btn-sm" title="Editar">
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button type="button" onClick={() => void remove(lead)} className="erp-btn-ghost erp-btn-sm text-destructive" title="Excluir">
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
        title={editing ? 'Editar lead' : 'Novo lead'}
        size="lg"
        footer={<ModalFooterActions onCancel={() => setModalOpen(false)} onSave={() => void save()} saving={saving} />}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="sm:col-span-2 text-sm font-medium">Nome da empresa *
            <input className="erp-input mt-1 w-full" value={String(form.nome || '')} onChange={(event) => field('nome', event.target.value)} />
          </label>
          <label className="text-sm font-medium">CNPJ
            <input className="erp-input mt-1 w-full" value={String(form.cnpj || '')} onChange={(event) => field('cnpj', event.target.value)} placeholder="CNPJ numérico ou alfanumérico" />
          </label>
          <label className="text-sm font-medium">Nome do contato
            <input className="erp-input mt-1 w-full" value={String(form.nome_contato || '')} onChange={(event) => field('nome_contato', event.target.value)} />
          </label>
          <label className="text-sm font-medium">E-mail
            <input type="email" className="erp-input mt-1 w-full" value={String(form.email || '')} onChange={(event) => field('email', event.target.value)} />
          </label>
          <label className="text-sm font-medium">Telefone
            <input className="erp-input mt-1 w-full" value={String(form.telefone || '')} onChange={(event) => field('telefone', event.target.value)} />
          </label>
          <label className="text-sm font-medium">Cidade
            <input className="erp-input mt-1 w-full" value={String(form.cidade || '')} onChange={(event) => field('cidade', event.target.value)} />
          </label>
          <label className="text-sm font-medium">UF
            <input maxLength={2} className="erp-input mt-1 w-full uppercase" value={String(form.uf || '')} onChange={(event) => field('uf', event.target.value)} />
          </label>
          <label className="text-sm font-medium">Origem
            <select className="erp-select mt-1 w-full" value={String(form.origem || 'OUTRA')} onChange={(event) => field('origem', event.target.value)}>
              <option value="INDICACAO">Indicação</option>
              <option value="SITE">Site</option>
              <option value="WHATSAPP">WhatsApp</option>
              <option value="TELEFONE">Telefone</option>
              <option value="EVENTO">Evento</option>
              <option value="OUTRA">Outra</option>
            </select>
          </label>
          <label className="sm:col-span-2 text-sm font-medium">Observações
            <textarea className="erp-input mt-1 min-h-24 w-full" value={String(form.observacoes || '')} onChange={(event) => field('observacoes', event.target.value)} />
          </label>
        </div>
        {formError ? <p className="mt-4 text-sm text-destructive">{formError}</p> : null}
      </Modal>
    </div>
  );
};

export default CRMLeads;
