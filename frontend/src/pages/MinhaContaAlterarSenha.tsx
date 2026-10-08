import { useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import { minhaContaService } from '@/services/api/minhaConta';
import { apiErrorMessage } from '@/services/api/config';

export default function MinhaContaAlterarSenha() {
  const [form, setForm] = useState({ senha_atual: '', nova_senha: '', confirmar_senha: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.senha_atual) {
      setError('Informe a senha atual.');
      return;
    }
    if (!form.nova_senha) {
      setError('Informe a nova senha.');
      return;
    }
    if (form.nova_senha !== form.confirmar_senha) {
      setError('Nova senha e confirmação não conferem.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await minhaContaService.alterarSenha(form);
      toast.success(res.mensagem || 'Senha alterada com sucesso.');
      setForm({ senha_atual: '', nova_senha: '', confirmar_senha: '' });
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="erp-page">
      <PageHeader
        title="Alterar senha"
        description="Minha conta — troque sua senha informando a senha atual."
        breadcrumbs={[
          { label: 'Início', path: '/dashboard' },
          { label: 'Minha conta' },
          { label: 'Alterar senha' },
        ]}
      />
      <form onSubmit={(e) => void handleSubmit(e)} className="max-w-md rounded-lg border border-border bg-card p-6 space-y-4">
        {error ? (
          <p className="text-sm text-destructive rounded border border-destructive/30 bg-destructive/10 px-3 py-2">{error}</p>
        ) : null}
        <div>
          <label className="erp-label">Senha atual *</label>
          <input
            type="password"
            autoComplete="current-password"
            className="erp-input mt-1 w-full"
            value={form.senha_atual}
            onChange={(e) => setForm((p) => ({ ...p, senha_atual: e.target.value }))}
          />
        </div>
        <div>
          <label className="erp-label">Nova senha *</label>
          <input
            type="password"
            autoComplete="new-password"
            className="erp-input mt-1 w-full"
            value={form.nova_senha}
            onChange={(e) => setForm((p) => ({ ...p, nova_senha: e.target.value }))}
          />
        </div>
        <div>
          <label className="erp-label">Confirmar nova senha *</label>
          <input
            type="password"
            autoComplete="new-password"
            className="erp-input mt-1 w-full"
            value={form.confirmar_senha}
            onChange={(e) => setForm((p) => ({ ...p, confirmar_senha: e.target.value }))}
          />
        </div>
        <div className="flex gap-2 pt-2">
          <button type="submit" className="erp-btn-primary" disabled={loading}>
            {loading ? 'Salvando…' : 'Alterar senha'}
          </button>
          <Link to="/dashboard" className="erp-btn-outline inline-flex items-center">
            Voltar
          </Link>
        </div>
      </form>
    </div>
  );
}
