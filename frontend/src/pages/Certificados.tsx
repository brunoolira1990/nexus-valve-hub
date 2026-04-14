import { FileText } from 'lucide-react';

const certificados = [
  { id: 1, nfe: 'NFS-001', cliente: 'Petrobrás S.A.', data: '2024-03-20', valor: 12500 },
  { id: 2, nfe: 'NFS-002', cliente: 'Vale S.A.', data: '2024-04-05', valor: 35000 },
];

const Certificados = () => (
  <div>
    <h1 className="text-2xl font-bold text-foreground mb-6">Certificados de Qualidade</h1>
    <div className="erp-card overflow-x-auto">
      <table className="erp-table">
        <thead><tr><th>NF-e Saída</th><th>Cliente</th><th>Data</th><th>Valor</th><th>Certificado</th></tr></thead>
        <tbody>
          {certificados.map(c => (
            <tr key={c.id}>
              <td className="font-medium">{c.nfe}</td><td>{c.cliente}</td><td>{c.data}</td>
              <td>R$ {c.valor.toFixed(2)}</td>
              <td><button className="erp-btn-outline erp-btn-sm" onClick={() => alert('PDF de certificado mock gerado!')}><FileText className="h-4 w-4 mr-1" /> Ver PDF</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

export default Certificados;
