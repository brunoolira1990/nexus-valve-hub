import { useState } from 'react';
import { InlinePanel } from '@/components/workspace/InlinePanel';
import { WorkspaceField } from '@/components/workspace/WorkspaceField';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import type { Colaborador } from '@/types';

type Props = {
  colaborador: Colaborador;
  onSuccess: () => void;
  onClose: () => void;
};

export function RedefinirSenhaColaboradorPanel({ colaborador, onSuccess, onClose }: Props) {
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!novaSenha) {
      setError('Informe a nova senha.');
      return;
    }
    if (!confirmar) {
      setError('Confirme a nova senha.');
      return;
    }
    if (novaSenha !== confirmar) {
      setError('As senhas informadas não conferem.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await colaboradoresService.redefinirSenha(colaborador.id, {
        nova_senha: novaSenha,
        confirmar_senha: confirmar,
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
      title="Redefinir senha"
      onCancel={onClose}
      onSave={() => void handleSubmit()}
      saving={loading}
      saveLabel="Redefinir senha"
      error={error}
    >
      {error ? (
        <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 mb-4">
          {error}
        </p>
      ) : null}

      <p className="text-sm text-muted-foreground mb-2">
        Usuário: <strong>{colaborador.usuario_login || colaborador.usuario_email}</strong>
      </p>
      <p className="text-xs text-muted-foreground mb-4">
        A senha atual não é exibida. Ao salvar, o usuário deverá acessar com a nova senha informada.
      </p>

      <div className="space-y-4">
        <WorkspaceField label="Nova senha *">
          <input
            type="password"
            autoComplete="new-password"
            className="erp-input mt-1 w-full"
            value={novaSenha}
            onChange={(e) => setNovaSenha(e.target.value)}
          />
        </WorkspaceField>

        <WorkspaceField label="Confirmar nova senha *">
          <input
            type="password"
            autoComplete="new-password"
            className="erp-input mt-1 w-full"
            value={confirmar}
            onChange={(e) => setConfirmar(e.target.value)}
          />
        </WorkspaceField>
      </div>
    </InlinePanel>
  );
}