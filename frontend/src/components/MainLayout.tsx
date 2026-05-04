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
  '/produtos': [{ label: 'Produtos' }, { label: 'Produtos' }],
  '/corridas': [{ label: 'Qualidade' }, { label: 'Corridas / Lotes Técnicos' }],
  '/regras-fiscais': [{ label: 'Fiscal' }, { label: 'Regras Fiscais' }],
  '/propostas': [{ label: 'Comercial' }, { label: 'Propostas' }],
  '/pedidos-venda': [{ label: 'Comercial' }, { label: 'Pedidos de Venda' }],
  '/pedidos-compra': [{ label: 'Compras' }, { label: 'Pedidos de Compra' }],
  '/nfe-entrada': [{ label: 'Compras' }, { label: 'NF-e de Entrada' }],
  '/nfe-entrada-historica-importada': [{ label: 'Compras' }, { label: 'NF-e Entrada Histórica/XML' }],
  '/nfe-saida': [{ label: 'Fiscal' }, { label: 'NF-e Saída' }],
  '/nfe-historica-importada': [{ label: 'Fiscal' }, { label: 'NF-e Saída Histórica/XML' }],
  '/cte-entrada': [{ label: 'Fiscal' }, { label: 'CT-e Entrada' }],
  '/cte-historico-importado': [{ label: 'Fiscal' }, { label: 'CT-e Histórico/XML' }],
  '/visao-gerencial-nfe-historica': [{ label: 'Fiscal' }, { label: 'Painel Fiscal/Gerencial' }],
  '/certificados': [{ label: 'Qualidade', }, { label: 'Certificados' }],
  '/certificados-fornecedor': [{ label: 'Qualidade' }, { label: 'Certificados de Fornecedor' }],
  '/estoque': [{ label: 'Estoque' }, { label: 'Saldos' }],
  '/apuracao-fiscal': [{ label: 'Apuração Fiscal' }],
  '/contabil': [{ label: 'Contábil' }],
};

export const MainLayout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const isConferenciaEntrada = /^\/nfe-entrada\/[^/]+\/conferencia$/.test(location.pathname);
  const basePath = '/' + location.pathname.split('/')[1];
  const breadcrumbs = isConferenciaEntrada
    ? [{ label: 'Compras' }, { label: 'NF-e Entrada Histórica/XML' }, { label: 'Conferência de Entrada' }]
    : (breadcrumbMap[basePath] || [{ label: 'Página' }]);

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
