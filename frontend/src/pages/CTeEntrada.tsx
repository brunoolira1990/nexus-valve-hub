import { useState, useEffect } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { cteEntradasService } from '@/services/api/fiscal';
import type { CTeEntrada } from '@/types';

const CTeEntrada = () => {
  const [items, setItems] = useState<CTeEntrada[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CTeEntrada | null>(null);
  const [form, setForm] = useState({ numero:'', transportadora_id:1, transportadora_nome:'Transportes Rápido Ltda', tomador_id:1, tomador_nome:'Nexus Válvulas Ltda', valor_frete:0, data:'', nfe_ids:[] as number[] });

  const load = async () => setItems(await cteEntradasService.getAll());
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({ numero:'',transportadora_id:1,transportadora_nome:'',tomador_id:1,tomador_nome:'',valor_frete:0,data:'',nfe_ids:[] }); setModalOpen(true); };
  const openEdit = (e: CTeEntrada) => { setEditing(e); setForm(e); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await cteEntradasService.delete(id); load(); } };
  const handleSave = async () => {
    if (editing) await cteEntradasService.update(editing.id, form);
    else await cteEntradasService.create(form as Omit<CTeEntrada, 'id'>);
    setModalOpen(false); load();
  };

  const filtered = items.filter(i => i.numero.includes(search));

  return (
    <div>
      <PageHeader title="CT-e Entrada" onAdd={openNew} addLabel="Novo CT-e" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Número</th><th>Transportadora</th><th>Tomador</th><th>Valor Frete</th><th>Data</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-medium">{e.numero}</td><td>{e.transportadora_nome}</td><td>{e.tomador_nome}</td>
                <td>R$ {e.valor_frete.toFixed(2)}</td><td>{e.data}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar CT-e' : 'Novo CT-e'} size="md">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div><label className="erp-label">Número</label><input className="erp-input mt-1" value={form.numero} onChange={e => setForm(p => ({...p,numero:e.target.value}))} /></div>
          <div><label className="erp-label">Transportadora</label><select className="erp-select mt-1" value={form.transportadora_id} onChange={e => setForm(p => ({...p,transportadora_id:+e.target.value}))}><option value={1}>Transportes Rápido Ltda</option></select></div>
          <div><label className="erp-label">Tomador</label><select className="erp-select mt-1" value={form.tomador_id} onChange={e => setForm(p => ({...p,tomador_id:+e.target.value}))}><option value={1}>Nexus Válvulas Ltda</option><option value={2}>Nexus Válvulas Filial SP</option></select></div>
          <div><label className="erp-label">Valor Frete</label><input type="number" step="0.01" className="erp-input mt-1" value={form.valor_frete} onChange={e => setForm(p => ({...p,valor_frete:+e.target.value}))} /></div>
          <div><label className="erp-label">Data</label><input type="date" className="erp-input mt-1" value={form.data} onChange={e => setForm(p => ({...p,data:e.target.value}))} /></div>
          <div><label className="erp-label">NF(s) vinculada(s)</label><input className="erp-input mt-1" placeholder="IDs separados por vírgula" /></div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default CTeEntrada;
