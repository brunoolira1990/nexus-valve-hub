import { useState, useEffect } from 'react';
import { Pencil, Trash2, Plus, X } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { pedidosCompraService } from '@/services/api/comercial';
import type { PedidoCompra, ItemPedido } from '@/types';

const PedidosCompra = () => {
  const [items, setItems] = useState<PedidoCompra[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<PedidoCompra | null>(null);
  const [form, setForm] = useState({ numero:'', fornecedor_id:1, fornecedor_nome:'Tupy S.A.', data:'', status:'Pendente' });
  const [itens, setItens] = useState<ItemPedido[]>([]);

  const load = async () => setItems(await pedidosCompraService.getAll());
  useEffect(() => { load(); }, []);

  const addItem = () => setItens(p => [...p, { id: Date.now(), produto_id:1, produto_nome:'', quantidade:1, valor_unitario:0 }]);
  const removeItem = (id: number) => setItens(p => p.filter(i => i.id !== id));
  const total = itens.reduce((s, i) => s + i.quantidade * i.valor_unitario, 0);

  const openNew = () => { setEditing(null); setForm({ numero:'',fornecedor_id:1,fornecedor_nome:'',data:'',status:'Pendente' }); setItens([]); setModalOpen(true); };
  const openEdit = (e: PedidoCompra) => { setEditing(e); setForm(e); setItens(e.itens); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await pedidosCompraService.delete(id); load(); } };
  const handleSave = async () => {
    const data = { ...form, itens, valor_total: total };
    if (editing) await pedidosCompraService.update(editing.id, data);
    else await pedidosCompraService.create(data as Omit<PedidoCompra, 'id'>);
    setModalOpen(false); load();
  };

  const filtered = items.filter(i => i.numero.includes(search));

  return (
    <div>
      <PageHeader title="Pedidos de Compra" onAdd={openNew} addLabel="Novo Pedido" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Número</th><th>Fornecedor</th><th>Data</th><th>Status</th><th>Valor Total</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-medium">{e.numero}</td><td>{e.fornecedor_nome}</td><td>{e.data}</td>
                <td><span className={e.status === 'Recebido' ? 'erp-badge-success' : 'erp-badge-warning'}>{e.status}</span></td>
                <td>R$ {e.valor_total.toFixed(2)}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Pedido de Compra' : 'Novo Pedido de Compra'} size="lg">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div><label className="erp-label">Número</label><input className="erp-input mt-1" value={form.numero} onChange={e => setForm(p => ({...p,numero:e.target.value}))} /></div>
          <div><label className="erp-label">Fornecedor</label><select className="erp-select mt-1" value={form.fornecedor_id} onChange={e => setForm(p => ({...p,fornecedor_id:+e.target.value}))}><option value={1}>Tupy S.A.</option><option value={2}>Vallourec</option></select></div>
          <div><label className="erp-label">Data</label><input type="date" className="erp-input mt-1" value={form.data} onChange={e => setForm(p => ({...p,data:e.target.value}))} /></div>
          <div><label className="erp-label">Status</label><select className="erp-select mt-1" value={form.status} onChange={e => setForm(p => ({...p,status:e.target.value}))}><option>Pendente</option><option>Aprovado</option><option>Recebido</option></select></div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-sm">Itens</h3>
            <button onClick={addItem} className="erp-btn-outline erp-btn-sm"><Plus className="h-3 w-3" /> Item</button>
          </div>
          {itens.map((item, idx) => (
            <div key={item.id} className="grid grid-cols-4 gap-2 mb-2 items-end">
              <div><label className="text-xs text-muted-foreground">Produto</label><select className="erp-input h-8 text-sm" value={item.produto_id} onChange={e => { const n=[...itens]; n[idx]={...n[idx],produto_id:+e.target.value}; setItens(n); }}><option value={1}>Válvula Gaveta 2"</option><option value={2}>Válvula Esfera 4"</option></select></div>
              <div><label className="text-xs text-muted-foreground">Qtd</label><input type="number" className="erp-input h-8 text-sm" value={item.quantidade} onChange={e => { const n=[...itens]; n[idx]={...n[idx],quantidade:+e.target.value}; setItens(n); }} /></div>
              <div><label className="text-xs text-muted-foreground">Valor Unit.</label><input type="number" step="0.01" className="erp-input h-8 text-sm" value={item.valor_unitario} onChange={e => { const n=[...itens]; n[idx]={...n[idx],valor_unitario:+e.target.value}; setItens(n); }} /></div>
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

export default PedidosCompra;
