import { useState } from 'react';
import { Modal } from '@/components/Modal';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import { PERFIS_ACESSO, perfilInicialSugerido } from '@/lib/colaboradorAcesso';
import type { Colaborador } from '@/types';

type Props = {
  colaborador: Colaborador;
  onSuccess: () => void;
  onClose: () => void;
};

export function DefinirPerfilAcessoModal({ colaborador, onSuccess, onClose }: Props) {
  const [perfil, setPerfil] = useState(perfilInicialSugerido(colaborador));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!perfil) {
      setError('Selecione um perfil de acesso.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await colaboradoresService.definirPerfil(colaborador.id, perfil);
      onSuccess();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title="Definir perfil de acesso" size="sm">
      {error ? (
        <p className="mb-3 text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}
      <p className="text-sm text-muted-foreground mb-4">
        Usuário <strong>{colaborador.usuario_login}</strong> está ativo sem perfil/grupo.
      </p>
      <div>
        <label className="erp-label">Perfil de acesso *</label>
        <select className="erp-select mt-1 w-full" value={perfil} onChange={(e) => setPerfil(e.target.value)}>
          {PERFIS_ACESSO.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-6 pt-4 border-t border-border">
        <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={onClose} disabled={loading}>
          Cancelar
        </button>
        <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? 'Salvando…' : 'Definir perfil'}
        </button>
      </div>
    </Modal>
  );
}
