import { useState } from 'react';
import { Modal } from '@/components/Modal';
import { apuracaoService } from '@/services/api/outros';
import type { ApuracaoFiscal } from '@/types';

const ApuracaoFiscalPage = () => {
  const [mes, setMes] = useState(3);
  const [ano, setAno] = useState(2024);
  const [data, setData] = useState<ApuracaoFiscal | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [contadorValues, setContadorValues] = useState<Record<string, number>>({});

  const consultar = async () => {
    const d = await apuracaoService.get(mes, ano);
    setData(d);
  };

  const impostos = data ? [
    { label: 'IRPJ', valor: data.irpj },
    { label: 'CSLL', valor: data.csll },
    { label: 'PIS', valor: data.pis },
    { label: 'COFINS', valor: data.cofins },
    { label: 'ICMS', valor: data.icms },
    { label: 'IPI', valor: data.ipi },
    { label: 'CBS', valor: data.cbs },
    { label: 'IBS', valor: data.ibs },
  ] : [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-foreground mb-6">Apuração Fiscal</h1>
      <div className="erp-card p-4 mb-4">
        <div className="flex items-end gap-4">
          <div><label className="erp-label">Mês</label><select className="erp-select mt-1" value={mes} onChange={e => setMes(+e.target.value)}>{Array.from({length:12},(_,i) => <option key={i+1} value={i+1}>{i+1}</option>)}</select></div>
          <div><label className="erp-label">Ano</label><select className="erp-select mt-1" value={ano} onChange={e => setAno(+e.target.value)}><option>2024</option><option>2023</option></select></div>
          <button onClick={consultar} className="erp-btn-primary">Consultar</button>
          {data && <button onClick={() => setModalOpen(true)} className="erp-btn-outline">Comparar com Contador</button>}
        </div>
      </div>
      {data && (
        <div className="erp-card overflow-x-auto">
          <div className="p-4 border-b border-border">
            <span className="text-sm text-muted-foreground">Receita Bruta: </span>
            <span className="text-lg font-bold">R$ {data.receita_bruta.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
          </div>
          <table className="erp-table">
            <thead><tr><th>Imposto</th><th>Valor Calculado</th></tr></thead>
            <tbody>
              {impostos.map(i => (
                <tr key={i.label}><td className="font-medium">{i.label}</td><td>R$ {i.valor.toFixed(2)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Comparar com Contador" size="lg">
        <table className="erp-table">
          <thead><tr><th>Imposto</th><th>Sistema</th><th>Contador</th><th>Diferença</th></tr></thead>
          <tbody>
            {impostos.map(i => {
              const cv = contadorValues[i.label] ?? 0;
              const diff = i.valor - cv;
              return (
                <tr key={i.label}>
                  <td className="font-medium">{i.label}</td>
                  <td>R$ {i.valor.toFixed(2)}</td>
                  <td><input type="number" step="0.01" className="erp-input h-8 w-32" value={cv} onChange={e => setContadorValues(p => ({...p,[i.label]:+e.target.value}))} /></td>
                  <td className={diff !== 0 ? 'text-destructive font-bold' : 'text-success'}>{diff === 0 ? 'OK' : `R$ ${diff.toFixed(2)}`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="flex justify-end mt-4"><button onClick={() => setModalOpen(false)} className="erp-btn-primary">Fechar</button></div>
      </Modal>
    </div>
  );
};

export default ApuracaoFiscalPage;
