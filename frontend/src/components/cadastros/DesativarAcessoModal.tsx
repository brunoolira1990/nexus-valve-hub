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

export function DesativarAcessoModal({ colaborador, onSuccess, onClose }: Props) {
  const [motivo, setMotivo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      await colaboradoresService.desativarAcesso(colaborador.id, motivo.trim() || undefined);
      onSuccess();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title="Desativar acesso?" size="sm">
      {error ? (
        <p className="mb-3 text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}
      <p className="text-sm text-muted-foreground mb-4">
        O usuário não poderá mais acessar o sistema, mas o cadastro do colaborador será mantido.
      </p>
      <div>
        <label className="erp-label">Motivo (opcional)</label>
        <input className="erp-input mt-1" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </div>
      <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-6 pt-4 border-t border-border">
        <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={onClose} disabled={loading}>
          Cancelar
        </button>
        <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? 'Desativando…' : 'Desativar acesso'}
        </button>
      </div>
    </Modal>
  );
}
