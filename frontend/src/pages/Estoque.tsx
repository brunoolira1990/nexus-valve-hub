import { useState, useEffect } from 'react';
import { estoqueService } from '@/services/api/outros';
import type { EstoqueItem } from '@/types';

const Estoque = () => {
  const [items, setItems] = useState<EstoqueItem[]>([]);
  const [filtro, setFiltro] = useState('');

  useEffect(() => { estoqueService.getAll().then(setItems); }, []);

  const filtered = items.filter(i => i.produto_nome.toLowerCase().includes(filtro.toLowerCase()) || i.corrida_numero.includes(filtro));

  return (
    <div>
      <h1 className="text-2xl font-bold text-foreground mb-6">Consulta de Estoque</h1>
      <div className="erp-card p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="erp-label">Filtrar por Produto / Corrida</label>
            <input className="erp-input mt-1" placeholder="Digite para filtrar..." value={filtro} onChange={e => setFiltro(e.target.value)} />
          </div>
        </div>
      </div>
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Produto</th><th>Corrida</th><th>Saldo Atual</th><th>Status</th></tr></thead>
          <tbody>
            {filtered.map((e, i) => (
              <tr key={i}>
                <td className="font-medium">{e.produto_nome}</td>
                <td className="font-mono">{e.corrida_numero}</td>
                <td className="font-bold">{e.saldo}</td>
                <td>{e.saldo <= 3 ? <span className="erp-badge-danger">Baixo</span> : e.saldo <= 10 ? <span className="erp-badge-warning">Atenção</span> : <span className="erp-badge-success">OK</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Estoque;
