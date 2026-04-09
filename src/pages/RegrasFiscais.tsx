import { useState, useEffect } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { regrasFiscaisService } from '@/services/api/regras-fiscais';
import type { RegraFiscal } from '@/types';
import { UFS } from '@/types';

const empty: Omit<RegraFiscal, 'id'> = {
  ncm:'', uf_origem:'0', uf_destino:'SP', operacao:'Saída', cfop:'',
  cst_icms:'', aliquota_icms:0, cst_pis:'', aliquota_pis:0,
  cst_cofins:'', aliquota_cofins:0, cst_ipi:'', aliquota_ipi:0, base_calculo:'OPERACAO'
};

const RegrasFiscais = () => {
  const [items, setItems] = useState<RegraFiscal[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<RegraFiscal | null>(null);
  const [form, setForm] = useState(empty);

  const load = async () => setItems(await regrasFiscaisService.getAll());
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({...empty}); setModalOpen(true); };
  const openEdit = (e: RegraFiscal) => { setEditing(e); setForm(e); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await regrasFiscaisService.delete(id); load(); } };
  const handleSave = async () => {
    if (editing) await regrasFiscaisService.update(editing.id, form);
    else await regrasFiscaisService.create(form);
    setModalOpen(false); load();
  };
  const f = (k: keyof typeof form, v: string | number) => setForm(p => ({ ...p, [k]: v }));
  const filtered = items.filter(i => i.ncm.includes(search) || i.cfop.includes(search));

  return (
    <div>
      <PageHeader title="Regras Fiscais (NCM/UF)" onAdd={openNew} addLabel="Nova Regra" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>NCM</th><th>Origem</th><th>Destino</th><th>Operação</th><th>CFOP</th><th>CST ICMS</th><th>Alíq. ICMS</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-mono">{e.ncm}</td><td>{e.uf_origem}</td><td>{e.uf_destino}</td>
                <td><span className={e.operacao === 'Entrada' ? 'erp-badge-info' : 'erp-badge-success'}>{e.operacao}</span></td>
                <td>{e.cfop}</td><td>{e.cst_icms}</td><td>{e.aliquota_icms}%</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Regra Fiscal' : 'Nova Regra Fiscal'} size="lg">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div><label className="erp-label">NCM</label><input className="erp-input mt-1" value={form.ncm} onChange={e => f('ncm', e.target.value)} /></div>
          <div><label className="erp-label">UF Origem</label><select className="erp-select mt-1" value={form.uf_origem} onChange={e => f('uf_origem', e.target.value)}><option value="0">Geral (0)</option>{UFS.map(u => <option key={u}>{u}</option>)}</select></div>
          <div><label className="erp-label">UF Destino</label><select className="erp-select mt-1" value={form.uf_destino} onChange={e => f('uf_destino', e.target.value)}>{UFS.map(u => <option key={u}>{u}</option>)}</select></div>
          <div><label className="erp-label">Operação</label><select className="erp-select mt-1" value={form.operacao} onChange={e => f('operacao', e.target.value)}><option>Entrada</option><option>Saída</option></select></div>
          <div><label className="erp-label">CFOP</label><input className="erp-input mt-1" value={form.cfop} onChange={e => f('cfop', e.target.value)} /></div>
          <div><label className="erp-label">Base de Cálculo</label><select className="erp-select mt-1" value={form.base_calculo} onChange={e => f('base_calculo', e.target.value)}><option>OPERACAO</option><option>PRECO</option><option>PAUTA</option></select></div>
          <div><label className="erp-label">CST ICMS</label><input className="erp-input mt-1" value={form.cst_icms} onChange={e => f('cst_icms', e.target.value)} /></div>
          <div><label className="erp-label">Alíquota ICMS %</label><input type="number" step="0.01" className="erp-input mt-1" value={form.aliquota_icms} onChange={e => f('aliquota_icms', +e.target.value)} /></div>
          <div><label className="erp-label">CST PIS</label><input className="erp-input mt-1" value={form.cst_pis} onChange={e => f('cst_pis', e.target.value)} /></div>
          <div><label className="erp-label">Alíquota PIS %</label><input type="number" step="0.01" className="erp-input mt-1" value={form.aliquota_pis} onChange={e => f('aliquota_pis', +e.target.value)} /></div>
          <div><label className="erp-label">CST COFINS</label><input className="erp-input mt-1" value={form.cst_cofins} onChange={e => f('cst_cofins', e.target.value)} /></div>
          <div><label className="erp-label">Alíquota COFINS %</label><input type="number" step="0.01" className="erp-input mt-1" value={form.aliquota_cofins} onChange={e => f('aliquota_cofins', +e.target.value)} /></div>
          <div><label className="erp-label">CST IPI</label><input className="erp-input mt-1" value={form.cst_ipi} onChange={e => f('cst_ipi', e.target.value)} /></div>
          <div><label className="erp-label">Alíquota IPI %</label><input type="number" step="0.01" className="erp-input mt-1" value={form.aliquota_ipi} onChange={e => f('aliquota_ipi', +e.target.value)} /></div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default RegrasFiscais;
