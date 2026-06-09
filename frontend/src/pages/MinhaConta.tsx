import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { MinhaContaEditarDadosModal } from '@/components/minha-conta/MinhaContaEditarDadosModal';
import { appContextoService, type MinhaConta } from '@/services/api/appContexto';
import { setAppContextoCache } from '@/hooks/useAppContexto';
import { getUsuarioNomeExibicao } from '@/lib/usuarioExibicao';
import { formatCnpjDisplay } from '@/lib/cnpj';

function tipoUsuarioLabel(usuario: MinhaConta['usuario']): string {
  if (usuario.is_superuser) return 'Superusuário';
  if (usuario.is_staff) return 'Staff';
  return 'Usuário';
}

function statusLabel(ativo?: boolean): string {
  if (ativo === undefined) return '—';
  return ativo ? 'Ativo' : 'Inativo';
}

function DlRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words">{value ?? '—'}</dd>
    </>
  );
}

export default function MinhaConta() {
  const [data, setData] = useState<MinhaConta | null>(null);
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await appContextoService.getMinhaConta();
      setData(res);
      setAppContextoCache(res);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const { usuario, colaborador, empresa, avisos = [] } = data ?? {
    usuario: null,
    colaborador: null,
    empresa: null,
    avisos: [],
  };

  const nomeExibicao = getUsuarioNomeExibicao(usuario ?? undefined);

  return (
    <div className="erp-page">
      <PageHeader
        title="Minha conta"
        description="Dados do seu acesso ao sistema."
        breadcrumbs={[
          { label: 'Início', path: '/dashboard' },
          { label: 'Minha conta' },
        ]}
      />

      {loading ? (
        <p className="text-sm text-muted-foreground">Carregando…</p>
      ) : (
        <div className="grid gap-4 max-w-2xl">
          {avisos.length > 0 ? (
            <div className="rounded-lg border border-amber-300/60 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-700/50 px-4 py-3 text-sm text-amber-900 dark:text-amber-100">
              {avisos.map((msg) => (
                <p key={msg}>{msg}</p>
              ))}
            </div>
          ) : null}

          <section className="rounded-lg border border-border bg-card p-4 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-sm font-semibold">Dados pessoais</h2>
              <button type="button" className="erp-btn-secondary text-sm shrink-0" onClick={() => setEditOpen(true)}>
                Editar meus dados
              </button>
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
              <DlRow label="Nome" value={nomeExibicao} />
              <DlRow label="E-mail" value={usuario?.email} />
              <DlRow label="Telefone" value={colaborador?.telefone || '—'} />
              <DlRow label="Cargo" value={colaborador?.cargo || '—'} />
              <DlRow label="Departamento" value={colaborador?.departamento || '—'} />
            </dl>
          </section>

          <section className="rounded-lg border border-border bg-card p-4 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-sm font-semibold">Dados de acesso</h2>
              <Link to="/minha-conta/alterar-senha" className="erp-btn-secondary text-sm shrink-0">
                Alterar senha
              </Link>
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
              <DlRow label="Login" value={usuario?.username} />
              <DlRow label="Perfil de acesso" value={usuario?.perfil_label} />
              <DlRow label="Status do usuário" value={statusLabel(usuario?.is_active)} />
              <DlRow label="Tipo de usuário" value={usuario ? tipoUsuarioLabel(usuario) : '—'} />
            </dl>
          </section>

          {colaborador ? (
            <section className="rounded-lg border border-border bg-card p-4 space-y-2">
              <h2 className="text-sm font-semibold">Colaborador vinculado</h2>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                <DlRow label="Nome do colaborador" value={colaborador.nome} />
                <DlRow label="Código" value={colaborador.codigo || '—'} />
                <DlRow
                  label="Funções internas"
                  value={colaborador.funcoes_internas.length ? colaborador.funcoes_internas.join(', ') : '—'}
                />
                <DlRow label="Status do colaborador" value={statusLabel(colaborador.ativo)} />
              </dl>
            </section>
          ) : null}

          {empresa ? (
            <section className="rounded-lg border border-border bg-card p-4 space-y-2">
              <h2 className="text-sm font-semibold">Empresa atual</h2>
              <p className="text-xs text-muted-foreground">
                Identificação visual. Troca de empresa não disponível nesta versão.
              </p>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                <DlRow label="Nome" value={empresa.nome_exibicao} />
                <DlRow label="Razão social" value={empresa.razao_social} />
                <DlRow label="CNPJ" value={formatCnpjDisplay(empresa.cnpj)} />
                <DlRow label="Ambiente" value={data?.ambiente_label} />
              </dl>
            </section>
          ) : null}
        </div>
      )}

      {usuario ? (
        <MinhaContaEditarDadosModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          email={usuario.email}
          telefone={colaborador?.telefone || ''}
          onSaved={() => void load()}
        />
      ) : null}
    </div>
  );
}
