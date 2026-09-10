import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PedidosVendaWorkspace from './PedidosVendaWorkspace';
import { pedidosVendaService } from '@/services/api/comercial';
import type { PedidoVenda } from '@/types';

export default function PedidoVendaDetalhe() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [pedido, setPedido] = useState<PedidoVenda | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (id === undefined) {
      setPedido(null);
      setLoading(false);
      return;
    }
    let active = true;
    if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) {
      setError('Identificador de pedido inválido.');
      setLoading(false);
      return;
    }
    setLoading(true);
    pedidosVendaService.getById(Number(id)).then(
      (pedidoData) => {
        if (active) setPedido(pedidoData);
        setLoading(false);
      },
      () => {
        if (active) setError('Não foi possível carregar o pedido.');
        setLoading(false);
      }
    );
    return () => { active = false; };
  }, [id, attempt]);

  if (loading) return <p role="status">Carregando pedido...</p>;

  if (error) return (
    <div className="space-y-4">
      <p role="alert">{error}</p>
      <button className="erp-btn-outline" onClick={() => setAttempt(n => n + 1)}>Tentar novamente</button>
      <Link to="/pedidos-venda" className="erp-btn-outline">Voltar para listagem</Link>
    </div>
  );

  return (
    <PedidosVendaWorkspace
      pedido={pedido}
      onClose={() => navigate('/pedidos-venda')}
    />
  );
}