import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiErrorMessage } from '@/services/api/config';
import { login, persistTokens } from '@/services/api/auth';
import { clearAppContextoCache } from '@/hooks/useAppContexto';

const Login = () => {
  const [username, setUsername] = useState('');
  const [senha, setSenha] = useState('');
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro(null);
    setLoading(true);
    try {
      const tokens = await login(username.trim(), senha);
      persistTokens(tokens);
      clearAppContextoCache();
      navigate('/dashboard');
    } catch (err) {
      setErro(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary text-primary-foreground font-bold text-2xl mb-4">NV</div>
          <h1 className="text-2xl font-bold text-foreground">NEXUS APP</h1>
          <p className="text-sm text-muted-foreground mt-1">Sistema de Gestão Empresarial</p>
        </div>
        <form onSubmit={handleLogin} className="erp-card p-6 space-y-4">
          {erro && (
            <div className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
              {erro}
            </div>
          )}
          <div>
            <label className="erp-label">Usuário</label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="mesmo usuário do Django (ex.: admin)"
              className="erp-input mt-1"
              required
            />
          </div>
          <div>
            <label className="erp-label">Senha</label>
            <input
              type="password"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="••••••••"
              className="erp-input mt-1"
              required
            />
          </div>
          <button type="submit" disabled={loading} className="erp-btn-primary w-full">
            {loading ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
