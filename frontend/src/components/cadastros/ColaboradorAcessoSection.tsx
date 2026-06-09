import { useState } from 'react';
import {
  acessoColaboradorTooltip,
  badgeAcessoListagem,
  badgeAcessoVariant,
  tipoUsuarioLabel,
} from '@/lib/colaboradorAcesso';
import type { Colaborador } from '@/types';
import { CriarUsuarioColaboradorModal } from './CriarUsuarioColaboradorModal';
import { DefinirPerfilAcessoModal } from './DefinirPerfilAcessoModal';
import { DesativarAcessoModal } from './DesativarAcessoModal';
import { EditarAcessoModal } from './EditarAcessoModal';
import { RedefinirSenhaColaboradorModal } from './RedefinirSenhaColaboradorModal';
import { VincularUsuarioExistenteModal } from './VincularUsuarioExistenteModal';

type Props = {
  colaborador: Colaborador | null;
  onRefresh: () => void;
};

function badgeClass(variant: ReturnType<typeof badgeAcessoVariant>): string {
  switch (variant) {
    case 'destructive':
      return 'bg-destructive/15 text-destructive';
    case 'warning':
      return 'bg-amber-500/15 text-amber-900 dark:text-amber-100';
    case 'muted':
      return 'bg-muted text-muted-foreground';
    default:
      return 'bg-primary/10 text-primary';
  }
}

export function ColaboradorAcessoSection({ colaborador, onRefresh }: Props) {
  const [modal, setModal] = useState<'criar' | 'vincular' | 'perfil' | 'editar' | 'desativar' | 'senha' | null>(
    null,
  );

  if (!colaborador?.id) {
    return (
      <p className="text-sm text-muted-foreground">
        Salve o colaborador antes de configurar o acesso ao sistema.
      </p>
    );
  }

  const c = colaborador;
  const temUsuario = Boolean(c.usuario_id || c.acesso_sistema?.tem_usuario);
  const badge = badgeAcessoListagem(c);
  const variant = badgeAcessoVariant(c);
  const closeModal = () => setModal(null);

  const handleSuccess = () => {
    onRefresh();
    closeModal();
  };

  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div>
        <h3 className="text-sm font-semibold">Acesso ao sistema</h3>
        <p className="text-[11px] text-muted-foreground mt-1">
          As funções internas indicam atuação operacional. O perfil de acesso define o que o usuário pode acessar no
          sistema.
        </p>
      </div>

      {!temUsuario ? (
        <>
          <p className="text-sm text-muted-foreground">Este colaborador ainda não possui acesso ao sistema.</p>
          <div className="flex flex-wrap gap-2">
            {c.pode_criar_usuario ? (
              <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setModal('criar')}>
                Criar usuário de acesso
              </button>
            ) : null}
            {c.pode_vincular_usuario ? (
              <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setModal('vincular')}>
                Vincular usuário existente
              </button>
            ) : null}
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${badgeClass(variant)}`}
              title={acessoColaboradorTooltip(c)}
            >
              {badge}
            </span>
          </div>

          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">Status</dt>
              <dd>{c.usuario_ativo ? 'Ativo' : 'Inativo'}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Login</dt>
              <dd className="font-mono text-xs">{c.usuario_login || '—'}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-muted-foreground">E-mail de acesso</dt>
              <dd>{c.usuario_email || '—'}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Perfil de acesso</dt>
              <dd>{c.perfil_acesso_label || (c.sem_perfil ? 'Sem perfil' : '—')}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Tipo de usuário</dt>
              <dd>{tipoUsuarioLabel(c)}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-muted-foreground">Grupos/perfis</dt>
              <dd>
                {c.usuario_is_superuser
                  ? '— (superusuário)'
                  : c.usuario_grupos?.filter((g) => g !== 'superusuario').join(', ') || 'nenhum'}
              </dd>
            </div>
          </dl>

          {c.email_tecnico ? (
            <p className="text-xs text-amber-800 dark:text-amber-200 rounded border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20 px-2 py-1.5">
              Este e-mail é técnico/local. Para produção, informe um e-mail real.
            </p>
          ) : null}

          {c.motivo_bloqueio_acesso ? (
            <p className="text-xs text-amber-800 dark:text-amber-200">{c.motivo_bloqueio_acesso}</p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {c.pode_editar_acesso ? (
              <button type="button" className="erp-btn-primary erp-btn-sm" onClick={() => setModal('editar')}>
                Editar acesso
              </button>
            ) : null}
            {c.pode_definir_perfil ? (
              <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setModal('perfil')}>
                Definir perfil
              </button>
            ) : null}
            {c.pode_redefinir_senha ? (
              <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setModal('senha')}>
                Redefinir senha
              </button>
            ) : null}
            {c.pode_desativar_acesso ? (
              <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setModal('desativar')}>
                Desativar acesso
              </button>
            ) : null}
          </div>
        </>
      )}

      {modal === 'criar' ? (
        <CriarUsuarioColaboradorModal colaborador={c} onClose={closeModal} onSuccess={handleSuccess} />
      ) : null}
      {modal === 'vincular' ? (
        <VincularUsuarioExistenteModal colaborador={c} onClose={closeModal} onSuccess={handleSuccess} />
      ) : null}
      {modal === 'perfil' ? (
        <DefinirPerfilAcessoModal colaborador={c} onClose={closeModal} onSuccess={handleSuccess} />
      ) : null}
      {modal === 'editar' ? (
        <EditarAcessoModal colaborador={c} onClose={closeModal} onSuccess={handleSuccess} />
      ) : null}
      {modal === 'desativar' ? (
        <DesativarAcessoModal colaborador={c} onClose={closeModal} onSuccess={handleSuccess} />
      ) : null}
      {modal === 'senha' ? (
        <RedefinirSenhaColaboradorModal colaborador={c} onClose={closeModal} onSuccess={handleSuccess} />
      ) : null}
    </div>
  );
}
