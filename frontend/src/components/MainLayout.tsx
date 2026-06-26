import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { PageContainer } from '@/components/nexus/PageContainer';

const DASHBOARD_MODULO_LABELS: Record<string, string> = {
  comercial: 'BI Comercial',
  fiscal: 'BI Fiscal',
  estoque: 'BI Estoque',
  expedicao: 'BI Expedição',
  compras: 'BI Compras',
  qualidade: 'BI Qualidade',
  financeiro: 'BI Financeiro',
};

const breadcrumbMap: Record<string, { label: string; path?: string }[]> = {
  '/dashboard': [{ label: 'Dashboard' }],
  '/empresas': [{ label: 'Cadastros' }, { label: 'Empresas' }],
  '/clientes': [{ label: 'Cadastros' }, { label: 'Clientes' }],
  '/fornecedores': [{ label: 'Cadastros' }, { label: 'Fornecedores' }],
  '/transportadoras': [{ label: 'Cadastros' }, { label: 'Transportadoras' }],
  '/colaboradores': [{ label: 'Cadastros' }, { label: 'Colaboradores' }],
  '/produtos': [{ label: 'Catálogo' }, { label: 'Produtos' }],
  '/corridas': [{ label: 'Catálogo' }, { label: 'Corridas / Lotes' }],
  '/regras-fiscais': [{ label: 'Fiscal' }, { label: 'Regras Fiscais' }],
  '/propostas': [{ label: 'Comercial' }, { label: 'Propostas' }],
  '/pedidos-venda': [{ label: 'Comercial' }, { label: 'Pedidos de Venda' }],
  '/modulos/crm': [{ label: 'CRM' }, { label: 'Visão geral' }],
  '/modulos/gestao-resultado': [{ label: 'Gestão de Resultado' }, { label: 'Visão geral' }],
  '/modulos/folha-rh': [{ label: 'Folha / RH' }, { label: 'Visão geral' }],
  '/pedidos-compra': [{ label: 'Compras' }, { label: 'Pedidos de Compra' }],
  '/nfe-entrada': [{ label: 'Compras' }, { label: 'NF-e de Entrada' }],
  '/nfe-entrada-historica-importada': [{ label: 'Compras' }, { label: 'NF-e Entrada (base)' }],
  '/nfe-saida': [{ label: 'Fiscal' }, { label: 'NF-e Saída' }],
  '/nfe-historica-importada': [{ label: 'Fiscal' }, { label: 'NF-e Saída (base)' }],
  '/cte-entrada': [{ label: 'Fiscal' }, { label: 'CT-e Entrada' }],
  '/cte-historico-importado': [{ label: 'Fiscal' }, { label: 'CT-e (base)' }],
  '/visao-gerencial-nfe-historica': [{ label: 'Fiscal' }, { label: 'Painel fiscal gerencial' }],
  '/central-dfe': [{ label: 'Fiscal' }, { label: 'DF-e Recebidos' }],
  '/nfe-sefaz': [{ label: 'Fiscal' }, { label: 'Status SEFAZ' }],
  '/certificados': [{ label: 'Qualidade' }, { label: 'Certificados de Qualidade' }],
  '/certificados-fornecedor': [{ label: 'Qualidade' }, { label: 'Certificados de Fornecedor' }],
  '/estoque': [{ label: 'Estoque & Logística' }, { label: 'Saldos' }],
  '/atendimentos-estoque': [{ label: 'Estoque & Logística' }, { label: 'Atendimentos Operacionais' }],
  '/expedicao': [{ label: 'Estoque & Logística' }, { label: 'Expedição' }],
  '/apuracao-fiscal': [{ label: 'Fiscal' }, { label: 'Apuração Fiscal' }],
  '/contabil': [{ label: 'Contábil' }],
  '/contador/exportar-xmls': [{ label: 'Contador' }, { label: 'Exportar XMLs' }],
  '/contador/sped': [{ label: 'Contador' }, { label: 'SPED' }],
  '/financeiro': [{ label: 'Financeiro' }, { label: 'Visão geral' }],
  '/financeiro/contas-receber': [{ label: 'Financeiro' }, { label: 'Contas a Receber' }],
  '/financeiro/contas-pagar': [{ label: 'Financeiro' }, { label: 'Contas a Pagar' }],
  '/financeiro/creditos': [{ label: 'Financeiro' }, { label: 'Créditos' }],
  '/financeiro/cadastros': [{ label: 'Financeiro' }, { label: 'Cadastros' }],
  '/financeiro/relatorios': [{ label: 'Financeiro' }, { label: 'Relatórios' }],
  '/financeiro/relatorios/contas-receber': [
    { label: 'Financeiro', path: '/financeiro' },
    { label: 'Relatórios', path: '/financeiro/relatorios' },
    { label: 'Contas a Receber' },
  ],
  '/financeiro/relatorios/contas-pagar': [
    { label: 'Financeiro', path: '/financeiro' },
    { label: 'Relatórios', path: '/financeiro/relatorios' },
    { label: 'Contas a Pagar' },
  ],
  '/financeiro/relatorios/fluxo-previsto': [
    { label: 'Financeiro', path: '/financeiro' },
    { label: 'Relatórios', path: '/financeiro/relatorios' },
    { label: 'Fluxo previsto' },
  ],
  '/financeiro/relatorios/categorias': [
    { label: 'Financeiro', path: '/financeiro' },
    { label: 'Relatórios', path: '/financeiro/relatorios' },
    { label: 'Por categoria' },
  ],
  '/financeiro/relatorios/clientes': [
    { label: 'Financeiro', path: '/financeiro' },
    { label: 'Relatórios', path: '/financeiro/relatorios' },
    { label: 'Por cliente' },
  ],
  '/financeiro/relatorios/fornecedores': [
    { label: 'Financeiro', path: '/financeiro' },
    { label: 'Relatórios', path: '/financeiro/relatorios' },
    { label: 'Por fornecedor' },
  ],
};

export const MainLayout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const isConferenciaEntrada = /^\/nfe-entrada\/[^/]+\/conferencia$/.test(location.pathname);
  const dashModuloMatch = location.pathname.match(/^\/dashboard\/([^/]+)$/);
  const basePath = '/' + location.pathname.split('/')[1];
  const breadcrumbs = isConferenciaEntrada
    ? [{ label: 'Compras' }, { label: 'NF-e Entrada (base)' }, { label: 'Conferência de Entrada' }]
    : dashModuloMatch
      ? [
          { label: 'Dashboard', path: '/dashboard' },
          { label: DASHBOARD_MODULO_LABELS[dashModuloMatch[1]] ?? dashModuloMatch[1] },
        ]
      : (breadcrumbMap[location.pathname] ?? breadcrumbMap[basePath] ?? [{ label: 'Página' }]);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header onToggleSidebar={() => setSidebarOpen(true)} breadcrumbs={breadcrumbs} />
        <main className="flex-1 overflow-auto px-4 py-5 lg:px-6 lg:py-6">
          <PageContainer>
            <Outlet />
          </PageContainer>
        </main>
      </div>
    </div>
  );
};
