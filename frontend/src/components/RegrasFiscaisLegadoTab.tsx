import { useState } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { regrasFiscaisService } from '@/services/api/regras-fiscais';
import type { RegraFiscal } from '@/types';
import { UFS } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';

const empty: Omit<RegraFiscal, 'id'> = {
  ncm: '',
  uf_origem: '0',
  uf_destino: 'SP',
  operacao: 'Saída',
  cfop: '',
  cst_icms: '',
  aliquota_icms: 0,
  cst_pis: '',
  aliquota_pis: 0,
  cst_cofins: '',
  aliquota_cofins: 0,
  cst_ipi: '',
  aliquota_ipi: 0,
  base_calculo: 'OPERACAO',
};

/** Tabela legada usada por propostas/pricing (`RegraFiscal` + `find_regra_fiscal`). */
export const RegrasFiscaisLegadoTab = () => {
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
  } = usePaginatedList<RegraFiscal>({ fetchPage: regrasFiscaisService.listPaginated });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<RegraFiscal | null>(null);
  const [form, setForm] = useState(empty);
  const [formError, setFormError] = useState<string | null>(null);

  const validarForm = () => {
    if (!form.ncm.trim()) return 'Informe o NCM.';
    if (!form.cfop.trim()) return 'Informe o CFOP.';
    if (!form.operacao.trim()) return 'Informe o tipo de operação.';
    if (!form.cst_icms.trim()) return 'Informe o CST/CSOSN de ICMS.';
    return null;
  };

  const openNew = () => {
    setEditing(null);
    setForm({ ...empty });
    setModalOpen(true);
  };
  const openEdit = (e: RegraFiscal) => {
    setEditing(e);
    setForm(e);
    setModalOpen(true);
  };
  const handleDelete = async (id: number) => {
    if (confirm('Excluir regra fiscal legada?')) {
      await regrasFiscaisService.delete(id);
      void reload();
    }
  };
  const handleSave = async () => {
    const erro = validarForm();
    if (erro) {
      setFormError(erro);
      return;
    }
    setFormError(null);
    if (editing) await regrasFiscaisService.update(editing.id, form);
    else await regrasFiscaisService.create(form);
    setModalOpen(false);
    void reload();
  };
  const f = (k: keyof typeof form, v: string | number) => setForm((p) => ({ ...p, [k]: v }));

  return (
    <section className="mt-8 pt-6 border-t border-border">
      <h2 className="text-lg font-semibold mb-1">Regras antigas de proposta / pricing</h2>
      <p className="text-xs text-muted-foreground mb-3 max-w-3xl">
        Estas regras alimentam <strong>propostas</strong> hoje (busca por NCM + UF + operação Saída). Mantenha-as até a
        migração para o cenário fiscal de saída.
      </p>
      <PageHeader title="" onAdd={openNew} addLabel="Nova regra legada" searchValue={search} onSearch={setSearch} />
      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={5} cols={8} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable>
            <thead>
              <tr>
                <th>NCM</th>
                <th>Origem</th>
                <th>Destino</th>
                <th>Operação</th>
                <th>CFOP</th>
                <th>CST ICMS</th>
                <th>Alíq. ICMS</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <EmptyState
                      message="Nenhuma regra fiscal cadastrada. Cadastre a regra mínima de venda com CFOP, natureza e CST/CSOSN."
                      actionLabel="Nova regra fiscal"
                      onAction={openNew}
                    />
                  </td>
                </tr>
              ) : (
            items.map((e) => (
              <tr key={e.id}>
                <td className="font-mono">{e.ncm}</td>
                <td>{e.uf_origem}</td>
                <td>{e.uf_destino}</td>
                <td>
                  <StatusBadge status={e.operacao === 'Entrada' ? 'entrada' : 'saida'} />
                </td>
                <td>{e.cfop}</td>
                <td>{e.cst_icms}</td>
                <td>{e.aliquota_icms}%</td>
                <td>
                  <div className="flex gap-1">
                    <button type="button" onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm" title="Editar">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDelete(e.id)}
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
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar regra fiscal (legado)' : 'Nova regra fiscal (legado)'}
        size="lg"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="erp-label">NCM</label>
            <input className="erp-input mt-1" value={form.ncm} onChange={(e) => f('ncm', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">UF Origem</label>
            <select className="erp-select mt-1" value={form.uf_origem} onChange={(e) => f('uf_origem', e.target.value)}>
              <option value="0">Geral (0)</option>
              {UFS.map((u) => (
                <option key={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">UF Destino</label>
            <select className="erp-select mt-1" value={form.uf_destino} onChange={(e) => f('uf_destino', e.target.value)}>
              {UFS.map((u) => (
                <option key={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Operação</label>
            <select className="erp-select mt-1" value={form.operacao} onChange={(e) => f('operacao', e.target.value)}>
              <option>Entrada</option>
              <option>Saída</option>
            </select>
          </div>
          <div>
            <label className="erp-label">CFOP</label>
            <input className="erp-input mt-1" value={form.cfop} onChange={(e) => f('cfop', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Base de Cálculo</label>
            <select className="erp-select mt-1" value={form.base_calculo} onChange={(e) => f('base_calculo', e.target.value)}>
              <option>OPERACAO</option>
              <option>PRECO</option>
              <option>PAUTA</option>
            </select>
          </div>
          <div>
            <label className="erp-label">CST ICMS</label>
            <input className="erp-input mt-1" value={form.cst_icms} onChange={(e) => f('cst_icms', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Alíquota ICMS %</label>
            <input
              type="number"
              step="0.01"
              className="erp-input mt-1"
              value={form.aliquota_icms}
              onChange={(e) => f('aliquota_icms', +e.target.value)}
            />
          </div>
          <div>
            <label className="erp-label">CST PIS</label>
            <input className="erp-input mt-1" value={form.cst_pis} onChange={(e) => f('cst_pis', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Alíquota PIS %</label>
            <input
              type="number"
              step="0.01"
              className="erp-input mt-1"
              value={form.aliquota_pis}
              onChange={(e) => f('aliquota_pis', +e.target.value)}
            />
          </div>
          <div>
            <label className="erp-label">CST COFINS</label>
            <input className="erp-input mt-1" value={form.cst_cofins} onChange={(e) => f('cst_cofins', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Alíquota COFINS %</label>
            <input
              type="number"
              step="0.01"
              className="erp-input mt-1"
              value={form.aliquota_cofins}
              onChange={(e) => f('aliquota_cofins', +e.target.value)}
            />
          </div>
          <div>
            <label className="erp-label">CST IPI</label>
            <input className="erp-input mt-1" value={form.cst_ipi} onChange={(e) => f('cst_ipi', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Alíquota IPI %</label>
            <input
              type="number"
              step="0.01"
              className="erp-input mt-1"
              value={form.aliquota_ipi}
              onChange={(e) => f('aliquota_ipi', +e.target.value)}
            />
          </div>
        </div>
        {formError ? <p className="text-sm text-destructive mt-4">{formError}</p> : null}
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" onClick={() => setModalOpen(false)} className="erp-btn-outline">
            Cancelar
          </button>
          <button type="button" onClick={() => void handleSave()} className="erp-btn-primary">
            Salvar
          </button>
        </div>
      </Modal>
    </section>
  );
};
