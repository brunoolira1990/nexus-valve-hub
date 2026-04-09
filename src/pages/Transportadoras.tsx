import { useState, useEffect } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { transportadorasService } from '@/services/api/transportadoras';
import type { Transportadora } from '@/types';
import { UFS } from '@/types';

const empty: Omit<Transportadora, 'id'> = {
  razao_social:'', cnpj:'', ie:'',
  logradouro:'', numero:'', complemento:'', bairro:'', cidade:'', uf:'SP', cep:'',
  telefone:'', email:'', placa_padrao:'', uf_placa:'SP'
};

const Transportadoras = () => {
  const [items, setItems] = useState<Transportadora[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Transportadora | null>(null);
  const [form, setForm] = useState(empty);

  const load = async () => setItems(await transportadorasService.getAll());
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({...empty}); setModalOpen(true); };
  const openEdit = (e: Transportadora) => { setEditing(e); setForm(e); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await transportadorasService.delete(id); load(); } };
  const handleSave = async () => {
    if (editing) await transportadorasService.update(editing.id, form);
    else await transportadorasService.create(form);
    setModalOpen(false); load();
  };
  const f = (k: keyof typeof form, v: string) => setForm(p => ({ ...p, [k]: v }));
  const filtered = items.filter(i => i.razao_social.toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <PageHeader title="Transportadoras" onAdd={openNew} addLabel="Nova Transportadora" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Razão Social</th><th>CNPJ</th><th>Telefone</th><th>Placa</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-medium">{e.razao_social}</td><td>{e.cnpj}</td><td>{e.telefone}</td><td>{e.placa_padrao}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Transportadora' : 'Nova Transportadora'} size="lg">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div><label className="erp-label">Razão Social</label><input className="erp-input mt-1" value={form.razao_social} onChange={e => f('razao_social', e.target.value)} /></div>
          <div><label className="erp-label">CNPJ</label><input className="erp-input mt-1" value={form.cnpj} onChange={e => f('cnpj', e.target.value)} /></div>
          <div><label className="erp-label">IE</label><input className="erp-input mt-1" value={form.ie} onChange={e => f('ie', e.target.value)} /></div>
          <div className="md:col-span-2"><label className="erp-label">Logradouro</label><input className="erp-input mt-1" value={form.logradouro} onChange={e => f('logradouro', e.target.value)} /></div>
          <div><label className="erp-label">Número</label><input className="erp-input mt-1" value={form.numero} onChange={e => f('numero', e.target.value)} /></div>
          <div><label className="erp-label">Complemento</label><input className="erp-input mt-1" value={form.complemento} onChange={e => f('complemento', e.target.value)} /></div>
          <div><label className="erp-label">Bairro</label><input className="erp-input mt-1" value={form.bairro} onChange={e => f('bairro', e.target.value)} /></div>
          <div><label className="erp-label">Cidade</label><input className="erp-input mt-1" value={form.cidade} onChange={e => f('cidade', e.target.value)} /></div>
          <div><label className="erp-label">UF</label><select className="erp-select mt-1" value={form.uf} onChange={e => f('uf', e.target.value)}>{UFS.map(u => <option key={u}>{u}</option>)}</select></div>
          <div><label className="erp-label">CEP</label><input className="erp-input mt-1" value={form.cep} onChange={e => f('cep', e.target.value)} /></div>
          <div><label className="erp-label">Telefone</label><input className="erp-input mt-1" value={form.telefone} onChange={e => f('telefone', e.target.value)} /></div>
          <div><label className="erp-label">E-mail</label><input className="erp-input mt-1" value={form.email} onChange={e => f('email', e.target.value)} /></div>
          <div><label className="erp-label">Placa Padrão</label><input className="erp-input mt-1" value={form.placa_padrao} onChange={e => f('placa_padrao', e.target.value)} /></div>
          <div><label className="erp-label">UF Placa</label><select className="erp-select mt-1" value={form.uf_placa} onChange={e => f('uf_placa', e.target.value)}>{UFS.map(u => <option key={u}>{u}</option>)}</select></div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default Transportadoras;
