import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import { toast } from 'sonner';
import type { Colaborador } from '@/types';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { ColaboradorAcessoSection } from '@/components/cadastros/ColaboradorAcessoSection';
import { User, Briefcase, Key } from 'lucide-react';

import { WorkspaceLayout } from '@/components/workspace/WorkspaceLayout';
import { WorkspaceSection } from '@/components/workspace/WorkspaceSection';
import { WorkspaceField } from '@/components/workspace/WorkspaceField';

type ColaboradorForm = {
  nome: string;
  codigo: string;
  email: string;
  telefone: string;
  cargo: string;
  departamento: string;
  ativo: boolean;
  observacoes: string;
  eh_vendedor: boolean;
  eh_comprador: boolean;
  eh_responsavel_fiscal: boolean;
  eh_responsavel_financeiro: boolean;
  eh_responsavel_estoque: boolean;
  eh_responsavel_qualidade: boolean;
  eh_administrador: boolean;
};

const FUNCAO_CAMPOS: { key: keyof ColaboradorForm; label: string }[] = [
  { key: 'eh_vendedor', label: 'Vendedor' },
  { key: 'eh_comprador', label: 'Comprador' },
  { key: 'eh_responsavel_fiscal', label: 'Fiscal' },
  { key: 'eh_responsavel_financeiro', label: 'Financeiro' },
  { key: 'eh_responsavel_estoque', label: 'Estoque' },
  { key: 'eh_responsavel_qualidade', label: 'Qualidade' },
  { key: 'eh_administrador', label: 'Admin' },
];

type ColaboradorWorkspaceProps = {
  colaborador: Colaborador | null;
  onClose: () => void;
};

const formularioInicial: ColaboradorForm = {
  nome: '',
  codigo: '',
  email: '',
  telefone: '',
  cargo: '',
  departamento: '',
  ativo: true,
  observacoes: '',
  eh_vendedor: false,
  eh_comprador: false,
  eh_responsavel_fiscal: false,
  eh_responsavel_financeiro: false,
  eh_responsavel_estoque: false,
  eh_responsavel_qualidade: false,
  eh_administrador: false,
};

