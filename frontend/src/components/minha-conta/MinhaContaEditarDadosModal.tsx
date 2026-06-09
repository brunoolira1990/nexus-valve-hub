import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Modal } from '@/components/Modal';
import { appContextoService } from '@/services/api/appContexto';
import { apiErrorMessage } from '@/services/api/config';

type Props = {
  open: boolean;
  onClose: () => void;
  email: string;
  telefone: string;
  onSaved: () => void;
};

export function MinhaContaEditarDadosModal({ open, onClose, email, telefone, onSaved }: Props) {
  const [form, setForm] = useState({ email, telefone });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setForm({ email, telefone });
      setError(null);
    }
  }, [open, email, telefone]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await appContextoService.patchMinhaConta({
        email: form.email.trim(),
        telefone: form.telefone.trim(),
      });
      toast.success(res.mensagem || 'Seus dados foram atualizados.');
      onSaved();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={open} onClose={onClose} title="Editar meus dados" size="sm">
      <form id="minha-conta-editar-form" onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Você pode atualizar e-mail e telefone. Nome, login, perfil e funções são administrados pelo Admin.
        </p>
        <div>
          <label htmlFor="mc-email" className="block text-sm font-medium mb-1">
            E-mail
          </label>
          <input
            id="mc-email"
            type="email"
            required
            className="erp-input w-full"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
          />
        </div>
        <div>
          <label htmlFor="mc-telefone" className="block text-sm font-medium mb-1">
            Telefone
          </label>
          <input
            id="mc-telefone"
            type="tel"
            className="erp-input w-full"
            value={form.telefone}
            onChange={(e) => setForm((f) => ({ ...f, telefone: e.target.value }))}
            placeholder="Opcional"
          />
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="erp-btn-secondary" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button type="submit" className="erp-btn-primary" disabled={loading}>
            {loading ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
