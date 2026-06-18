import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';

type Props = {
  open: boolean;
  loading?: boolean;
  onClose: () => void;
  onConfirm: (motivo: string) => void;
};

export function RecuperarPropostaModal({ open, loading, onClose, onConfirm }: Props) {
  const [motivo, setMotivo] = useState('');

  useEffect(() => {
    if (open) setMotivo('');
  }, [open]);

  return (
    <Modal open={open} onClose={onClose} title="Recuperar proposta cancelada/perdida">
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          A proposta será reaberta para negociação. O histórico de cancelamento/perda anterior será preservado.
          Informe o motivo da recuperação.
        </p>
        <div>
          <label className="erp-label">Motivo da recuperação *</label>
          <textarea
            className="erp-input mt-1 w-full min-h-[96px]"
            value={motivo}
            disabled={loading}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ex.: Cliente retomou negociação e aprovou parte da proposta"
          />
        </div>
        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <button type="button" className="erp-btn-outline" disabled={loading} onClick={onClose}>
            Cancelar
          </button>
          <button
            type="button"
            className="erp-btn-primary"
            disabled={loading || !motivo.trim()}
            onClick={() => onConfirm(motivo.trim())}
          >
            {loading ? 'Recuperando…' : 'Recuperar proposta'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
