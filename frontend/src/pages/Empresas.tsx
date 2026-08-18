import { useState, useEffect } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { empresasService } from '@/services/api/empresas';
import { nfeNumeracoesService, type NFeNumeracaoConfig } from '@/services/api/fiscal';
import { consultaCep, consultaCnpj } from '@/services/api/consulta';
import { apiErrorMessage } from '@/services/api/config';
import { toast } from 'sonner';
import type { Empresa } from '@/types';
import { UFS } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState, LoadingState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { EmpresaNfeAmbienteSelector } from '@/components/cadastros/EmpresaNfeAmbienteSelector';
import { NFeInutilizacaoModal } from '@/components/fiscal/NFeInutilizacaoModal';
import type { NfeAmbienteEmpresa } from '@/lib/empresaNfeAmbiente';

const emptyEmpresa: Omit<Empresa, 'id'> = {
  razao_social:'', nome_fantasia:'', cnpj:'', ie:'', im:'', regime_tributario:'Lucro Presumido',
  logradouro:'', numero:'', complemento:'', bairro:'', cidade:'', uf:'SC', cep:'',
  telefone:'', email:'', site:'', empresa_pai_id:null, senha_certificado:'',
  nfe_ambiente: 'homologacao',
};

const Empresas = () => {
  const {
    items,
    count,
    page,
    pageSize,
    totalPages,
    search,
    setSearch,
    setPage,
    setPageSize,
    loading,
    error,
    reload,
  } = usePaginatedList<Empresa>({ fetchPage: empresasService.listPaginated });
  const [empresasOptions, setEmpresasOptions] = useState<Empresa[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Empresa | null>(null);
  const [form, setForm] = useState(emptyEmpresa);
  const [certFile, setCertFile] = useState<File | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [tab, setTab] = useState<'dados'|'endereco'|'contato'|'certificado'|'numeracao'>('dados');
  const [numeracoes, setNumeracoes] = useState<NFeNumeracaoConfig[]>([]);
  const [inutilizacaoConfigId, setInutilizacaoConfigId] = useState<number | null>(null);
  const [numeracaoLoading, setNumeracaoLoading] = useState(false);

  const loadOptions = async () => {
    const d = await empresasService.getAll({ limit: 100 });
    setEmpresasOptions(d);
  };

  useEffect(() => {
    if (modalOpen) void loadOptions();
  }, [modalOpen]);

  useEffect(() => {
    if (!modalOpen || tab !== 'numeracao' || !editing?.id) return;
    setNumeracaoLoading(true);
    nfeNumeracoesService
      .listByEmpresa(editing.id)
      .then(setNumeracoes)
      .catch(() => setNumeracoes([]))
      .finally(() => setNumeracaoLoading(false));
  }, [modalOpen, tab, editing?.id]);

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
    setForm({
      ...e,
      senha_certificado: '',
      nfe_ambiente: (e.nfe_ambiente || 'homologacao') as NfeAmbienteEmpresa,
    });
    setCertFile(null);
    setLogoFile(null);
    setLogoPreview(typeof e.logotipo === 'string' ? e.logotipo : null);
    setFormError(null);
    setTab('dados');
    setModalOpen(true);
  };
  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await empresasService.delete(id);
      void reload();
    }
  };

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
      void reload();
    } catch (error: unknown) {
      setFormError(apiErrorMessage(error));
    }
  };

  const f = (key: keyof typeof form, val: string | number | null) => setForm(prev => ({ ...prev, [key]: val }));

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
    { key: 'numeracao' as const, label: 'Fiscal / NF-e / Numeração' },
  ];

  return (
    <div>
      <PageHeader
        title="Empresas"
        description="Cadastro de empresas, certificados digitais e numeração de NF-e."
        onAdd={openNew}
        addLabel="Nova Empresa"
        searchValue={search}
        onSearch={setSearch}
      />
      <DataTableShell>
        {error ? <ErrorState onRetry={() => void reload()} /> : null}
        {loading ? <LoadingState /> : null}
        {!loading && !error ? (
          <DataTable mobileMode="cards">
            <thead><tr><th>Razão Social</th><th>CNPJ</th><th>Telefone</th><th>Cidade/UF</th><th className="w-24">Ações</th></tr></thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={5}><EmptyState message="Nenhuma empresa encontrada." actionLabel="Nova empresa" onAction={openNew} /></td></tr>
              ) : (
                items.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium">{e.razao_social}</td>
                    <td>{e.cnpj}</td>
                    <td>{e.telefone}</td>
                    <td>{e.cidade}/{e.uf}</td>
                    <td>
                      <div className="flex gap-1">
                        <button type="button" onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                        <button type="button" onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </DataTable>
        ) : null}
        {!loading && !error && count > 0 ? (
          <PaginationControls
            page={page}
            pageSize={pageSize}
            count={count}
            totalPages={totalPages}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        ) : null}
      </DataTableShell>

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Empresa' : 'Nova Empresa'} size="lg">
        {formError && (
          <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {formError}
          </div>
        )}
        <div className="flex flex-wrap gap-1 mb-4 border-b border-border">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} className={`px-2 sm:px-4 py-2 text-xs sm:text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>{t.label}</button>
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
                {empresasOptions.filter(i => i.id !== editing?.id).map(i => <option key={i.id} value={i.id}>{i.razao_social}</option>)}
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
        {tab === 'numeracao' && (
          <div className="space-y-4">
            {!editing ? (
              <p className="text-sm text-muted-foreground">Salve a empresa para configurar a numeração NF-e.</p>
            ) : (
              <>
                <EmpresaNfeAmbienteSelector
                  value={(form.nfe_ambiente || 'homologacao') as NfeAmbienteEmpresa}
                  producaoHabilitada={Boolean(form.nfe_producao_habilitada)}
                  onChange={(ambiente) => f('nfe_ambiente', ambiente)}
                />
                <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-950 dark:text-amber-100">
                  A alteração de série ou próximo número pode causar duplicidade, rejeição ou necessidade de
                  inutilização. Revise com o contador antes de alterar.
                </div>
                {numeracaoLoading ? (
                  <p className="text-sm text-muted-foreground">Carregando…</p>
                ) : (
                  <div className="space-y-4">
                    {numeracoes.map((cfg) => (
                      <div key={cfg.id} className="rounded-md border border-border p-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                          <label className="erp-label">Ambiente</label>
                          <p className="text-sm mt-1 capitalize">{cfg.ambiente}</p>
                        </div>
                        <div>
                          <label className="erp-label">Modelo</label>
                          <p className="text-sm mt-1">{cfg.modelo_documento}</p>
                        </div>
                        <div>
                          <label className="erp-label">Série</label>
                          <input
                            className="erp-input mt-1"
                            value={cfg.serie}
                            onChange={(e) =>
                              setNumeracoes((prev) =>
                                prev.map((x) => (x.id === cfg.id ? { ...x, serie: e.target.value } : x)),
                              )
                            }
                          />
                        </div>
                        <div>
                          <label className="erp-label">Próximo número</label>
                          <input
                            type="number"
                            className="erp-input mt-1"
                            value={cfg.proximo_numero}
                            onChange={(e) =>
                              setNumeracoes((prev) =>
                                prev.map((x) =>
                                  x.id === cfg.id ? { ...x, proximo_numero: Number(e.target.value) } : x,
                                ),
                              )
                            }
                          />
                        </div>
                        <div>
                          <label className="erp-label">Últ. reservado</label>
                          <p className="text-sm mt-1">{cfg.ultimo_numero_reservado ?? '—'}</p>
                        </div>
                        <div>
                          <label className="erp-label">Últ. autorizado</label>
                          <p className="text-sm mt-1">{cfg.ultimo_numero_autorizado ?? '—'}</p>
                        </div>
                        <div className="md:col-span-2 flex flex-col sm:flex-row items-stretch sm:items-end gap-2">
                          <button
                            type="button"
                            className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                            onClick={async () => {
                              try {
                                const confirmar =
                                  cfg.ambiente === 'producao'
                                    ? window.confirm(
                                        'Confirma alteração do próximo número em PRODUÇÃO? Revise com o contador.',
                                      )
                                    : true;
                                if (!confirmar) return;
                                await nfeNumeracoesService.update(cfg.id, {
                                  serie: cfg.serie,
                                  proximo_numero: cfg.proximo_numero,
                                  ativo: cfg.ativo,
                                  observacoes: cfg.observacoes,
                                  ...(cfg.ambiente === 'producao'
                                    ? { confirmar_alteracao_producao: true }
                                    : {}),
                                });
                                const list = await nfeNumeracoesService.listByEmpresa(editing.id);
                                setNumeracoes(list);
                                toast.success(
                                  `Numeração ${cfg.ambiente} salva — série ${cfg.serie}, próximo nº ${cfg.proximo_numero}.`,
                                );
                              } catch (error: unknown) {
                                const msg = apiErrorMessage(error);
                                setFormError(msg);
                                toast.error(msg);
                              }
                            }}
                          >
                            Salvar numeração
                          </button>
                          {(cfg.tipo_operacao ?? 'saida') === 'saida' ? (
                            <button
                              type="button"
                              className="erp-btn-destructive erp-btn-sm w-full sm:w-auto"
                              onClick={() => setInutilizacaoConfigId(cfg.id)}
                            >
                              Inutilizar numeração
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline w-full sm:w-auto">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary w-full sm:w-auto">Salvar</button>
        </div>
      </Modal>

      <NFeInutilizacaoModal
        mode="config"
        open={inutilizacaoConfigId != null}
        configuracaoId={inutilizacaoConfigId}
        onClose={() => setInutilizacaoConfigId(null)}
        onInutilizada={async () => {
          if (editing?.id) {
            const list = await nfeNumeracoesService.listByEmpresa(editing.id);
            setNumeracoes(list);
          }
        }}
      />
    </div>
  );
};

export default Empresas;
