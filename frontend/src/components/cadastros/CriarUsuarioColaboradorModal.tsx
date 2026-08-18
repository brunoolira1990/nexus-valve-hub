import { useState } from 'react';
import { Modal } from '@/components/Modal';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import { PERFIS_ACESSO, perfilInicialSugerido } from '@/lib/colaboradorAcesso';
import { emailOperacionalValido } from '@/lib/validacaoSenha';
import type { Colaborador } from '@/types';

type Props = {
  colaborador: Colaborador;
  onSuccess: () => void;
  onClose: () => void;
};

export function CriarUsuarioColaboradorModal({ colaborador, onSuccess, onClose }: Props) {
  const sugestao = perfilInicialSugerido(colaborador);
  const [form, setForm] = useState({
    email: colaborador.email || '',
    nome: colaborador.nome || '',
    perfil: sugestao,
    ativo: true,
    senha: '',
    confirmar_senha: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!form.email.trim()) {
      setError('Informe o e-mail.');
      return;
    }
    if (!emailOperacionalValido(form.email)) {
      setError('Informe um e-mail válido.');
      return;
    }
    if (!form.nome.trim()) {
      setError('Informe o nome.');
      return;
    }
    if (!form.perfil) {
      setError('Selecione um perfil de acesso.');
      return;
    }
    if (!form.senha) {
      setError('Informe a senha.');
      return;
    }
    if (!form.confirmar_senha) {
      setError('Confirme a senha.');
      return;
    }
    if (form.senha !== form.confirmar_senha) {
      setError('As senhas informadas não conferem.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await colaboradoresService.criarUsuario(colaborador.id, {
        email: form.email.trim(),
        nome: form.nome.trim(),
        perfil: form.perfil,
        ativo: form.ativo,
        senha: form.senha,
        confirmar_senha: form.confirmar_senha,
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
    <Modal isOpen onClose={onClose} title="Criar usuário de acesso" size="md">
      {error ? (
        <p className="mb-3 text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}
      <p className="text-sm text-muted-foreground mb-2">
        Colaborador: <strong>{colaborador.nome}</strong>
      </p>
      <p className="text-xs text-muted-foreground mb-4">
        A senha será definida agora e não será exibida novamente após salvar.
      </p>
      {colaborador.perfil_sugerido_label ? (
        <p className="text-xs text-amber-800 dark:text-amber-200 mb-3 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5">
          Perfil sugerido com base nas funções internas: {colaborador.perfil_sugerido_label}
        </p>
      ) : null}
      <div className="grid gap-4">
        <div>
          <label className="erp-label">E-mail *</label>
          <input
            type="email"
            className="erp-input mt-1"
            value={form.email}
            onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
          />
        </div>
        <div>
          <label className="erp-label">Nome *</label>
          <input
            className="erp-input mt-1"
            value={form.nome}
            onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))}
          />
        </div>
        <div>
          <label className="erp-label">Perfil de acesso *</label>
          <select
            className="erp-select mt-1 w-full"
            value={form.perfil}
            onChange={(e) => setForm((p) => ({ ...p, perfil: e.target.value }))}
          >
            {PERFIS_ACESSO.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.ativo}
            onChange={(e) => setForm((p) => ({ ...p, ativo: e.target.checked }))}
          />
          Usuário ativo
        </label>
        <div>
          <label className="erp-label">Senha *</label>
          <input
            type="password"
            autoComplete="new-password"
            className="erp-input mt-1"
            value={form.senha}
            onChange={(e) => setForm((p) => ({ ...p, senha: e.target.value }))}
          />
        </div>
        <div>
          <label className="erp-label">Confirmar senha *</label>
          <input
            type="password"
            autoComplete="new-password"
            className="erp-input mt-1"
            value={form.confirmar_senha}
            onChange={(e) => setForm((p) => ({ ...p, confirmar_senha: e.target.value }))}
          />
        </div>
      </div>
      <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-6 pt-4 border-t border-border">
        <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={onClose} disabled={loading}>
          Cancelar
        </button>
        <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? 'Criando…' : 'Criar usuário'}
        </button>
      </div>
    </Modal>
  );
}
