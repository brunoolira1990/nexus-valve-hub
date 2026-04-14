import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

const breadcrumbMap: Record<string, { label: string; path?: string }[]> = {
  '/dashboard': [{ label: 'Dashboard' }],
  '/empresas': [{ label: 'Cadastros' }, { label: 'Empresas' }],
  '/clientes': [{ label: 'Cadastros' }, { label: 'Clientes' }],
  '/fornecedores': [{ label: 'Cadastros' }, { label: 'Fornecedores' }],
  '/transportadoras': [{ label: 'Cadastros' }, { label: 'Transportadoras' }],
  '/condicoes-pagamento': [{ label: 'Cadastros' }, { label: 'Condições de pagamento' }],
  '/produtos': [{ label: 'Produtos' }],
  '/corridas': [{ label: 'Corridas' }],
  '/regras-fiscais': [{ label: 'Regras Fiscais' }],
  '/propostas': [{ label: 'Comercial' }, { label: 'Propostas' }],
  '/pedidos-venda': [{ label: 'Comercial' }, { label: 'Pedidos de Venda' }],
  '/pedidos-compra': [{ label: 'Comercial' }, { label: 'Pedidos de Compra' }],
  '/nfe-entrada': [{ label: 'Fiscal' }, { label: 'NF-e Entrada' }],
  '/nfe-saida': [{ label: 'Fiscal' }, { label: 'NF-e Saída' }],
  '/cte-entrada': [{ label: 'Fiscal' }, { label: 'CT-e Entrada' }],
  '/certificados': [{ label: 'Qualidade', }, { label: 'Certificados' }],
  '/estoque': [{ label: 'Estoque' }],
  '/apuracao-fiscal': [{ label: 'Apuração Fiscal' }],
  '/contabil': [{ label: 'Contábil' }],
};

export const MainLayout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const basePath = '/' + location.pathname.split('/')[1];
  const breadcrumbs = breadcrumbMap[basePath] || [{ label: 'Página' }];

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header onToggleSidebar={() => setSidebarOpen(true)} breadcrumbs={breadcrumbs} />
        <main className="flex-1 overflow-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
