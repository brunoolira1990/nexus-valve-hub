import { useState, useEffect } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { clientesService } from '@/services/api/clientes';
import type { Cliente } from '@/types';
import { UFS } from '@/types';

const empty: Omit<Cliente, 'id'> = {
  razao_social:'', nome_fantasia:'', cnpj:'', ie:'',
  logradouro:'', numero:'', complemento:'', bairro:'', cidade:'', uf:'SP', cep:'',
  telefone:'', email:'', contato_responsavel:'', observacoes:''
};

const Clientes = () => {
  const [items, setItems] = useState<Cliente[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Cliente | null>(null);
  const [form, setForm] = useState(empty);

  const load = async () => setItems(await clientesService.getAll());
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({...empty}); setModalOpen(true); };
  const openEdit = (e: Cliente) => { setEditing(e); setForm(e); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await clientesService.delete(id); load(); } };
  const handleSave = async () => {
    if (editing) await clientesService.update(editing.id, form);
    else await clientesService.create(form);
    setModalOpen(false); load();
  };
  const f = (k: keyof typeof form, v: string) => setForm(p => ({ ...p, [k]: v }));
  const filtered = items.filter(i => i.razao_social.toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <PageHeader title="Clientes" onAdd={openNew} addLabel="Novo Cliente" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Razão Social</th><th>CNPJ</th><th>Telefone</th><th>Contato</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-medium">{e.razao_social}</td><td>{e.cnpj}</td><td>{e.telefone}</td><td>{e.contato_responsavel}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Cliente' : 'Novo Cliente'} size="lg">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div><label className="erp-label">Razão Social</label><input className="erp-input mt-1" value={form.razao_social} onChange={e => f('razao_social', e.target.value)} /></div>
          <div><label className="erp-label">Nome Fantasia</label><input className="erp-input mt-1" value={form.nome_fantasia} onChange={e => f('nome_fantasia', e.target.value)} /></div>
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
          <div><label className="erp-label">Contato Responsável</label><input className="erp-input mt-1" value={form.contato_responsavel} onChange={e => f('contato_responsavel', e.target.value)} /></div>
          <div className="md:col-span-2"><label className="erp-label">Observações</label><textarea className="erp-input mt-1 h-20" value={form.observacoes} onChange={e => f('observacoes', e.target.value)} /></div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default Clientes;
