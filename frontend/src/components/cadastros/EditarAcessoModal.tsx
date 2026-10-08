import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
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

export function EditarAcessoModal({ colaborador, onSuccess, onClose }: Props) {
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
    <Modal isOpen onClose={onClose} title="Editar acesso" size="md">
      {error ? (
        <p className="mb-3 text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}

      {emailTecnico ? (
        <p className="mb-3 text-sm text-amber-900 dark:text-amber-100 rounded-md border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20 px-3 py-2">
          Este e-mail é técnico/local. Para produção, informe um e-mail real.
        </p>
      ) : null}

      <div className="space-y-3 text-sm">
        <div>
          <label className="erp-label">Login (somente leitura)</label>
          <input className="erp-input mt-1 w-full bg-muted/40" value={colaborador.usuario_login || '—'} readOnly />
        </div>
        <div>
          <label className="erp-label">E-mail de acesso *</label>
          <input
            className="erp-input mt-1 w-full"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <input id="acesso-ativo" type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
          <label htmlFor="acesso-ativo">Usuário ativo</label>
        </div>
        {!isSuperuser ? (
          <div>
            <label className="erp-label">Perfil de acesso {ativo ? '*' : ''}</label>
            <select className="erp-select mt-1 w-full" value={perfil} onChange={(e) => setPerfil(e.target.value)}>
              <option value="">— Selecione —</option>
              {perfis.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Superusuário não exige perfil/grupo.</p>
        )}
        <div className="flex items-center gap-2">
          <input id="acesso-staff" type="checkbox" checked={isStaff} onChange={(e) => setIsStaff(e.target.checked)} />
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
      </div>

      <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-6 pt-4 border-t border-border">
        <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={onClose} disabled={loading}>
          Cancelar
        </button>
        <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? 'Salvando…' : 'Salvar acesso'}
        </button>
      </div>
    </Modal>
  );
}
