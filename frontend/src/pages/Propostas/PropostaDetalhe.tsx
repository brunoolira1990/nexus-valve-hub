import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Propostas from '../Propostas';
import { propostasService } from '@/services/api/comercial';
import type { Proposta } from '@/types';

export default function PropostaDetalhe() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<{ id: string; proposta?: Proposta; error?: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (id === undefined) return;
    let active = true;
    if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) {
      setResult({ id, error: 'Identificador de proposta inválido.' });
      return;
    }
    setResult(null);
    propostasService.getById(Number(id)).then(
      proposta => { if (active) setResult({ id, proposta }); },
      () => { if (active) setResult({ id, error: 'Não foi possível carregar a proposta.' }); },
    );
    return () => { active = false; };
  }, [id, attempt]);
  if (id === undefined) return <Propostas key="nova" dedicated />;
  if (!result || result.id !== id) return <p role="status">Carregando proposta...</p>;
  if (result.error) return (
    <div className="space-y-4">
      <p role="alert">{result.error}</p>
      <button className="erp-btn-outline" onClick={() => setAttempt(n => n + 1)}>Tentar novamente</button>
      <Link to="/propostas" className="erp-btn-outline">Voltar para listagem</Link>
    </div>
  );
  return <Propostas key={id} dedicated proposta={result.proposta} />;
}
