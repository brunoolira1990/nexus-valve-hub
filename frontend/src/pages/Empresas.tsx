import { useState, useEffect } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { empresasService } from '@/services/api/empresas';
import { consultaCep, consultaCnpj } from '@/services/api/consulta';
import { apiErrorMessage } from '@/services/api/config';
import type { Empresa } from '@/types';
import { UFS } from '@/types';

const emptyEmpresa: Omit<Empresa, 'id'> = {
  razao_social:'', nome_fantasia:'', cnpj:'', ie:'', im:'', regime_tributario:'Lucro Presumido',
  logradouro:'', numero:'', complemento:'', bairro:'', cidade:'', uf:'SC', cep:'',
  telefone:'', email:'', site:'', empresa_pai_id:null, senha_certificado:'',
};

const Empresas = () => {
  const [items, setItems] = useState<Empresa[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Empresa | null>(null);
  const [form, setForm] = useState(emptyEmpresa);
  const [certFile, setCertFile] = useState<File | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [tab, setTab] = useState<'dados'|'endereco'|'contato'|'certificado'>('dados');

  const load = async () => { const d = await empresasService.getAll(); setItems(d); };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyEmpresa });
    setCertFile(null);
    setLogoFile(null);
    setLogoPreview(null);
    setFormError(null);
    setTab('dados');
    setModalOpen(true);
  };
  const openEdit = (e: Empresa) => {
    setEditing(e);
    setForm({ ...e, senha_certificado: '' });
    setCertFile(null);
    setLogoFile(null);
    setLogoPreview(typeof e.logotipo === 'string' ? e.logotipo : null);
    setFormError(null);
    setTab('dados');
    setModalOpen(true);
  };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await empresasService.delete(id); load(); } };

  const handleSave = async () => {
    try {
      setFormError(null);
      const files = { cert: certFile, logo: logoFile };
      if (editing) await empresasService.update(editing.id, form, files);
      else await empresasService.create(form, files);
      setModalOpen(false);
      setCertFile(null);
      setLogoFile(null);
      setLogoPreview(null);
      load();
    } catch (error: unknown) {
      setFormError(apiErrorMessage(error));
    }
  };

  const f = (key: keyof typeof form, val: string | number | null) => setForm(prev => ({ ...prev, [key]: val }));
  const filtered = items.filter(i => i.razao_social.toLowerCase().includes(search.toLowerCase()) || i.cnpj.includes(search));

  useEffect(() => {
    if (!logoFile) return;
    const objectUrl = URL.createObjectURL(logoFile);
    setLogoPreview(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [logoFile]);

  const handleCepBlur = async () => {
    const cep = (form.cep || '').replace(/\D/g, '');
    if (cep.length !== 8) return;
    try {
      setFormError(null);
      const { data } = await consultaCep(cep);
      setForm(prev => ({
        ...prev,
        logradouro: data.logradouro || prev.logradouro,
        bairro: data.bairro || prev.bairro,
        cidade: data.cidade || prev.cidade,
        uf: data.uf || prev.uf,
        cep: data.cep || prev.cep,
      }));
    } catch (error: unknown) {
      setFormError(apiErrorMessage(error));
    }
  };

  const handleCnpjBlur = async () => {
    const cnpj = (form.cnpj || '').replace(/\D/g, '');
    if (cnpj.length !== 14) return;
    try {
      setFormError(null);
      const { data } = await consultaCnpj(cnpj);
      setForm(prev => ({
        ...prev,
        razao_social: data.razao_social || prev.razao_social,
        nome_fantasia: data.nome_fantasia || prev.nome_fantasia,
        logradouro: data.logradouro || prev.logradouro,
        numero: data.numero || prev.numero,
        complemento: data.complemento || prev.complemento,
        bairro: data.bairro || prev.bairro,
        cidade: data.cidade || prev.cidade,
        uf: data.uf || prev.uf,
        cep: data.cep || prev.cep,
        telefone: data.telefone || prev.telefone,
      }));
    } catch (error: unknown) {
      setFormError(apiErrorMessage(error));
    }
  };

  const tabs = [
    { key: 'dados' as const, label: 'Dados Principais' },
    { key: 'endereco' as const, label: 'Endereço' },
    { key: 'contato' as const, label: 'Contato' },
    { key: 'certificado' as const, label: 'Certificado Digital' },
  ];

  return (
    <div>
      <PageHeader title="Empresas" onAdd={openNew} addLabel="Nova Empresa" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Razão Social</th><th>CNPJ</th><th>Telefone</th><th>Cidade/UF</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-medium">{e.razao_social}</td>
                <td>{e.cnpj}</td>
                <td>{e.telefone}</td>
                <td>{e.cidade}/{e.uf}</td>
                <td>
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                    <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Empresa' : 'Nova Empresa'} size="lg">
        {formError && (
          <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {formError}
          </div>
        )}
        <div className="flex gap-1 mb-4 border-b border-border">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>{t.label}</button>
          ))}
        </div>

        {tab === 'dados' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="erp-label">Razão Social</label><input className="erp-input mt-1" value={form.razao_social} onChange={e => f('razao_social', e.target.value)} /></div>
            <div><label className="erp-label">Nome Fantasia</label><input className="erp-input mt-1" value={form.nome_fantasia} onChange={e => f('nome_fantasia', e.target.value)} /></div>
            <div><label className="erp-label">CNPJ</label><input className="erp-input mt-1" value={form.cnpj} onChange={e => f('cnpj', e.target.value)} onBlur={handleCnpjBlur} /></div>
            <div><label className="erp-label">IE</label><input className="erp-input mt-1" value={form.ie} onChange={e => f('ie', e.target.value)} /></div>
            <div><label className="erp-label">IM</label><input className="erp-input mt-1" value={form.im} onChange={e => f('im', e.target.value)} /></div>
            <div><label className="erp-label">Regime Tributário</label>
              <select className="erp-select mt-1" value={form.regime_tributario} onChange={e => f('regime_tributario', e.target.value)}>
                <option>Simples Nacional</option><option>Lucro Presumido</option><option>Lucro Real</option>
              </select>
            </div>
            <div><label className="erp-label">Empresa Pai (Filial de)</label>
              <select className="erp-select mt-1" value={form.empresa_pai_id ?? ''} onChange={e => f('empresa_pai_id', e.target.value ? Number(e.target.value) : null)}>
                <option value="">Nenhuma (Matriz)</option>
                {items.filter(i => i.id !== editing?.id).map(i => <option key={i.id} value={i.id}>{i.razao_social}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="erp-label">Logotipo</label>
              <input
                type="file"
                accept="image/*"
                className="erp-input mt-1"
                onChange={e => setLogoFile(e.target.files?.[0] ?? null)}
              />
              {logoPreview && (
                <img src={logoPreview} alt="Preview do logotipo" className="mt-3 h-20 w-20 rounded-md border border-border object-contain bg-background p-1" />
              )}
            </div>
          </div>
        )}
        {tab === 'endereco' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className="erp-label">Logradouro</label><input className="erp-input mt-1" value={form.logradouro} onChange={e => f('logradouro', e.target.value)} /></div>
            <div><label className="erp-label">Número</label><input className="erp-input mt-1" value={form.numero} onChange={e => f('numero', e.target.value)} /></div>
            <div><label className="erp-label">Complemento</label><input className="erp-input mt-1" value={form.complemento} onChange={e => f('complemento', e.target.value)} /></div>
            <div><label className="erp-label">Bairro</label><input className="erp-input mt-1" value={form.bairro} onChange={e => f('bairro', e.target.value)} /></div>
            <div><label className="erp-label">Cidade</label><input className="erp-input mt-1" value={form.cidade} onChange={e => f('cidade', e.target.value)} /></div>
            <div><label className="erp-label">UF</label>
              <select className="erp-select mt-1" value={form.uf} onChange={e => f('uf', e.target.value)}>{UFS.map(u => <option key={u}>{u}</option>)}</select>
            </div>
            <div><label className="erp-label">CEP</label><input className="erp-input mt-1" value={form.cep} onChange={e => f('cep', e.target.value)} onBlur={handleCepBlur} /></div>
          </div>
        )}
        {tab === 'contato' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="erp-label">Telefone</label><input className="erp-input mt-1" value={form.telefone} onChange={e => f('telefone', e.target.value)} /></div>
            <div><label className="erp-label">E-mail</label><input className="erp-input mt-1" value={form.email} onChange={e => f('email', e.target.value)} /></div>
            <div><label className="erp-label">Site</label><input className="erp-input mt-1" value={form.site} onChange={e => f('site', e.target.value)} /></div>
          </div>
        )}
        {tab === 'certificado' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="erp-label">Arquivo do Certificado (.p12 / .pfx)</label><input type="file" accept=".p12,.pfx" className="erp-input mt-1" onChange={e => setCertFile(e.target.files?.[0] ?? null)} /></div>
            <div><label className="erp-label">Senha do Certificado</label><input type="password" className="erp-input mt-1" value={form.senha_certificado} onChange={e => f('senha_certificado', e.target.value)} /></div>
          </div>
        )}

        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default Empresas;
