import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import PedidosVenda from './PedidosVenda';
import { pedidosVendaService } from '@/services/api/comercial';
import type { PedidoVenda } from '@/types';

export default function PedidoVendaDetalhe() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<{ id: string; pedido?: PedidoVenda; error?: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (id === undefined) return;
    let active = true;
    if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) {
      setResult({ id, error: 'Identificador de pedido inválido.' });
      return;
    }
    setResult(null);
    pedidosVendaService.getById(Number(id)).then(
      pedido => { if (active) setResult({ id, pedido }); },
      () => { if (active) setResult({ id, error: 'Não foi possível carregar o pedido.' }); },
    );
    return () => { active = false; };
  }, [id, attempt]);
  if (id === undefined) return <PedidosVenda key="nova" dedicated />;
  if (!result || result.id !== id) return <p role="status">Carregando pedido...</p>;
  if (result.error) return (
    <div className="space-y-4">
      <p role="alert">{result.error}</p>
      <button className="erp-btn-outline" onClick={() => setAttempt(n => n + 1)}>Tentar novamente</button>
      <Link to="/pedidos-venda" className="erp-btn-outline">Voltar para listagem</Link>
    </div>
  );
  return <PedidosVenda key={id} dedicated pedido={result.pedido} />;
}