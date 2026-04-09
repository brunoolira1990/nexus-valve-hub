import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      localStorage.setItem('nexus_token', 'mock-jwt-token-123');
      navigate('/dashboard');
    }, 500);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary text-primary-foreground font-bold text-2xl mb-4">NV</div>
          <h1 className="text-2xl font-bold text-foreground">Nexus Válvulas</h1>
          <p className="text-sm text-muted-foreground mt-1">Sistema de Gestão Empresarial</p>
        </div>
        <form onSubmit={handleLogin} className="erp-card p-6 space-y-4">
          <div>
            <label className="erp-label">E-mail</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@nexus.com" className="erp-input mt-1" required />
          </div>
          <div>
            <label className="erp-label">Senha</label>
            <input type="password" value={senha} onChange={e => setSenha(e.target.value)} placeholder="••••••••" className="erp-input mt-1" required />
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
