import { useState, useEffect } from 'react';
import { Pencil, Trash2, Plus, X } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { nfeEntradasService } from '@/services/api/fiscal';
import type { NFeEntrada, ItemNFe } from '@/types';

const NFeEntrada = () => {
  const [items, setItems] = useState<NFeEntrada[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<NFeEntrada | null>(null);
  const [form, setForm] = useState({ numero:'', fornecedor_id:1, fornecedor_nome:'Tupy S.A.', data:'', pedido_compra_id:undefined as number|undefined, cte_id:undefined as number|undefined });
  const [itens, setItens] = useState<ItemNFe[]>([]);

  const load = async () => setItems(await nfeEntradasService.getAll());
  useEffect(() => { load(); }, []);

  const addItem = () => setItens(p => [...p, { id:Date.now(), produto_id:1, produto_nome:'', quantidade:1, valor:0, corrida_id:undefined }]);
  const removeItem = (id: number) => setItens(p => p.filter(i => i.id !== id));
  const total = itens.reduce((s, i) => s + i.quantidade * i.valor, 0);

  const openNew = () => { setEditing(null); setForm({ numero:'',fornecedor_id:1,fornecedor_nome:'',data:'',pedido_compra_id:undefined,cte_id:undefined }); setItens([]); setModalOpen(true); };
  const openEdit = (e: NFeEntrada) => { setEditing(e); setForm({...e, pedido_compra_id: e.pedido_compra_id, cte_id: e.cte_id}); setItens(e.itens); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await nfeEntradasService.delete(id); load(); } };
  const handleSave = async () => {
    const data = { ...form, itens, valor_total: total };
    if (editing) await nfeEntradasService.update(editing.id, data);
    else await nfeEntradasService.create(data as Omit<NFeEntrada, 'id'>);
    setModalOpen(false); load();
  };

  const filtered = items.filter(i => i.numero.includes(search));

  return (
    <div>
      <PageHeader title="NF-e Entrada" onAdd={openNew} addLabel="Nova NF-e" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Número</th><th>Fornecedor</th><th>Data</th><th>Valor Total</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-medium">{e.numero}</td><td>{e.fornecedor_nome}</td><td>{e.data}</td><td>R$ {e.valor_total.toFixed(2)}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar NF-e Entrada' : 'Nova NF-e Entrada'} size="xl">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div><label className="erp-label">Número</label><input className="erp-input mt-1" value={form.numero} onChange={e => setForm(p => ({...p,numero:e.target.value}))} /></div>
          <div><label className="erp-label">Fornecedor</label><select className="erp-select mt-1" value={form.fornecedor_id} onChange={e => setForm(p => ({...p,fornecedor_id:+e.target.value}))}><option value={1}>Tupy S.A.</option><option value={2}>Vallourec</option></select></div>
          <div><label className="erp-label">Data</label><input type="date" className="erp-input mt-1" value={form.data} onChange={e => setForm(p => ({...p,data:e.target.value}))} /></div>
          <div><label className="erp-label">Pedido Compra (opcional)</label><input className="erp-input mt-1" placeholder="PC-001" value={form.pedido_compra_id ?? ''} onChange={e => setForm(p => ({...p,pedido_compra_id:e.target.value?+e.target.value:undefined}))} /></div>
          <div><label className="erp-label">CT-e vinculado (opcional)</label><input className="erp-input mt-1" placeholder="CTE-001" value={form.cte_id ?? ''} onChange={e => setForm(p => ({...p,cte_id:e.target.value?+e.target.value:undefined}))} /></div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="flex justify-between items-center mb-3"><h3 className="font-medium text-sm">Itens</h3><button onClick={addItem} className="erp-btn-outline erp-btn-sm"><Plus className="h-3 w-3" /> Item</button></div>
          {itens.map((item, idx) => (
            <div key={item.id} className="grid grid-cols-5 gap-2 mb-2 items-end">
              <div><label className="text-xs text-muted-foreground">Produto</label><select className="erp-input h-8 text-sm" value={item.produto_id} onChange={e => { const n=[...itens]; n[idx]={...n[idx],produto_id:+e.target.value}; setItens(n); }}><option value={1}>Válvula Gaveta 2"</option><option value={2}>Válvula Esfera 4"</option></select></div>
              <div><label className="text-xs text-muted-foreground">Qtd</label><input type="number" className="erp-input h-8 text-sm" value={item.quantidade} onChange={e => { const n=[...itens]; n[idx]={...n[idx],quantidade:+e.target.value}; setItens(n); }} /></div>
              <div><label className="text-xs text-muted-foreground">Valor</label><input type="number" step="0.01" className="erp-input h-8 text-sm" value={item.valor} onChange={e => { const n=[...itens]; n[idx]={...n[idx],valor:+e.target.value}; setItens(n); }} /></div>
              <div><label className="text-xs text-muted-foreground">Corrida</label><select className="erp-input h-8 text-sm" value={item.corrida_id ?? ''} onChange={e => { const n=[...itens]; n[idx]={...n[idx],corrida_id:+e.target.value||undefined}; setItens(n); }}><option value="">Nova corrida</option><option value={1}>C-2024-001</option><option value={2}>C-2024-002</option></select></div>
              <button onClick={() => removeItem(item.id)} className="erp-btn-ghost erp-btn-sm text-destructive h-8"><X className="h-4 w-4" /></button>
            </div>
          ))}
          <div className="text-right mt-3 pt-3 border-t border-border font-bold">Total: R$ {total.toFixed(2)}</div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default NFeEntrada;
