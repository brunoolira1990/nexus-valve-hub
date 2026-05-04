import { useState, useEffect } from 'react';
import { estoqueService } from '@/services/api/outros';
import type { EstoqueSaldoItem } from '@/types';

function fmt(v?: string | null): string {
  if (v == null) return '—';
  const asNumber = Number(v);
  if (Number.isNaN(asNumber)) return '—';
  return asNumber.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

const Estoque = () => {
  const [items, setItems] = useState<EstoqueSaldoItem[]>([]);
  const [busca, setBusca] = useState('');
  const [corrida, setCorrida] = useState('');
  const [tipoFisico, setTipoFisico] = useState('');
  const [somenteDimensionais, setSomenteDimensionais] = useState(false);
  const [somenteComSaldo, setSomenteComSaldo] = useState(true);
  const [somenteComAlertas, setSomenteComAlertas] = useState(false);

  useEffect(() => {
    const params: Record<string, string | boolean> = {
      com_saldo: somenteComSaldo,
      somente_dimensionais: somenteDimensionais,
      com_alertas: somenteComAlertas,
    };
    if (busca.trim()) {
      if (/[0-9]/.test(busca)) params.codigo = busca.trim();
      else params.descricao = busca.trim();
    }
    if (corrida.trim()) params.corrida = corrida.trim();
    if (tipoFisico.trim()) params.tipo_fisico = tipoFisico.trim();
    estoqueService.getSaldos(params).then(setItems);
  }, [busca, corrida, tipoFisico, somenteDimensionais, somenteComSaldo, somenteComAlertas]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-foreground mb-6">Consulta de Estoque</h1>
      <div className="erp-card p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="erp-label">Código / Descrição</label>
            <input className="erp-input mt-1" placeholder="Ex.: 6118 ou TUBO" value={busca} onChange={e => setBusca(e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Corrida</label>
            <input className="erp-input mt-1" placeholder="Ex.: ABC123" value={corrida} onChange={e => setCorrida(e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Tipo físico</label>
            <input className="erp-input mt-1" placeholder="Ex.: TUBO" value={tipoFisico} onChange={e => setTipoFisico(e.target.value)} />
          </div>
          <div className="flex flex-col justify-end gap-2">
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={somenteDimensionais} onChange={e => setSomenteDimensionais(e.target.checked)} />
              Somente produtos dimensionais
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={somenteComSaldo} onChange={e => setSomenteComSaldo(e.target.checked)} />
              Somente com saldo
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={somenteComAlertas} onChange={e => setSomenteComAlertas(e.target.checked)} />
              Somente com alertas
            </label>
          </div>
        </div>
      </div>
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Produto</th>
              <th>Corrida</th>
              <th>Saldo principal</th>
              <th>Equivalentes</th>
              <th>Alertas</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e, i) => (
              <tr key={`${e.produto_id}-${e.corrida || i}`}>
                <td className="font-mono">{e.codigo || '—'}</td>
                <td className="font-medium">{e.descricao}</td>
                <td className="font-mono">{e.corrida || '—'}</td>
                <td className="font-bold">Saldo: {fmt(e.saldo_principal)} {e.unidade_principal || 'UN'}</td>
                <td>
                  {e.usa_conversao_dimensional ? (
                    <span className="text-sm">
                      Equiv.: {fmt(e.metros)} M | {fmt(e.barras)} BR | {fmt(e.toneladas)} TON
                    </span>
                  ) : (
                    <span className="text-sm text-muted-foreground">—</span>
                  )}
                </td>
                <td className="max-w-[320px]">
                  {e.alertas?.length ? (
                    <ul className="flex flex-wrap gap-1">
                      {e.alertas.map((a, idx) => (
                        <li key={idx} className="erp-badge-warning text-xs">{a}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Estoque;
