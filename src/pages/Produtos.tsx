import { useState, useEffect } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { produtosService } from '@/services/api/produtos';
import type { Produto } from '@/types';
import { POLEGADAS, MATERIAIS } from '@/types';

const empty: Omit<Produto, 'id'> = {
  figura:'', sufixo:'', schedule:'', polegada_principal:'1/2"', polegada_secundaria:'',
  descricao:'', material:'Aço Carbono', tipo_peca:'', pressao_nominal:'', norma:'',
  conexao:'', ncm:'', preco_custo:0, preco_venda:0, estoque_minimo:0, codigo_completo:''
};

const Produtos = () => {
  const [items, setItems] = useState<Produto[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Produto | null>(null);
  const [form, setForm] = useState(empty);

  const load = async () => setItems(await produtosService.getAll());
  useEffect(() => { load(); }, []);

  const genCodigo = () => `${form.figura}.${form.sufixo}.${form.schedule}.${form.polegada_principal.replace('"','')}`;

  const openNew = () => { setEditing(null); setForm({...empty}); setModalOpen(true); };
  const openEdit = (e: Produto) => { setEditing(e); setForm(e); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await produtosService.delete(id); load(); } };
  const handleSave = async () => {
    const data = { ...form, codigo_completo: genCodigo() };
    if (editing) await produtosService.update(editing.id, data);
    else await produtosService.create(data);
    setModalOpen(false); load();
  };
  const f = (k: keyof typeof form, v: string | number) => setForm(p => ({ ...p, [k]: v }));
  const filtered = items.filter(i => i.descricao.toLowerCase().includes(search.toLowerCase()) || i.codigo_completo.includes(search));

  return (
    <div>
      <PageHeader title="Produtos" onAdd={openNew} addLabel="Novo Produto" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Código</th><th>Descrição</th><th>Material</th><th>NCM</th><th>Preço Venda</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-mono text-xs">{e.codigo_completo}</td>
                <td className="font-medium">{e.descricao}</td>
                <td>{e.material}</td><td>{e.ncm}</td>
                <td>R$ {e.preco_venda.toFixed(2)}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Produto' : 'Novo Produto'} size="lg">
        <div className="mb-3 p-3 bg-muted rounded-md">
          <span className="text-sm text-muted-foreground">Código gerado: </span>
          <span className="font-mono font-bold">{genCodigo()}</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div><label className="erp-label">Figura</label><input className="erp-input mt-1" value={form.figura} onChange={e => f('figura', e.target.value)} /></div>
          <div><label className="erp-label">Sufixo</label><input className="erp-input mt-1" value={form.sufixo} onChange={e => f('sufixo', e.target.value)} /></div>
          <div><label className="erp-label">Schedule</label><input className="erp-input mt-1" value={form.schedule} onChange={e => f('schedule', e.target.value)} /></div>
          <div><label className="erp-label">Polegada Principal</label><select className="erp-select mt-1" value={form.polegada_principal} onChange={e => f('polegada_principal', e.target.value)}>{POLEGADAS.map(p => <option key={p}>{p}</option>)}</select></div>
          <div><label className="erp-label">Polegada Secundária</label><select className="erp-select mt-1" value={form.polegada_secundaria} onChange={e => f('polegada_secundaria', e.target.value)}><option value="">-</option>{POLEGADAS.map(p => <option key={p}>{p}</option>)}</select></div>
          <div><label className="erp-label">Material</label><select className="erp-select mt-1" value={form.material} onChange={e => f('material', e.target.value)}>{MATERIAIS.map(m => <option key={m}>{m}</option>)}</select></div>
          <div className="md:col-span-3"><label className="erp-label">Descrição</label><input className="erp-input mt-1" value={form.descricao} onChange={e => f('descricao', e.target.value)} /></div>
          <div><label className="erp-label">Tipo de Peça</label><input className="erp-input mt-1" value={form.tipo_peca} onChange={e => f('tipo_peca', e.target.value)} /></div>
          <div><label className="erp-label">Pressão Nominal</label><input className="erp-input mt-1" value={form.pressao_nominal} onChange={e => f('pressao_nominal', e.target.value)} /></div>
          <div><label className="erp-label">Norma</label><input className="erp-input mt-1" value={form.norma} onChange={e => f('norma', e.target.value)} /></div>
          <div><label className="erp-label">Conexão</label><input className="erp-input mt-1" value={form.conexao} onChange={e => f('conexao', e.target.value)} /></div>
          <div><label className="erp-label">NCM</label><input className="erp-input mt-1" value={form.ncm} onChange={e => f('ncm', e.target.value)} /></div>
          <div><label className="erp-label">Preço Custo</label><input type="number" step="0.01" className="erp-input mt-1" value={form.preco_custo} onChange={e => f('preco_custo', +e.target.value)} /></div>
          <div><label className="erp-label">Preço Venda</label><input type="number" step="0.01" className="erp-input mt-1" value={form.preco_venda} onChange={e => f('preco_venda', +e.target.value)} /></div>
          <div><label className="erp-label">Estoque Mínimo</label><input type="number" className="erp-input mt-1" value={form.estoque_minimo} onChange={e => f('estoque_minimo', +e.target.value)} /></div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default Produtos;
