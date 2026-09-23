import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import ColaboradorWorkspace from './ColaboradorWorkspace';
import { colaboradoresService } from '@/services/api/colaboradores';
import type { Colaborador } from '@/types';

export default function ColaboradorDetalhe() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [colaborador, setColaborador] = useState<Colaborador | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const isNovo = id === undefined || id === 'novo';

  useEffect(() => {
    if (isNovo) {
      setColaborador(null);
      setError(null);
      setLoading(false);
      return;
    }
    let active = true;
    if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) {
      setError('Identificador de colaborador inválido.');
      setLoading(false);
      return;
    }
    setLoading(true);
    colaboradoresService.getById(Number(id)).then(
      (colaboradorData) => {
        if (active) setColaborador(colaboradorData);
        setLoading(false);
      },
      () => {
        if (active) setError('Não foi possível carregar o colaborador.');
        setLoading(false);
      }
    );
    return () => { active = false; };
  }, [id, attempt, isNovo]);

  if (isNovo) {
    return (
      <ColaboradorWorkspace
        colaborador={null}
        onClose={() => navigate('/colaboradores')}
      />
    );
  }

  if (loading) return <p role="status">Carregando colaborador...</p>;

  if (error) return (
    <div className="space-y-4">
      <p role="alert">{error}</p>
      <button className="erp-btn-outline" onClick={() => setAttempt(n => n + 1)}>Tentar novamente</button>
      <Link to="/colaboradores" className="erp-btn-outline">Voltar para listagem</Link>
    </div>
  );

  return (
    <ColaboradorWorkspace
      colaborador={colaborador}
      onClose={() => navigate('/colaboradores')}
    />
  );
}