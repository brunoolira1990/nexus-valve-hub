import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Building2, Users, Truck, Package, Layers, FileText,
  ShoppingCart, Receipt, ShieldCheck, Warehouse, Calculator, BookOpen,
  ChevronDown, ChevronRight, X
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface MenuItem {
  label: string;
  path?: string;
  icon: React.ElementType;
  children?: { label: string; path: string }[];
}

const menuItems: MenuItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Cadastros', icon: Building2, children: [
    { label: 'Empresas', path: '/empresas' },
    { label: 'Clientes', path: '/clientes' },
    { label: 'Fornecedores', path: '/fornecedores' },
    { label: 'Transportadoras', path: '/transportadoras' },
  ]},
  { label: 'Produtos', path: '/produtos', icon: Package },
  { label: 'Corridas', path: '/corridas', icon: Layers },
  { label: 'Regras Fiscais', path: '/regras-fiscais', icon: FileText },
  { label: 'Comercial', icon: ShoppingCart, children: [
    { label: 'Propostas', path: '/propostas' },
    { label: 'Pedidos de Venda', path: '/pedidos-venda' },
    { label: 'Pedidos de Compra', path: '/pedidos-compra' },
  ]},
  { label: 'Fiscal', icon: Receipt, children: [
    { label: 'NF-e Entrada', path: '/nfe-entrada' },
    { label: 'NF-e Saída', path: '/nfe-saida' },
    { label: 'CT-e Entrada', path: '/cte-entrada' },
  ]},
  { label: 'Qualidade', path: '/certificados', icon: ShieldCheck },
  { label: 'Estoque', path: '/estoque', icon: Warehouse },
  { label: 'Apuração Fiscal', path: '/apuracao-fiscal', icon: Calculator },
  { label: 'Contábil', path: '/contabil', icon: BookOpen },
];

export const Sidebar = ({ isOpen, onClose }: SidebarProps) => {
  const location = useLocation();
  const [expanded, setExpanded] = useState<string[]>(['Cadastros', 'Comercial', 'Fiscal']);

  const toggleExpand = (label: string) => {
    setExpanded(prev => prev.includes(label) ? prev.filter(l => l !== label) : [...prev, label]);
  };

  const isActive = (path?: string) => path && location.pathname.startsWith(path);

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-foreground/30 z-40 lg:hidden" onClick={onClose} />
      )}
      <aside className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-sidebar-bg text-sidebar-fg flex flex-col transition-transform duration-200 ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="h-14 flex items-center justify-between px-4 border-b border-sidebar-hover">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-sidebar-active flex items-center justify-center text-primary-foreground font-bold text-sm">NV</div>
            <span className="font-semibold text-sm">Nexus Válvulas</span>
          </Link>
          <button onClick={onClose} className="lg:hidden text-sidebar-muted hover:text-sidebar-fg">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-2 px-2">
          {menuItems.map(item => (
            <div key={item.label}>
              {item.children ? (
                <>
                  <button
                    onClick={() => toggleExpand(item.label)}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg transition-colors"
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {expanded.includes(item.label) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  </button>
                  {expanded.includes(item.label) && (
                    <div className="ml-4 pl-3 border-l border-sidebar-hover">
                      {item.children.map(child => (
                        <Link
                          key={child.path}
                          to={child.path}
                          onClick={onClose}
                          className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${isActive(child.path) ? 'bg-sidebar-active text-primary-foreground font-medium' : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'}`}
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <Link
                  to={item.path!}
                  onClick={onClose}
                  className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${isActive(item.path) ? 'bg-sidebar-active text-primary-foreground font-medium' : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'}`}
                >
                  <item.icon className="h-4 w-4 shrink-0" />
                  <span>{item.label}</span>
                </Link>
              )}
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
};
