import { useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Building2, Package, ShoppingBag, Handshake, Receipt, ShieldCheck, Warehouse, BookOpen,
  ChevronDown, ChevronRight, X, Wallet,
} from 'lucide-react';
import { useDashboardPermissoes } from '@/hooks/useDashboardPermissoes';
import { navItemsForPermissoes } from '@/components/bi/dashboardBiConfig';
import { isSidebarPathActive } from '@/lib/sidebarNav';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface MenuItem {
  label: string;
  path?: string;
  icon: React.ElementType;
  dashboardNav?: boolean;
  children?: { label: string; path: string; activeMatchPaths?: string[] }[];
}

const baseMenuItems: MenuItem[] = [
  { label: 'Dashboard', icon: LayoutDashboard, dashboardNav: true },
  { label: 'Cadastros', icon: Building2, children: [
    { label: 'Empresas', path: '/empresas' },
    { label: 'Clientes', path: '/clientes' },
    { label: 'Fornecedores', path: '/fornecedores' },
    { label: 'Transportadoras', path: '/transportadoras' },
    { label: 'Colaboradores', path: '/colaboradores' },
  ]},
  { label: 'Produtos', icon: Package, children: [
    { label: 'Produtos', path: '/produtos' },
  ]},
  { label: 'Compras', icon: ShoppingBag, children: [
    { label: 'Pedidos de Compra', path: '/pedidos-compra' },
    { label: 'NF-e de Entrada', path: '/nfe-entrada', activeMatchPaths: ['/nfe-entrada/:id/conferencia'] },
    { label: 'Base NF-e Entrada Importada', path: '/nfe-entrada-historica-importada' },
  ]},
  { label: 'Comercial', icon: Handshake, children: [
    { label: 'Propostas', path: '/propostas' },
    { label: 'Pedidos de Venda', path: '/pedidos-venda' },
  ]},
  { label: 'Fiscal', icon: Receipt, children: [
    { label: 'DF-e Recebidos', path: '/central-dfe' },
    { label: 'NF-e Saída', path: '/nfe-saida' },
    { label: 'SEFAZ — Status serviço', path: '/nfe-sefaz' },
    { label: 'Base NF-e Saída Importada', path: '/nfe-historica-importada' },
    { label: 'Painel fiscal/gerencial consolidado', path: '/visao-gerencial-nfe-historica' },
    { label: 'Apuração Fiscal', path: '/apuracao-fiscal' },
    { label: 'CT-e Entrada', path: '/cte-entrada' },
    { label: 'Base CT-e Importada', path: '/cte-historico-importado' },
    { label: 'Regras Fiscais', path: '/regras-fiscais' },
  ]},
  { label: 'Estoque', icon: Warehouse, children: [
    { label: 'Saldos', path: '/estoque' },
    { label: 'Atendimentos Operacionais', path: '/atendimentos-estoque' },
    { label: 'Expedição / Logística', path: '/expedicao' },
  ]},
  { label: 'Qualidade', icon: ShieldCheck, children: [
    { label: 'Certificados de Qualidade', path: '/certificados' },
    { label: 'Certificados de Fornecedor', path: '/certificados-fornecedor' },
    { label: 'Corridas / Lotes Técnicos', path: '/corridas' },
  ]},
  { label: 'Financeiro', icon: Wallet, children: [
    { label: 'Visão geral', path: '/financeiro' },
    { label: 'Contas a Receber', path: '/financeiro/contas-receber' },
    { label: 'Contas a Pagar', path: '/financeiro/contas-pagar' },
    { label: 'Créditos', path: '/financeiro/creditos' },
    { label: 'Relatórios', path: '/financeiro/relatorios' },
    { label: 'Cadastros', path: '/financeiro/cadastros' },
  ]},
  { label: 'Contábil', path: '/contabil', icon: BookOpen },
];

export const Sidebar = ({ isOpen, onClose }: SidebarProps) => {
  const location = useLocation();
  const { permissoes } = useDashboardPermissoes();
  const [expanded, setExpanded] = useState<string[]>(['Dashboard', 'Cadastros', 'Produtos', 'Compras', 'Comercial', 'Fiscal', 'Estoque', 'Qualidade', 'Financeiro']);

  const dashboardChildren = useMemo(
    () => navItemsForPermissoes(permissoes).map((item) => ({ label: item.label, path: item.path })),
    [permissoes],
  );

  const toggleExpand = (label: string) => {
    setExpanded((prev) => (prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]));
  };

  const isActive = (path?: string, activeMatchPaths?: string[]) =>
    isSidebarPathActive(location.pathname, path, activeMatchPaths);

  const dashboardSectionActive = location.pathname.startsWith('/dashboard');

  return (
    <>
      {isOpen ? (
        <div className="fixed inset-0 bg-foreground/30 z-40 lg:hidden" onClick={onClose} />
      ) : null}
      <aside className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-sidebar-bg text-sidebar-fg flex flex-col transition-transform duration-200 ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="h-14 flex items-center justify-between px-4 border-b border-sidebar-hover">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-sidebar-active flex items-center justify-center text-primary-foreground font-bold text-sm">NV</div>
            <span className="font-semibold text-sm">NEXUS APP</span>
          </Link>
          <button type="button" onClick={onClose} className="lg:hidden text-sidebar-muted hover:text-sidebar-fg">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {baseMenuItems.map((item) => (
            <div key={item.label}>
              {item.dashboardNav ? (
                <>
                  <button
                    type="button"
                    onClick={() => toggleExpand(item.label)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-150 ${
                      dashboardSectionActive
                        ? 'bg-sidebar-active text-primary-foreground font-medium shadow-sm'
                        : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                    }`}
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {expanded.includes(item.label) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  </button>
                  {expanded.includes(item.label) ? (
                    <div className="ml-3 pl-3 border-l border-sidebar-hover/80 mb-1 space-y-0.5">
                      {dashboardChildren.map((child) => (
                        <Link
                          key={child.path}
                          to={child.path}
                          onClick={onClose}
                          className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors duration-150 ${
                            isActive(child.path)
                              ? 'bg-sidebar-active text-primary-foreground font-medium shadow-sm'
                              : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                          }`}
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : item.children ? (
                <>
                  <button
                    type="button"
                    onClick={() => toggleExpand(item.label)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg transition-colors duration-150"
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {expanded.includes(item.label) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  </button>
                  {expanded.includes(item.label) ? (
                    <div className="ml-3 pl-3 border-l border-sidebar-hover/80 space-y-0.5">
                      {item.children.map((child) => (
                        <Link
                          key={`${item.label}-${child.label}`}
                          to={child.path}
                          onClick={onClose}
                          className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors duration-150 ${
                            isActive(child.path, child.activeMatchPaths)
                              ? 'bg-sidebar-active text-primary-foreground font-medium shadow-sm'
                              : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                          }`}
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <Link
                  to={item.path!}
                  onClick={onClose}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-150 ${
                    isActive(item.path) ? 'bg-sidebar-active text-primary-foreground font-medium shadow-sm' : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                  }`}
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
