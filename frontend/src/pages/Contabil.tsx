import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, ChevronRight } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { contabilService } from '@/services/api/outros';
import type { ContaContabil, Balancete } from '@/types';

const Contabil = () => {
  const [tab, setTab] = useState<'plano'|'balancete'>('plano');
  const [contas, setContas] = useState<ContaContabil[]>([]);
  const [balancete, setBalancete] = useState<Balancete[]>([]);
  const [mes, setMes] = useState(3);
  const [ano, setAno] = useState(2024);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ContaContabil | null>(null);
  const [form, setForm] = useState({ codigo:'', nome:'', tipo:'Analítica', pai_id: null as number|null });

  const loadContas = async () => setContas(await contabilService.getContas());
  useEffect(() => { loadContas(); }, []);

  const loadBalancete = async () => setBalancete(await contabilService.getBalancete(mes, ano));

  const openNew = () => { setEditing(null); setForm({ codigo:'',nome:'',tipo:'Analítica',pai_id:null }); setModalOpen(true); };
  const openEdit = (c: ContaContabil) => { setEditing(c); setForm(c); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await contabilService.deleteConta(id); loadContas(); } };
  const handleSave = async () => {
    if (editing) await contabilService.updateConta(editing.id, form);
    else await contabilService.createConta(form as Omit<ContaContabil, 'id'>);
    setModalOpen(false); loadContas();
  };

  const roots = contas.filter(c => !c.pai_id);
  const getChildren = (id: number) => contas.filter(c => c.pai_id === id);

  const renderConta = (c: ContaContabil, level: number) => (
    <div key={c.id}>
      <div className={`flex items-center gap-2 py-1.5 px-3 hover:bg-muted/50 rounded`} style={{ paddingLeft: `${level * 20 + 12}px` }}>
        {getChildren(c.id).length > 0 && <ChevronRight className="h-3 w-3 text-muted-foreground" />}
        <span className="font-mono text-sm text-muted-foreground w-16">{c.codigo}</span>
        <span className="flex-1 text-sm font-medium">{c.nome}</span>
        <span className="text-xs text-muted-foreground">{c.tipo}</span>
        <button onClick={() => openEdit(c)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-3 w-3" /></button>
        <button onClick={() => handleDelete(c.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-3 w-3" /></button>
      </div>
      {getChildren(c.id).map(ch => renderConta(ch, level + 1))}
    </div>
  );

  return (
    <div>
      <h1 className="text-2xl font-bold text-foreground mb-6">Contábil</h1>
      <div className="flex gap-2 mb-4">
        <button onClick={() => setTab('plano')} className={`erp-btn-sm ${tab === 'plano' ? 'erp-btn-primary' : 'erp-btn-outline'}`}>Plano de Contas</button>
        <button onClick={() => setTab('balancete')} className={`erp-btn-sm ${tab === 'balancete' ? 'erp-btn-primary' : 'erp-btn-outline'}`}>Balancete</button>
      </div>

      {tab === 'plano' && (
        <div className="erp-card">
          <div className="flex justify-between items-center p-4 border-b border-border">
            <h3 className="font-semibold">Plano de Contas</h3>
            <button onClick={openNew} className="erp-btn-primary erp-btn-sm"><Plus className="h-3 w-3" /> Nova Conta</button>
          </div>
          <div className="p-2">
            {roots.map(c => renderConta(c, 0))}
          </div>
        </div>
      )}

      {tab === 'balancete' && (
        <>
          <div className="erp-card p-4 mb-4">
            <div className="flex items-end gap-4">
              <div><label className="erp-label">Mês</label><select className="erp-select mt-1" value={mes} onChange={e => setMes(+e.target.value)}>{Array.from({length:12},(_,i) => <option key={i+1} value={i+1}>{i+1}</option>)}</select></div>
              <div><label className="erp-label">Ano</label><select className="erp-select mt-1" value={ano} onChange={e => setAno(+e.target.value)}><option>2024</option><option>2023</option></select></div>
              <button onClick={loadBalancete} className="erp-btn-primary">Consultar</button>
            </div>
          </div>
          {balancete.length > 0 && (
            <div className="erp-card overflow-x-auto">
              <table className="erp-table">
                <thead><tr><th>Código</th><th>Conta</th><th>Débito</th><th>Crédito</th><th>Saldo</th></tr></thead>
                <tbody>
                  {balancete.map(b => (
                    <tr key={b.conta_id}>
                      <td className="font-mono">{b.conta_codigo}</td>
                      <td className="font-medium">{b.conta_nome}</td>
                      <td>R$ {b.debito.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                      <td>R$ {b.credito.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                      <td className={b.saldo < 0 ? 'text-destructive font-bold' : 'font-bold'}>R$ {b.saldo.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Conta' : 'Nova Conta'} size="sm">
        <div className="space-y-4">
          <div><label className="erp-label">Código</label><input className="erp-input mt-1" value={form.codigo} onChange={e => setForm(p => ({...p,codigo:e.target.value}))} /></div>
          <div><label className="erp-label">Nome</label><input className="erp-input mt-1" value={form.nome} onChange={e => setForm(p => ({...p,nome:e.target.value}))} /></div>
          <div><label className="erp-label">Tipo</label><select className="erp-select mt-1" value={form.tipo} onChange={e => setForm(p => ({...p,tipo:e.target.value}))}><option>Sintética</option><option>Analítica</option></select></div>
          <div><label className="erp-label">Conta Pai</label><select className="erp-select mt-1" value={form.pai_id ?? ''} onChange={e => setForm(p => ({...p,pai_id:e.target.value?+e.target.value:null}))}><option value="">Nenhuma (raiz)</option>{contas.map(c => <option key={c.id} value={c.id}>{c.codigo} - {c.nome}</option>)}</select></div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default Contabil;
