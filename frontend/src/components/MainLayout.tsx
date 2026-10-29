import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { TopBar } from '@/components/layout/TopBar';
import { AppSwitcher } from '@/components/layout/AppSwitcher';
import { MobileTableEnhancer } from '@/components/nexus/MobileTableEnhancer';
import { PageContainer } from '@/components/nexus/PageContainer';
import { SIDEBAR_MENU_ITEMS } from '@/config/sidebarMenuConfig';
import { isRotaSelosNoConteudo, resolveSidebarModule } from '@/lib/sidebarNav';

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
  '/apps': [{ label: 'Aplicativos' }],
  '/dashboard': [{ label: 'Dashboard' }],
  '/empresas': [{ label: 'Cadastros' }, { label: 'Empresas' }],
  '/clientes': [{ label: 'Cadastros' }, { label: 'Clientes' }],
  '/fornecedores': [{ label: 'Cadastros' }, { label: 'Fornecedores' }],
  '/transportadoras': [{ label: 'Cadastros' }, { label: 'Transportadoras' }],
  '/colaboradores': [{ label: 'Cadastros' }, { label: 'Colaboradores' }],
  '/familias': [{ label: 'Cadastros' }, { label: 'Famílias' }],
  '/produtos': [{ label: 'Catálogo' }, { label: 'Produtos' }],
  '/corridas': [{ label: 'Catálogo' }, { label: 'Corridas / Lotes' }],
  '/regras-fiscais': [{ label: 'Fiscal' }, { label: 'Regras Fiscais' }],
  '/propostas': [{ label: 'Comercial' }, { label: 'Propostas' }],
  '/pedidos-venda': [{ label: 'Comercial' }, { label: 'Pedidos de Venda' }],
  '/modulos/crm': [{ label: 'CRM' }, { label: 'Visão geral' }],
  '/modulos/gestao-resultado': [{ label: 'Gestão de Resultado' }, { label: 'Visão geral' }],
  '/modulos/folha-rh': [{ label: 'Folha / RH' }, { label: 'Visão geral' }],
  '/pedidos-compra': [{ label: 'Compras' }, { label: 'Pedidos de Compra' }],
  '/nfe-entrada': [{ label: 'Compras' }, { label: 'Entrada Própria' }],
  '/cotacoes-fornecedores': [{ label: 'Compras' }, { label: 'Cotações com Fornecedores' }],
  '/nfe-entrada-historica-importada': [{ label: 'Fiscal' }, { label: 'NF-e Entrada (base)' }],
  '/nfe-saida': [{ label: 'Fiscal' }, { label: 'NF-e Saída' }],
  '/nfe-historica-importada': [{ label: 'Fiscal' }, { label: 'NF-e Saída (base)' }],
  '/cte-entrada': [{ label: 'Fiscal' }, { label: 'CT-e Entrada' }],
  '/cte-historico-importado': [{ label: 'Fiscal' }, { label: 'CT-e (base)' }],
  '/visao-gerencial-nfe-historica': [{ label: 'Fiscal' }, { label: 'Painel fiscal gerencial' }],
  '/central-dfe': [{ label: 'Fiscal' }, { label: 'Inbox Fiscal' }],
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
  '/financeiro/analises': [{ label: 'Financeiro' }, { label: 'Análises Financeiras' }],
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
  const [appSwitcherOpen, setAppSwitcherOpen] = useState(false);
  const location = useLocation();

  // Trocar de rota fecha drawer e grid de módulos, inclusive em navegação por teclado/redirect.
  useEffect(() => {
    setSidebarOpen(false);
    setAppSwitcherOpen(false);
  }, [location.pathname]);
  const isConferenciaEntrada = /^\/nfe-entrada\/[^/]+\/conferencia$/.test(location.pathname);
  const dashModuloMatch = location.pathname.match(/^\/dashboard\/([^/]+)$/);
  const basePath = '/' + location.pathname.split('/')[1];
  const breadcrumbs = isConferenciaEntrada
    ? [{ label: 'Fiscal' }, { label: 'NF-e Entrada (base)' }, { label: 'Conferência de Entrada' }]
    : dashModuloMatch
      ? [
          { label: 'Dashboard', path: '/dashboard' },
          { label: DASHBOARD_MODULO_LABELS[dashModuloMatch[1]] ?? dashModuloMatch[1] },
        ]
      : (breadcrumbMap[location.pathname] ?? breadcrumbMap[basePath] ?? [{ label: 'Página' }]);

  /** Sem submenu próprio (Dashboard, blocos isolados, rota desconhecida) a Sidebar não aparece. */
  const showMenuButton = resolveSidebarModule(location.pathname, SIDEBAR_MENU_ITEMS) !== null;
  /** No BI o selo de empresa/ambiente vive no topo do conteúdo, não no Header. */
  const selosNoConteudo = isRotaSelosNoConteudo(location.pathname);

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <TopBar onOpenAppSwitcher={() => setAppSwitcherOpen(true)} />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onOpenAppSwitcher={() => setAppSwitcherOpen(true)}
        />
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <MobileTableEnhancer />
          <Header
            onToggleSidebar={() => setSidebarOpen(true)}
            showMenuButton={showMenuButton}
            mostraSelos={!selosNoConteudo}
            breadcrumbs={breadcrumbs}
          />
          <main className="flex-1 min-w-0 overflow-auto bg-surface-muted px-3 py-4 sm:px-4 sm:py-5 lg:px-6 lg:py-6">
            <PageContainer>
              <Outlet />
            </PageContainer>
          </main>
        </div>
      </div>
      <AppSwitcher open={appSwitcherOpen} onClose={() => setAppSwitcherOpen(false)} />
    </div>
  );
};
