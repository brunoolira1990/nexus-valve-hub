import { useState, useEffect } from 'react';
import { Pencil, Trash2, ChevronDown, ChevronRight } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { corridasService } from '@/services/api/corridas';
import type { Corrida, ComposicaoQuimica, Tracao, Impacto } from '@/types';

const chemKeys: (keyof ComposicaoQuimica)[] = ['C','Mn','P','S','Si','Ni','Cr','Mo','Cu','V','Nb','Al','Ti','N','Zn','Fe','Sn','Pb','Ca','Ta','W','Li','CO'];

const emptyComp: ComposicaoQuimica = Object.fromEntries(chemKeys.map(k => [k, 0])) as ComposicaoQuimica;
const emptyTrac: Tracao = { norma:'',corpo_prova:'',direcao:'',posicao:'',temperatura:0,limite_escoamento:0,limite_resistencia:0,alongamento:0,estriccao:0,dureza:'',tratamento_termico:'' };
const emptyImp: Impacto = { norma:'',corpo_prova:'',direcao:'',posicao:'',temperatura:0,valor_a:0,valor_b:0,valor_c:0,media:0 };

const Corridas = () => {
  const [items, setItems] = useState<Corrida[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Corrida | null>(null);
  const [form, setForm] = useState({ numero:'', produto_id:1, produto_nome:'', fornecedor_id:1, fornecedor_nome:'', data_recebimento:'', nf_entrada:'' });
  const [comp, setComp] = useState(emptyComp);
  const [trac, setTrac] = useState(emptyTrac);
  const [imp, setImp] = useState(emptyImp);
  const [sections, setSections] = useState({ quimica: false, tracao: false, impacto: false });

  const load = async () => setItems(await corridasService.getAll());
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({ numero:'',produto_id:1,produto_nome:'',fornecedor_id:1,fornecedor_nome:'',data_recebimento:'',nf_entrada:'' }); setComp({...emptyComp}); setTrac({...emptyTrac}); setImp({...emptyImp}); setModalOpen(true); };
  const openEdit = (e: Corrida) => { setEditing(e); setForm(e); setComp(e.composicao_quimica); setTrac(e.tracao); setImp(e.impacto); setModalOpen(true); };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await corridasService.delete(id); load(); } };
  const handleSave = async () => {
    const data = { ...form, composicao_quimica: comp, tracao: trac, impacto: imp };
    if (editing) await corridasService.update(editing.id, data);
    else await corridasService.create(data as Omit<Corrida, 'id'>);
    setModalOpen(false); load();
  };

  const toggle = (s: keyof typeof sections) => setSections(p => ({ ...p, [s]: !p[s] }));
  const filtered = items.filter(i => i.numero.toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <PageHeader title="Corridas (Lotes)" onAdd={openNew} addLabel="Nova Corrida" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Número</th><th>Produto</th><th>Fornecedor</th><th>Data Receb.</th><th>NF</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-mono font-medium">{e.numero}</td><td>{e.produto_nome}</td><td>{e.fornecedor_nome}</td>
                <td>{e.data_recebimento}</td><td>{e.nf_entrada}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Corrida' : 'Nova Corrida'} size="xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div><label className="erp-label">Número da Corrida</label><input className="erp-input mt-1" value={form.numero} onChange={e => setForm(p => ({...p, numero:e.target.value}))} /></div>
          <div><label className="erp-label">Produto</label><select className="erp-select mt-1" value={form.produto_id} onChange={e => setForm(p => ({...p, produto_id:+e.target.value}))}><option value={1}>Válvula Gaveta 2"</option><option value={2}>Válvula Esfera 4"</option><option value={3}>Conexão WeldoFit 3"x2"</option></select></div>
          <div><label className="erp-label">Fornecedor</label><select className="erp-select mt-1" value={form.fornecedor_id} onChange={e => setForm(p => ({...p, fornecedor_id:+e.target.value}))}><option value={1}>Tupy S.A.</option><option value={2}>Vallourec</option></select></div>
          <div><label className="erp-label">Data Recebimento</label><input type="date" className="erp-input mt-1" value={form.data_recebimento} onChange={e => setForm(p => ({...p, data_recebimento:e.target.value}))} /></div>
          <div><label className="erp-label">NF Entrada</label><input className="erp-input mt-1" value={form.nf_entrada} onChange={e => setForm(p => ({...p, nf_entrada:e.target.value}))} /></div>
        </div>

        {/* Composição Química */}
        <button onClick={() => toggle('quimica')} className="flex items-center gap-2 w-full py-2 px-3 bg-muted rounded-md mb-2 font-medium text-sm">
          {sections.quimica ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />} Composição Química
        </button>
        {sections.quimica && (
          <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2 mb-4 p-3 border border-border rounded-md">
            {chemKeys.map(k => (
              <div key={k}><label className="text-xs text-muted-foreground">{k}</label><input type="number" step="0.001" className="erp-input mt-0.5 text-xs h-8" value={comp[k]} onChange={e => setComp(p => ({...p,[k]:+e.target.value}))} /></div>
            ))}
          </div>
        )}

        {/* Tração */}
        <button onClick={() => toggle('tracao')} className="flex items-center gap-2 w-full py-2 px-3 bg-muted rounded-md mb-2 font-medium text-sm">
          {sections.tracao ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />} Tração
        </button>
        {sections.tracao && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 p-3 border border-border rounded-md">
            <div><label className="erp-label text-xs">Norma</label><input className="erp-input mt-1 h-8 text-sm" value={trac.norma} onChange={e => setTrac(p => ({...p,norma:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Corpo Prova</label><input className="erp-input mt-1 h-8 text-sm" value={trac.corpo_prova} onChange={e => setTrac(p => ({...p,corpo_prova:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Direção</label><input className="erp-input mt-1 h-8 text-sm" value={trac.direcao} onChange={e => setTrac(p => ({...p,direcao:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Posição</label><input className="erp-input mt-1 h-8 text-sm" value={trac.posicao} onChange={e => setTrac(p => ({...p,posicao:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Temperatura</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={trac.temperatura} onChange={e => setTrac(p => ({...p,temperatura:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Lim. Escoamento (MPa)</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={trac.limite_escoamento} onChange={e => setTrac(p => ({...p,limite_escoamento:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Lim. Resistência (MPa)</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={trac.limite_resistencia} onChange={e => setTrac(p => ({...p,limite_resistencia:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Alongamento %</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={trac.alongamento} onChange={e => setTrac(p => ({...p,alongamento:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Estricção %</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={trac.estriccao} onChange={e => setTrac(p => ({...p,estriccao:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Dureza</label><input className="erp-input mt-1 h-8 text-sm" value={trac.dureza} onChange={e => setTrac(p => ({...p,dureza:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Tratamento Térmico</label><input className="erp-input mt-1 h-8 text-sm" value={trac.tratamento_termico} onChange={e => setTrac(p => ({...p,tratamento_termico:e.target.value}))} /></div>
          </div>
        )}

        {/* Impacto */}
        <button onClick={() => toggle('impacto')} className="flex items-center gap-2 w-full py-2 px-3 bg-muted rounded-md mb-2 font-medium text-sm">
          {sections.impacto ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />} Impacto
        </button>
        {sections.impacto && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 p-3 border border-border rounded-md">
            <div><label className="erp-label text-xs">Norma</label><input className="erp-input mt-1 h-8 text-sm" value={imp.norma} onChange={e => setImp(p => ({...p,norma:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Corpo Prova</label><input className="erp-input mt-1 h-8 text-sm" value={imp.corpo_prova} onChange={e => setImp(p => ({...p,corpo_prova:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Direção</label><input className="erp-input mt-1 h-8 text-sm" value={imp.direcao} onChange={e => setImp(p => ({...p,direcao:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Posição</label><input className="erp-input mt-1 h-8 text-sm" value={imp.posicao} onChange={e => setImp(p => ({...p,posicao:e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Temperatura</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={imp.temperatura} onChange={e => setImp(p => ({...p,temperatura:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Valor A</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={imp.valor_a} onChange={e => setImp(p => ({...p,valor_a:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Valor B</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={imp.valor_b} onChange={e => setImp(p => ({...p,valor_b:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Valor C</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={imp.valor_c} onChange={e => setImp(p => ({...p,valor_c:+e.target.value}))} /></div>
            <div><label className="erp-label text-xs">Média</label><input type="number" className="erp-input mt-1 h-8 text-sm" value={imp.media} onChange={e => setImp(p => ({...p,media:+e.target.value}))} /></div>
          </div>
        )}

        <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default Corridas;
