import { useState } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { ColaboradorAcessoSection } from '@/components/cadastros/ColaboradorAcessoSection';
import { CriarUsuarioColaboradorModal } from '@/components/cadastros/CriarUsuarioColaboradorModal';
import { DefinirPerfilAcessoModal } from '@/components/cadastros/DefinirPerfilAcessoModal';
import { colaboradoresService, type ColaboradorListParams } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import type { Colaborador, ColaboradorFuncao } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { NexusCard } from '@/components/nexus/NexusCard';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { badgeAcessoListagem, acessoColaboradorTooltip, badgeAcessoVariant } from '@/lib/colaboradorAcesso';
import { clearAppContextoCache } from '@/hooks/useAppContexto';
import type { ListQueryParams } from '@/lib/apiList';

type ColaboradorForm = {
  nome: string;
  codigo: string;
  email: string;
  telefone: string;
  cargo: string;
  departamento: string;
  ativo: boolean;
  observacoes: string;
  eh_vendedor: boolean;
  eh_comprador: boolean;
  eh_responsavel_fiscal: boolean;
  eh_responsavel_financeiro: boolean;
  eh_responsavel_estoque: boolean;
  eh_responsavel_qualidade: boolean;
  eh_administrador: boolean;
};

const emptyForm: ColaboradorForm = {
  nome: '',
  codigo: '',
  email: '',
  telefone: '',
  cargo: '',
  departamento: '',
  ativo: true,
  observacoes: '',
  eh_vendedor: false,
  eh_comprador: false,
  eh_responsavel_fiscal: false,
  eh_responsavel_financeiro: false,
  eh_responsavel_estoque: false,
  eh_responsavel_qualidade: false,
  eh_administrador: false,
};

const FUNCAO_CAMPOS: { key: keyof ColaboradorForm; label: string; badgeClass: string }[] = [
  { key: 'eh_vendedor', label: 'Vendedor', badgeClass: 'bg-emerald-600/15 text-emerald-800 dark:text-emerald-200' },
  { key: 'eh_comprador', label: 'Comprador', badgeClass: 'bg-blue-600/15 text-blue-800 dark:text-blue-200' },
  { key: 'eh_responsavel_fiscal', label: 'Fiscal', badgeClass: 'bg-violet-600/15 text-violet-800 dark:text-violet-200' },
  { key: 'eh_responsavel_financeiro', label: 'Financeiro', badgeClass: 'bg-amber-600/15 text-amber-900 dark:text-amber-100' },
  { key: 'eh_responsavel_estoque', label: 'Estoque', badgeClass: 'bg-cyan-600/15 text-cyan-900 dark:text-cyan-100' },
  { key: 'eh_responsavel_qualidade', label: 'Qualidade', badgeClass: 'bg-pink-600/15 text-pink-900 dark:text-pink-100' },
  { key: 'eh_administrador', label: 'Admin', badgeClass: 'bg-slate-600/15 text-slate-800 dark:text-slate-200' },
];

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

function colaboradorToForm(c: Colaborador): ColaboradorForm {
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
  return FUNCAO_CAMPOS.filter((f) => Boolean(c[f.key as keyof Colaborador])).map((f) => ({
    label: f.label,
    badgeClass: f.badgeClass,
  }));
}

const fetchColaboradoresPage = (params: ListQueryParams) => {
  const { ativo, funcao, ...rest } = params;
  const listParams: ColaboradorListParams = { ...rest };
  if (funcao) listParams.funcao = funcao as ColaboradorFuncao;
  if (ativo === 'true') listParams.ativo = true;
  else if (ativo === 'false') listParams.ativo = false;
  else listParams.ativo = 'all';
  return colaboradoresService.listPaginated(listParams);
};

