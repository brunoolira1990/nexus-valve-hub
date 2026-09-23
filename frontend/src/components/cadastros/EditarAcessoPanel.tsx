import { useEffect, useState } from 'react';
import { InlinePanel } from '@/components/workspace/InlinePanel';
import { WorkspaceField } from '@/components/workspace/WorkspaceField';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import { PERFIS_ACESSO, perfilInicialSugerido } from '@/lib/colaboradorAcesso';
import { useAppContexto } from '@/hooks/useAppContexto';
import type { Colaborador } from '@/types';

type Props = {
  colaborador: Colaborador;
  onSuccess: () => void;
  onClose: () => void;
};

export function EditarAcessoPanel({ colaborador, onSuccess, onClose }: Props) {
  const { data: ctx } = useAppContexto();
  const actorSuper = Boolean(ctx?.usuario?.is_superuser);

  const [ativo, setAtivo] = useState(Boolean(colaborador.usuario_ativo));
  const [email, setEmail] = useState(colaborador.usuario_email || colaborador.email || '');
  const [perfil, setPerfil] = useState(
    colaborador.usuario_is_superuser ? '' : perfilInicialSugerido(colaborador),
  );
  const [isStaff, setIsStaff] = useState(Boolean(colaborador.usuario_is_staff));
  const [isSuperuser, setIsSuperuser] = useState(Boolean(colaborador.usuario_is_superuser));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [perfis, setPerfis] = useState<{ value: string; label: string }[]>([...PERFIS_ACESSO]);

  useEffect(() => {
    void colaboradoresService.listPerfisAcesso().then((lista) => {
      if (lista?.length) setPerfis(lista);
    });
  }, []);

  const emailTecnico = Boolean(colaborador.email_tecnico);

  const handleSubmit = async () => {
    if (ativo && !isSuperuser && !perfil) {
      setError('Usuário ativo precisa ter um perfil de acesso ou ser superusuário.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await colaboradoresService.editarAcesso(colaborador.id, {
        ativo,
        email,
        perfil: isSuperuser ? '' : perfil,
        is_staff: isStaff,
        ...(actorSuper ? { is_superuser: isSuperuser } : {}),
      });
      onSuccess();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <InlinePanel
      title="Editar acesso"
      onCancel={onClose}
      onSave={() => void handleSubmit()}
      saving={loading}
      saveLabel="Salvar acesso"
      error={error}
    >
      {error ? (
        <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 mb-4">
          {error}
        </p>
      ) : null}

      {emailTecnico ? (
        <p className="text-sm text-amber-900 dark:text-amber-100 rounded-md border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20 px-3 py-2 mb-4">
          Este e-mail é técnico/local. Para produção, informe um e-mail real.
        </p>
      ) : null}

      <div className="space-y-4">
        <WorkspaceField label="Login (somente leitura)">
          <input
            className="erp-input w-full bg-muted/40"
            value={colaborador.usuario_login || '—'}
            readOnly
          />
        </WorkspaceField>

        <WorkspaceField label="E-mail de acesso" required>
          <input
            className="erp-input w-full"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </WorkspaceField>

        {!isSuperuser ? (
          <WorkspaceField label="Perfil de acesso" required={ativo}>
            <select className="erp-select w-full" value={perfil} onChange={(e) => setPerfil(e.target.value)}>
              <option value="">— Selecione —</option>
              {perfis.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </WorkspaceField>
        ) : (
          <p className="text-xs text-muted-foreground">Superusuário não exige perfil/grupo.</p>
        )}

        <div className="flex items-center gap-2">
          <input
            id="acesso-ativo"
            type="checkbox"
            checked={ativo}
            onChange={(e) => setAtivo(e.target.checked)}
          />
          <label htmlFor="acesso-ativo">Usuário ativo</label>
        </div>

        <div className="flex items-center gap-2">
          <input
            id="acesso-staff"
            type="checkbox"
            checked={isStaff}
            onChange={(e) => setIsStaff(e.target.checked)}
          />
          <label htmlFor="acesso-staff">Staff</label>
        </div>

        {actorSuper ? (
          <div className="flex items-center gap-2">
            <input
              id="acesso-super"
              type="checkbox"
              checked={isSuperuser}
              onChange={(e) => setIsSuperuser(e.target.checked)}
            />
            <label htmlFor="acesso-super">Superusuário</label>
          </div>
        ) : null}

        {colaborador.email_tecnico ? (
          <p className="text-xs text-amber-800 dark:text-amber-200 rounded border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20 px-2 py-1.5">
            Este e-mail é técnico/local. Para produção, informe um e-mail real.
          </p>
        ) : null}
      </div>
    </InlinePanel>
  );
}