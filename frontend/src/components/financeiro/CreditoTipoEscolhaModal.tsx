import { Modal } from '@/components/Modal';
import { FINANCEIRO_ACTION_LABELS } from '@/lib/financeiroUi';

type Props = {
  open: boolean;
  onClose: () => void;
  onEscolher: (tipo: 'CLIENTE' | 'FORNECEDOR') => void;
};

export function CreditoTipoEscolhaModal({ open, onClose, onEscolher }: Props) {
  return (
    <Modal isOpen={open} onClose={onClose} title={FINANCEIRO_ACTION_LABELS.novoCredito} size="sm">
      <p className="text-sm text-muted-foreground mb-4">Tipo do crédito</p>
      <div className="flex flex-col gap-2">
        <button
          type="button"
          className="erp-btn-outline w-full justify-center"
          onClick={() => {
            onEscolher('CLIENTE');
            onClose();
          }}
        >
          Cliente
        </button>
        <button
          type="button"
          className="erp-btn-outline w-full justify-center"
          onClick={() => {
            onEscolher('FORNECEDOR');
            onClose();
          }}
        >
          Fornecedor
        </button>
      </div>
    </Modal>
  );
}
