import { useCallback, useEffect, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { apiErrorMessage } from '@/services/api/config';
import {
  financeiroService,
  type CategoriaFinanceira,
  type CentroCusto,
  type ContaFinanceira,
} from '@/services/api/financeiro';
import {
  contaFinanceiraTipoBanco,
  labelBancoContaListagem,
  labelNomeContaFinanceira,
  PLACEHOLDER_BANCO_CONTA_FINANCEIRA,
  placeholderNomeContaFinanceira,
  validarContaFinanceiraForm,
} from '@/lib/financeiroUi';

type Tab = 'contas' | 'categorias' | 'centros';

const TABS: { id: Tab; label: string }[] = [
  { id: 'contas', label: 'Contas / Caixas' },
  { id: 'categorias', label: 'Categorias' },
  { id: 'centros', label: 'Centros de custo' },
];

const FinanceiroCadastros = () => {
  const [tab, setTab] = useState<Tab>('contas');
  const [loading, setLoading] = useState(true);
  const [contas, setContas] = useState<ContaFinanceira[]>([]);
  const [categorias, setCategorias] = useState<CategoriaFinanceira[]>([]);
  const [centros, setCentros] = useState<CentroCusto[]>([]);
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [c, cat, cc] = await Promise.all([
        financeiroService.listContas({ limit: 200 }),
        financeiroService.listCategorias({ limit: 200 }),
        financeiroService.listCentrosCusto({ limit: 200 }),
      ]);
      setContas(c.results ?? []);
      setCategorias(cat.results ?? []);
      setCentros(cc.results ?? []);
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível carregar os cadastros financeiros.' }));
      setContas([]);
      setCategorias([]);
      setCentros([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <div>
      <PageHeader
        title="Cadastros financeiros"
        description="Contas, categorias e centros de custo — base para baixas e títulos."
      />

      <div className="flex flex-wrap gap-2 mb-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`erp-btn-sm ${tab === t.id ? 'erp-btn-primary' : 'erp-btn-outline'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Carregando…</p> : null}

      {tab === 'contas' && !loading ? <CadastroContasTable items={contas} onReload={reload} /> : null}
      {tab === 'categorias' && !loading ? (
        <CadastroCategoriasTable items={categorias} onReload={reload} />
      ) : null}
      {tab === 'centros' && !loading ? (
        <CadastroCentrosCustoTable items={centros} onReload={reload} />
      ) : null}
    </div>
  );
};

function CadastroContasTable({
  items,
  onReload,
}: {
  items: ContaFinanceira[];
  onReload: () => void;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ContaFinanceira | null>(null);
  const [form, setForm] = useState({
    nome: '',
    tipo: 'CAIXA',
    banco: '',
    agencia: '',
    conta: '',
    ativo: true,
    observacoes: '',
  });

  const openNew = () => {
    setEditing(null);
    setForm({ nome: '', tipo: 'CAIXA', banco: '', agencia: '', conta: '', ativo: true, observacoes: '' });
    setModalOpen(true);
  };
  const openEdit = (c: ContaFinanceira) => {
    setEditing(c);
    setForm({
      nome: c.nome,
      tipo: c.tipo,
      banco: c.banco || '',
      agencia: c.agencia || '',
      conta: c.conta || '',
      ativo: c.ativo,
      observacoes: c.observacoes || '',
    });
    setModalOpen(true);
  };

  const salvar = async () => {
    const erro = validarContaFinanceiraForm(form);
    if (erro) {
      toast.error(erro);
      return;
    }
    const payload = {
      ...form,
      nome: form.nome.trim(),
      banco: form.banco.trim(),
      agencia: form.agencia.trim(),
      conta: form.conta.trim(),
      observacoes: form.observacoes.trim(),
    };
    try {
      if (editing) await financeiroService.updateConta(editing.id, payload);
      else await financeiroService.createConta(payload);
      toast.success('Conta salva.');
      setModalOpen(false);
      onReload();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  const excluir = async (id: number) => {
    if (!confirm('Excluir esta conta?')) return;
    try {
      await financeiroService.deleteConta(id);
      toast.success('Conta removida.');
      onReload();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  return (
    <div className="erp-card overflow-x-auto">
      <div className="flex justify-between items-center p-4 border-b border-border">
        <h3 className="font-semibold">Contas / Caixas</h3>
        <button type="button" onClick={openNew} className="erp-btn-primary erp-btn-sm">
          <Plus className="h-3 w-3" /> Nova conta
        </button>
      </div>
      <table className="erp-table">
        <thead>
          <tr>
            <th>Nome</th>
            <th>Tipo</th>
            <th>Banco</th>
            <th>Ativo</th>
            <th className="w-24">Ações</th>
          </tr>
        </thead>
        <tbody>
          {(items ?? []).map((c) => (
            <tr key={c.id}>
              <td className="font-medium">{c.nome}</td>
              <td>{c.tipo_label || c.tipo}</td>
              <td>{labelBancoContaListagem(c)}</td>
              <td>{c.ativo ? 'Sim' : 'Não'}</td>
              <td>
                <button type="button" className="erp-btn-ghost erp-btn-sm" onClick={() => openEdit(c)}>
                  <Pencil className="h-3 w-3" />
                </button>
                <button type="button" className="erp-btn-ghost erp-btn-sm text-destructive" onClick={() => void excluir(c.id)}>
                  <Trash2 className="h-3 w-3" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar conta' : 'Nova conta'} size="md">
        <div className="space-y-3">
          <div>
            <label htmlFor="conta-tipo" className="erp-label">Tipo</label>
            <select id="conta-tipo" className="erp-select mt-1 w-full" value={form.tipo} onChange={(e) => setForm((p) => ({ ...p, tipo: e.target.value }))}>
              <option value="CAIXA">Caixa</option>
              <option value="BANCO">Banco</option>
              <option value="CARTEIRA">Carteira</option>
              <option value="OUTRO">Outro</option>
            </select>
          </div>
          {contaFinanceiraTipoBanco(form.tipo) ? (
            <>
              <div>
                <label htmlFor="conta-banco" className="erp-label">Banco</label>
                <input
                  id="conta-banco"
                  className="erp-input mt-1 w-full"
                  value={form.banco}
                  onChange={(e) => setForm((p) => ({ ...p, banco: e.target.value }))}
                  placeholder={PLACEHOLDER_BANCO_CONTA_FINANCEIRA}
                />
              </div>
              <div>
                <label htmlFor="conta-nome" className="erp-label">{labelNomeContaFinanceira(form.tipo)}</label>
                <input
                  id="conta-nome"
                  className="erp-input mt-1 w-full"
                  value={form.nome}
                  onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))}
                  placeholder={placeholderNomeContaFinanceira(form.tipo)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="conta-agencia" className="erp-label">Agência</label>
                  <input
                    id="conta-agencia"
                    className="erp-input mt-1 w-full"
                    value={form.agencia}
                    onChange={(e) => setForm((p) => ({ ...p, agencia: e.target.value }))}
                    placeholder="Opcional"
                  />
                </div>
                <div>
                  <label htmlFor="conta-conta" className="erp-label">Conta</label>
                  <input
                    id="conta-conta"
                    className="erp-input mt-1 w-full"
                    value={form.conta}
                    onChange={(e) => setForm((p) => ({ ...p, conta: e.target.value }))}
                    placeholder="Opcional"
                  />
                </div>
              </div>
            </>
          ) : (
            <div>
              <label htmlFor="conta-nome" className="erp-label">{labelNomeContaFinanceira(form.tipo)}</label>
              <input
                id="conta-nome"
                className="erp-input mt-1 w-full"
                value={form.nome}
                onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))}
                placeholder={placeholderNomeContaFinanceira(form.tipo)}
              />
            </div>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.ativo} onChange={(e) => setForm((p) => ({ ...p, ativo: e.target.checked }))} />
            Ativo
          </label>
          <div>
            <label htmlFor="conta-observacoes" className="erp-label">Observações</label>
            <textarea
              id="conta-observacoes"
              className="erp-input mt-1 w-full min-h-[72px]"
              value={form.observacoes}
              onChange={(e) => setForm((p) => ({ ...p, observacoes: e.target.value }))}
              placeholder="Opcional"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" className="erp-btn-outline" onClick={() => setModalOpen(false)}>
              Cancelar
            </button>
            <button type="button" className="erp-btn-primary" onClick={() => void salvar()}>
              Salvar
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function CadastroCategoriasTable({ items, onReload }: { items: CategoriaFinanceira[]; onReload: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CategoriaFinanceira | null>(null);
  const [form, setForm] = useState({ nome: '', tipo: 'AMBOS', ativo: true, observacoes: '' });

  const salvar = async () => {
    try {
      if (editing) await financeiroService.updateCategoria(editing.id, form);
      else await financeiroService.createCategoria(form);
      toast.success('Categoria salva.');
      setModalOpen(false);
      onReload();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  return (
    <div className="erp-card overflow-x-auto">
      <div className="flex justify-between items-center p-4 border-b border-border">
        <h3 className="font-semibold">Categorias</h3>
        <button
          type="button"
          onClick={() => {
            setEditing(null);
            setForm({ nome: '', tipo: 'AMBOS', ativo: true, observacoes: '' });
            setModalOpen(true);
          }}
          className="erp-btn-primary erp-btn-sm"
        >
          <Plus className="h-3 w-3" /> Nova categoria
        </button>
      </div>
      <table className="erp-table">
        <thead>
          <tr>
            <th>Nome</th>
            <th>Tipo</th>
            <th>Ativo</th>
            <th className="w-16">Ações</th>
          </tr>
        </thead>
        <tbody>
          {(items ?? []).map((c) => (
            <tr key={c.id}>
              <td className="font-medium">{c.nome}</td>
              <td>{c.tipo_label || c.tipo}</td>
              <td>{c.ativo ? 'Sim' : 'Não'}</td>
              <td>
                <button
                  type="button"
                  className="erp-btn-ghost erp-btn-sm"
                  onClick={() => {
                    setEditing(c);
                    setForm({ nome: c.nome, tipo: c.tipo, ativo: c.ativo, observacoes: c.observacoes || '' });
                    setModalOpen(true);
                  }}
                >
                  <Pencil className="h-3 w-3" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar categoria' : 'Nova categoria'} size="sm">
        <div className="space-y-3">
          <div>
            <label className="erp-label">Nome</label>
            <input className="erp-input mt-1 w-full" value={form.nome} onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))} />
          </div>
          <div>
            <label className="erp-label">Tipo</label>
            <select className="erp-select mt-1 w-full" value={form.tipo} onChange={(e) => setForm((p) => ({ ...p, tipo: e.target.value }))}>
              <option value="RECEITA">Receita</option>
              <option value="DESPESA">Despesa</option>
              <option value="AMBOS">Ambos</option>
            </select>
          </div>
          <button type="button" className="erp-btn-primary w-full" onClick={() => void salvar()}>
            Salvar
          </button>
        </div>
      </Modal>
    </div>
  );
}

function CadastroCentrosCustoTable({ items, onReload }: { items: CentroCusto[]; onReload: () => void }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CentroCusto | null>(null);
  const [form, setForm] = useState({ nome: '', ativo: true, observacoes: '' });

  const salvar = async () => {
    try {
      if (editing) await financeiroService.updateCentroCusto(editing.id, form);
      else await financeiroService.createCentroCusto(form);
      toast.success('Centro de custo salvo.');
      setModalOpen(false);
      onReload();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  return (
    <div className="erp-card overflow-x-auto">
      <div className="flex justify-between items-center p-4 border-b border-border">
        <h3 className="font-semibold">Centros de custo</h3>
        <button
          type="button"
          onClick={() => {
            setEditing(null);
            setForm({ nome: '', ativo: true, observacoes: '' });
            setModalOpen(true);
          }}
          className="erp-btn-primary erp-btn-sm"
        >
          <Plus className="h-3 w-3" /> Novo centro
        </button>
      </div>
      <table className="erp-table">
        <thead>
          <tr>
            <th>Nome</th>
            <th>Ativo</th>
            <th className="w-16">Ações</th>
          </tr>
        </thead>
        <tbody>
          {(items ?? []).map((c) => (
            <tr key={c.id}>
              <td className="font-medium">{c.nome}</td>
              <td>{c.ativo ? 'Sim' : 'Não'}</td>
              <td>
                <button
                  type="button"
                  className="erp-btn-ghost erp-btn-sm"
                  onClick={() => {
                    setEditing(c);
                    setForm({ nome: c.nome, ativo: c.ativo, observacoes: c.observacoes || '' });
                    setModalOpen(true);
                  }}
                >
                  <Pencil className="h-3 w-3" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar centro' : 'Novo centro'} size="sm">
        <div className="space-y-3">
          <div>
            <label className="erp-label">Nome</label>
            <input className="erp-input mt-1 w-full" value={form.nome} onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.ativo} onChange={(e) => setForm((p) => ({ ...p, ativo: e.target.checked }))} />
            Ativo
          </label>
          <button type="button" className="erp-btn-primary w-full" onClick={() => void salvar()}>
            Salvar
          </button>
        </div>
      </Modal>
    </div>
  );
}

export default FinanceiroCadastros;