const Colaboradores = () => {
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
  const filtroFuncao = (filters.funcao || '') as ColaboradorFuncao | '';
  const filtroAtivo =
    filters.ativo === 'true' ? 'active' : filters.ativo === 'false' ? 'inactive' : 'all';
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Colaborador | null>(null);
  const [form, setForm] = useState<ColaboradorForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [listModal, setListModal] = useState<{ type: 'criar' | 'perfil'; c: Colaborador } | null>(null);

  const refreshEditing = async () => {
    clearAppContextoCache();
    await reload();
    if (editing?.id) {
      const fresh = await colaboradoresService.getById(editing.id);
      setEditing(fresh);
    }
  };

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = async (c: Colaborador) => {
    setFormError(null);
    try {
      const fresh = await colaboradoresService.getById(c.id);
      setEditing(fresh);
      setForm(colaboradorToForm(fresh));
      setModalOpen(true);
    } catch (err) {
      alert(apiErrorMessage(err));
    }
  };

  const handleDelete = async (c: Colaborador) => {
    if (!confirm(`Excluir colaborador "${c.nome}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await colaboradoresService.delete(c.id);
      void reload();
    } catch (err) {
      alert(apiErrorMessage(err));
    }
  };

  const handleSave = async () => {
    if (!form.nome.trim()) {
      setFormError('Informe o nome do colaborador.');
      return;
    }
    setFormError(null);
    const payload = {
      ...form,
      nome: form.nome.trim(),
      codigo: form.codigo.trim(),
      cargo: form.cargo.trim(),
      departamento: form.departamento.trim(),
    };
    try {
      if (editing) {
        const updated = await colaboradoresService.update(editing.id, payload);
        setEditing(updated);
      } else {
        const created = await colaboradoresService.create(payload);
        setEditing(created);
      }
      void reload();
    } catch (err) {
      setFormError(apiErrorMessage(err));
    }
  };

  const setFlag = (key: keyof ColaboradorForm, value: boolean) =>
    setForm((p) => ({ ...p, [key]: value }));

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
        <div className="flex flex-wrap gap-3">
          <select
            className="erp-select h-9 text-sm min-w-[10rem]"
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
            className="erp-select h-9 text-sm min-w-[8rem]"
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
          <DataTable>
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
                    <EmptyState message="Nenhum colaborador encontrado." actionLabel="Novo colaborador" onAction={openNew} />
                  </td>
                </tr>
              ) : (
                items.map((c) => {
                  const badges = badgesFuncoes(c);
                  const acessoBadge = badgeAcessoListagem(c);
                  const acessoVariant = badgeAcessoVariant(c);
                  return (
                    <tr key={c.id} className={!c.ativo ? 'opacity-60' : undefined}>
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
                          {c.pode_criar_usuario ? (
                            <button
                              type="button"
                              className="text-xs text-primary underline block"
                              onClick={() => setListModal({ type: 'criar', c })}
                            >
                              Criar usuário
                            </button>
                          ) : null}
                          {c.pode_definir_perfil ? (
                            <button
                              type="button"
                              className="text-xs text-amber-700 dark:text-amber-300 underline block"
                              onClick={() => setListModal({ type: 'perfil', c })}
                            >
                              Definir perfil
                            </button>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={c.ativo ? 'Ativo' : 'Inativo'} />
                      </td>
                      <td>
                        <div className="flex gap-1">
                          <button type="button" onClick={() => void openEdit(c)} className="erp-btn-ghost erp-btn-sm">
                            <Pencil className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(c)}
                            className="erp-btn-ghost erp-btn-sm text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
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

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar colaborador' : 'Novo colaborador'}
        size="lg"
      >
        {formError ? (
          <p className="mb-3 text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
            {formError}
          </p>
        ) : null}

        <div className="space-y-6">
          <section>
            <h3 className="text-sm font-semibold mb-3">Dados do colaborador</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label className="erp-label">Nome *</label>
                <input className="erp-input mt-1" value={form.nome} onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))} />
              </div>
              <div>
                <label className="erp-label">Código</label>
                <input className="erp-input mt-1" value={form.codigo} onChange={(e) => setForm((p) => ({ ...p, codigo: e.target.value }))} />
              </div>
              <div>
                <label className="erp-label flex items-center gap-2">
                  <input type="checkbox" checked={form.ativo} onChange={(e) => setFlag('ativo', e.target.checked)} />
                  Ativo
                </label>
              </div>
              <div>
                <label className="erp-label">E-mail</label>
                <input type="email" className="erp-input mt-1" value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
              </div>
              <div>
                <label className="erp-label">Telefone</label>
                <input className="erp-input mt-1" value={form.telefone} onChange={(e) => setForm((p) => ({ ...p, telefone: e.target.value }))} />
              </div>
              <div>
                <label className="erp-label">Cargo</label>
                <input className="erp-input mt-1" value={form.cargo} onChange={(e) => setForm((p) => ({ ...p, cargo: e.target.value }))} />
              </div>
              <div>
                <label className="erp-label">Departamento</label>
                <input className="erp-input mt-1" value={form.departamento} onChange={(e) => setForm((p) => ({ ...p, departamento: e.target.value }))} />
              </div>
              <div className="md:col-span-2">
                <label className="erp-label">Observações</label>
                <textarea className="erp-input mt-1 min-h-[3rem]" rows={2} value={form.observacoes} onChange={(e) => setForm((p) => ({ ...p, observacoes: e.target.value }))} />
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold">Funções internas</h3>
            <p className="text-[11px] text-muted-foreground mt-1 mb-2">
              Indicam como o colaborador participa da operação interna. Não substituem o perfil de acesso ao sistema.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {FUNCAO_CAMPOS.map((f) => (
                <label key={f.key} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={Boolean(form[f.key])} onChange={(e) => setFlag(f.key, e.target.checked)} />
                  {f.label}
                </label>
              ))}
            </div>
          </section>

          <section>
            <ColaboradorAcessoSection colaborador={editing} onRefresh={() => void refreshEditing()} />
          </section>
        </div>

        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" className="erp-btn-outline" onClick={() => setModalOpen(false)}>
            Fechar
          </button>
          <button type="button" className="erp-btn-primary" onClick={() => void handleSave()}>
            Salvar colaborador
          </button>
        </div>
      </Modal>

      {listModal?.type === 'criar' ? (
        <CriarUsuarioColaboradorModal
          colaborador={listModal.c}
          onClose={() => setListModal(null)}
          onSuccess={() => {
            clearAppContextoCache();
            void reload();
          }}
        />
      ) : null}
      {listModal?.type === 'perfil' ? (
        <DefinirPerfilAcessoModal
          colaborador={listModal.c}
          onClose={() => setListModal(null)}
          onSuccess={() => {
            clearAppContextoCache();
            void reload();
          }}
        />
      ) : null}
    </div>
  );
};

export default Colaboradores;
