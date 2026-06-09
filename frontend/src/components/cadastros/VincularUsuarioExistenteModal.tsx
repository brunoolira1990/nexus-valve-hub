import { useState } from 'react';
import { Modal } from '@/components/Modal';
import { UsuarioVinculoField } from '@/components/cadastros/UsuarioVinculoField';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import { PERFIS_ACESSO, perfilInicialSugerido } from '@/lib/colaboradorAcesso';
import type { Colaborador, Usuario } from '@/types';

type Props = {
  colaborador: Colaborador;
  onSuccess: () => void;
  onClose: () => void;
};

export function VincularUsuarioExistenteModal({ colaborador, onSuccess, onClose }: Props) {
  const [usuarioId, setUsuarioId] = useState<number | null>(null);
  const [selectedUsuario, setSelectedUsuario] = useState<Usuario | null>(null);
  const [perfil, setPerfil] = useState(perfilInicialSugerido(colaborador));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!usuarioId) {
      setError('Selecione um usuário.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await colaboradoresService.vincularUsuario(colaborador.id, {
        usuario_id: usuarioId,
        perfil,
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
    <Modal isOpen onClose={onClose} title="Vincular usuário existente" size="md">
      {error ? (
        <p className="mb-3 text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}
      <p className="text-sm text-muted-foreground mb-4">
        Colaborador: <strong>{colaborador.nome}</strong>
      </p>
      <div className="space-y-4">
        <div>
          <label className="erp-label">Usuário do sistema</label>
          <div className="mt-1">
            <UsuarioVinculoField
              valueId={usuarioId}
              selectedUsuario={selectedUsuario}
              onSelect={(u) => {
                setUsuarioId(u.id);
                setSelectedUsuario(u);
              }}
              onClear={() => {
                setUsuarioId(null);
                setSelectedUsuario(null);
              }}
            />
          </div>
        </div>
        <div>
          <label className="erp-label">Perfil de acesso *</label>
          <select className="erp-select mt-1 w-full" value={perfil} onChange={(e) => setPerfil(e.target.value)}>
            {PERFIS_ACESSO.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <p className="text-[10px] text-muted-foreground mt-1">
            Obrigatório se o usuário ainda não tiver grupo/perfil no sistema.
          </p>
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
        <button type="button" className="erp-btn-outline" onClick={onClose} disabled={loading}>
          Cancelar
        </button>
        <button type="button" className="erp-btn-primary" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? 'Vinculando…' : 'Vincular usuário'}
        </button>
      </div>
    </Modal>
  );
}
