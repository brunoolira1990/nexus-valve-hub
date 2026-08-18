import { useState } from 'react';
import { Modal } from '@/components/Modal';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import type { Colaborador } from '@/types';

type Props = {
  colaborador: Colaborador;
  onSuccess: () => void;
  onClose: () => void;
};

export function RedefinirSenhaColaboradorModal({ colaborador, onSuccess, onClose }: Props) {
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
    <Modal isOpen onClose={onClose} title="Redefinir senha" size="md">
      {error ? (
        <p className="mb-3 text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}
      <p className="text-sm text-muted-foreground mb-2">
        Usuário: <strong>{colaborador.usuario_login || colaborador.usuario_email}</strong>
      </p>
      <p className="text-xs text-muted-foreground mb-4">
        A senha atual não é exibida. Ao salvar, o usuário deverá acessar com a nova senha informada.
      </p>
      <div className="grid gap-4">
        <div>
          <label className="erp-label">Nova senha *</label>
          <input
            type="password"
            autoComplete="new-password"
            className="erp-input mt-1"
            value={novaSenha}
            onChange={(e) => setNovaSenha(e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">Confirmar nova senha *</label>
          <input
            type="password"
            autoComplete="new-password"
            className="erp-input mt-1"
            value={confirmar}
            onChange={(e) => setConfirmar(e.target.value)}
          />
        </div>
      </div>
      <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-6 pt-4 border-t border-border">
        <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={onClose} disabled={loading}>
          Cancelar
        </button>
        <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? 'Salvando…' : 'Redefinir senha'}
        </button>
      </div>
    </Modal>
  );
}