export default function ColaboradorWorkspace({ colaborador, onClose }: ColaboradorWorkspaceProps) {
  const navigate = useNavigate();
  const [form, setForm] = useState<ColaboradorForm>(formularioInicial);
  const [saving, setSaving] = useState(false);
  const [salvarError, setSalvarError] = useState<string | null>(null);
  const [modalTab, setModalTab] = useState<'dados' | 'funcoes' | 'acesso'>('dados');
  const [colaboradorAtual, setColaboradorAtual] = useState<Colaborador | null>(colaborador);
  const [colaboradorLoading, setColaboradorLoading] = useState(false);

  useEffect(() => {
    setColaboradorAtual(colaborador);
  }, [colaborador]);

  useEffect(() => {
    if (colaborador) {
      setForm({
        nome: colaborador.nome ?? '',
        codigo: colaborador.codigo ?? '',
        email: colaborador.email ?? '',
        telefone: colaborador.telefone ?? '',
        cargo: colaborador.cargo ?? '',
        departamento: colaborador.departamento ?? '',
        ativo: Boolean(colaborador.ativo),
        observacoes: colaborador.observacoes ?? '',
        eh_vendedor: Boolean(colaborador.eh_vendedor),
        eh_comprador: Boolean(colaborador.eh_comprador),
        eh_responsavel_fiscal: Boolean(colaborador.eh_responsavel_fiscal),
        eh_responsavel_financeiro: Boolean(colaborador.eh_responsavel_financeiro),
        eh_responsavel_estoque: Boolean(colaborador.eh_responsavel_estoque),
        eh_responsavel_qualidade: Boolean(colaborador.eh_responsavel_qualidade),
        eh_administrador: Boolean(colaborador.eh_administrador),
      });
    } else {
      setForm(formularioInicial);
    }
    setSalvarError(null);
  }, [colaborador]);

  useEffect(() => {
    if (colaborador?.id) {
      setModalTab('dados');
    }
  }, [colaborador?.id]);

  const handleSave = async () => {
    if (!form.nome.trim()) {
      setSalvarError('Nome é obrigatório.');
      return;
    }

    setSaving(true);
    setSalvarError(null);

    try {
      const payload = {
        ...form,
        nome: form.nome.trim(),
        codigo: form.codigo.trim(),
        email: form.email.trim(),
        telefone: form.telefone.trim(),
        cargo: form.cargo.trim(),
        departamento: form.departamento.trim(),
        observacoes: form.observacoes.trim(),
      };

      const salvo = colaboradorAtual?.id
        ? await colaboradoresService.update(colaboradorAtual.id, payload)
        : await colaboradoresService.create(payload);

      toast.success('Colaborador salvo');

      if (!colaboradorAtual?.id) {
        navigate(`/colaboradores/${salvo.id}`);
      }
    } catch (err) {
      setSalvarError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const reload = async () => {
    if (!colaboradorAtual?.id) return;

    setColaboradorLoading(true);
    try {
      const atualizado = await colaboradoresService.getById(colaboradorAtual.id);
      setColaboradorAtual(atualizado);
      setForm({
        nome: atualizado.nome ?? '',
        codigo: atualizado.codigo ?? '',
        email: atualizado.email ?? '',
        telefone: atualizado.telefone ?? '',
        cargo: atualizado.cargo ?? '',
        departamento: atualizado.departamento ?? '',
        ativo: Boolean(atualizado.ativo),
        observacoes: atualizado.observacoes ?? '',
        eh_vendedor: Boolean(atualizado.eh_vendedor),
        eh_comprador: Boolean(atualizado.eh_comprador),
        eh_responsavel_fiscal: Boolean(atualizado.eh_responsavel_fiscal),
        eh_responsavel_financeiro: Boolean(atualizado.eh_responsavel_financeiro),
        eh_responsavel_estoque: Boolean(atualizado.eh_responsavel_estoque),
        eh_responsavel_qualidade: Boolean(atualizado.eh_responsavel_qualidade),
        eh_administrador: Boolean(atualizado.eh_administrador),
      });
    } finally {
      setColaboradorLoading(false);
    }
  };

  return (
    <WorkspaceLayout
      title={colaboradorAtual?.id ? 'Editar colaborador' : 'Novo colaborador'}
      subtitle="Cadastro de colaborador com funções e perfil de acesso ao sistema."
      breadcrumbs={[
        { label: 'Cadastros', path: '/colaboradores' },
        { label: 'Colaboradores', path: '/colaboradores' },
        { label: colaboradorAtual?.id ? 'Editar' : 'Novo' }
      ]}
      onSave={handleSave}
      onClose={onClose}
      saving={saving}
      saveLabel="Salvar colaborador"
      error={salvarError}
      meta={[
        { label: 'Código', value: form.codigo || '—' },
        { label: 'E-mail', value: form.email || '—' },
        { label: 'Cargo', value: form.cargo || '—' },
        { label: 'Status', value: <StatusBadge status={form.ativo ? 'Ativo' : 'Inativo'} className="mt-0.5" /> },
      ]}
      tabs={[
        {
          value: 'dados',
          label: 'Dados',
          icon: User,
          content: (
            <div>
              <WorkspaceSection title="Informações básicas" className="pt-0">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <WorkspaceField label="Nome" required={true}>
                    <input
                      className="erp-input mt-1"
                      value={form.nome}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, nome: e.target.value }))
                      }
                    />
                  </WorkspaceField>
                  <WorkspaceField label="Código">
                    <input
                      className="erp-input mt-1"
                      value={form.codigo}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, codigo: e.target.value }))
                      }
                    />
                  </WorkspaceField>
                  <WorkspaceField label="Ativo">
                    <label className="flex items-center gap-2 text-sm pt-1.5">
                      <input
                        type="checkbox"
                        checked={form.ativo}
                        onChange={(e) =>
                          setForm((p) => ({ ...p, ativo: e.target.checked }))
                        }
                      />
                      <span>{form.ativo ? 'Ativo' : 'Inativo'}</span>
                    </label>
                  </WorkspaceField>
                </div>
              </WorkspaceSection>

              <WorkspaceSection title="Contato" description="">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <WorkspaceField label="E-mail">
                    <input
                      type="email"
                      className="erp-input"
                      value={form.email}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, email: e.target.value }))
                      }
                    />
                  </WorkspaceField>
                  <WorkspaceField label="Telefone">
                    <input
                      className="erp-input"
                      value={form.telefone}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, telefone: e.target.value }))
                      }
                    />
                  </WorkspaceField>
                </div>
              </WorkspaceSection>

              <WorkspaceSection title="Vínculo profissional" className="pt-0">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <WorkspaceField label="Cargo">
                    <input
                      className="erp-input"
                      value={form.cargo}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, cargo: e.target.value }))
                      }
                    />
                  </WorkspaceField>
                  <WorkspaceField label="Departamento">
                    <input
                      className="erp-input"
                      value={form.departamento}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, departamento: e.target.value }))
                      }
                    />
                  </WorkspaceField>
                  <WorkspaceField
                    label="Observações"
                    className="md:col-span-2"
                  >
                    <textarea
                      className="erp-input min-h-[8rem]"
                      rows={3}
                      value={form.observacoes}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, observacoes: e.target.value }))
                      }
                    />
                  </WorkspaceField>
                </div>
              </WorkspaceSection>
            </div>
          ),
        },
        {
          value: 'funcoes',
          label: 'Funções',
          icon: Briefcase,
          content: (
            <WorkspaceSection
              title="Funções internas"
              description="Indicam como o colaborador participa da operação interna. Não substituem o perfil de acesso ao sistema."
            >
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {FUNCAO_CAMPOS.map((f) => (
                  <label
                    key={f.key}
                    className={
                      `flex items-center gap-2 rounded-md border px-3 py-2 cursor-pointer transition-colors ${form[f.key]
                        ? 'border-primary/30 bg-primary/5'
                        : 'border-border hover:bg-muted/30'}`
                    }
                  >
                    <input
                      type="checkbox"
                      checked={Boolean(form[f.key])}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, [f.key]: e.target.checked }))
                      }
                    />
                    <span className="text-sm">{f.label}</span>
                  </label>
                ))}
              </div>
            </WorkspaceSection>
          ),
        },
        {
          value: 'acesso',
          label: 'Acesso',
          icon: Key,
          content: (
            <ColaboradorAcessoSection
              colaborador={colaboradorAtual}
              onRefresh={() => void reload()}
            />
          ),
        },
      ]}
      activeTab={modalTab}
      onTabChange={setModalTab}
    />
  );
}