import { DollarSign, Package, AlertTriangle, FileText, TrendingUp, ShoppingCart } from 'lucide-react';

const cards = [
  { label: 'Faturamento do Mês', value: 'R$ 125.000,00', icon: DollarSign, color: 'text-emerald-600 bg-emerald-50' },
  { label: 'Pedidos a Faturar', value: '8', icon: FileText, color: 'text-blue-600 bg-blue-50' },
  { label: 'Estoque Baixo', value: '3 itens', icon: AlertTriangle, color: 'text-amber-600 bg-amber-50' },
  { label: 'Propostas Pendentes', value: '5', icon: ShoppingCart, color: 'text-violet-600 bg-violet-50' },
  { label: 'NF-e Emitidas', value: '42', icon: TrendingUp, color: 'text-emerald-600 bg-emerald-50' },
  { label: 'Produtos Cadastrados', value: '156', icon: Package, color: 'text-blue-600 bg-blue-50' },
];

const Dashboard = () => (
  <div>
    <h1 className="text-2xl font-bold text-foreground mb-6">Dashboard</h1>
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
      {cards.map(c => (
        <div key={c.label} className="erp-card p-5 flex items-center gap-4">
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${c.color}`}>
            <c.icon className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">{c.label}</p>
            <p className="text-xl font-bold text-foreground">{c.value}</p>
          </div>
        </div>
      ))}
    </div>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="erp-card p-5">
        <h3 className="font-semibold mb-3">Últimos Pedidos de Venda</h3>
        <table className="erp-table">
          <thead><tr><th>Número</th><th>Cliente</th><th>Valor</th><th>Status</th></tr></thead>
          <tbody>
            <tr><td>PV-001</td><td>Petrobrás S.A.</td><td>R$ 12.500,00</td><td><span className="erp-badge-success">Faturado</span></td></tr>
            <tr><td>PV-002</td><td>Vale S.A.</td><td>R$ 35.000,00</td><td><span className="erp-badge-warning">Pendente</span></td></tr>
            <tr><td>PV-003</td><td>CSN</td><td>R$ 8.200,00</td><td><span className="erp-badge-info">Em separação</span></td></tr>
          </tbody>
        </table>
      </div>
      <div className="erp-card p-5">
        <h3 className="font-semibold mb-3">Alertas de Estoque</h3>
        <table className="erp-table">
          <thead><tr><th>Produto</th><th>Estoque</th><th>Mínimo</th></tr></thead>
          <tbody>
            <tr><td>Conexão WeldoFit 3"x2"</td><td className="text-destructive font-medium">2</td><td>10</td></tr>
            <tr><td>Válvula Esfera 4" Inox</td><td className="text-amber-600 font-medium">8</td><td>5</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
);

export default Dashboard;
