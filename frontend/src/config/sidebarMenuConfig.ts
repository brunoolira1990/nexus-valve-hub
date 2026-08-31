import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  Bell,
  Building2,
  Package,
  ShoppingBag,
  Handshake,
  Receipt,
  ShieldCheck,
  Warehouse,
  BookOpen,
  Wallet,
  Users,
  TrendingUp,
  UserCircle,
  Calculator,
} from 'lucide-react';

export type SidebarLinkChild = {
  type: 'link';
  label: string;
  path: string;
  activeMatchPaths?: string[];
};

export type SidebarGroupChild = {
  type: 'group';
  label: string;
};

export type SidebarChild = SidebarLinkChild | SidebarGroupChild;

export type SidebarMenuItem = {
  label: string;
  path?: string;
  icon: LucideIcon;
  dashboardNav?: boolean;
  children?: SidebarChild[];
};

export const SIDEBAR_MENU_ITEMS: SidebarMenuItem[] = [
  { label: 'Dashboard', icon: LayoutDashboard, dashboardNav: true },
  { label: 'Notificações', path: '/notificacoes', icon: Bell },
  {
    label: 'Cadastros',
    icon: Building2,
    children: [
      { type: 'link', label: 'Empresas', path: '/empresas' },
      { type: 'link', label: 'Clientes', path: '/clientes' },
      { type: 'link', label: 'Fornecedores', path: '/fornecedores' },
      { type: 'link', label: 'Transportadoras', path: '/transportadoras' },
      { type: 'link', label: 'Colaboradores', path: '/colaboradores' },
    ],
  },
  {
    label: 'Catálogo',
    icon: Package,
    children: [
      { type: 'link', label: 'Produtos', path: '/produtos' },
      { type: 'link', label: 'Corridas / Lotes', path: '/corridas' },
    ],
  },
  {
    label: 'Compras',
    icon: ShoppingBag,
    children: [
      { type: 'link', label: 'Pedidos de Compra', path: '/pedidos-compra' },
      { type: 'link', label: 'Entrada Própria', path: '/nfe-entrada' },
      { type: 'link', label: 'Cotações com Fornecedores', path: '/cotacoes-fornecedores' },
    ],
  },
  {
    label: 'Comercial',
    icon: Handshake,
    children: [
      { type: 'link', label: 'Propostas', path: '/propostas' },
      { type: 'link', label: 'Pedidos de Venda', path: '/pedidos-venda' },
    ],
  },
  {
    label: 'CRM',
    icon: Users,
    children: [
      { type: 'link', label: 'Visão geral', path: '/crm' },
      { type: 'link', label: 'Leads', path: '/crm/leads' },
      { type: 'link', label: 'Oportunidades', path: '/crm/oportunidades' },
      { type: 'link', label: 'Atividades', path: '/crm/atividades' },
    ],
  },
  {
    label: 'Estoque & Logística',
    icon: Warehouse,
    children: [
      { type: 'link', label: 'Saldos', path: '/estoque' },
      { type: 'link', label: 'Kardex por produto/corrida', path: '/estoque/kardex', activeMatchPaths: ['/estoque/kardex'] },
      { type: 'link', label: 'Atendimentos Operacionais', path: '/atendimentos-estoque' },
      { type: 'link', label: 'Expedição', path: '/expedicao' },
    ],
  },
  {
    label: 'Fiscal',
    icon: Receipt,
    children: [
      { type: 'group', label: 'Operação' },
      { type: 'link', label: 'Inbox Fiscal', path: '/central-dfe' },
      { type: 'link', label: 'NF-e Saída', path: '/nfe-saida' },
      { type: 'link', label: 'Status SEFAZ', path: '/nfe-sefaz' },
      { type: 'group', label: 'Bases / Histórico' },
      { type: 'link', label: 'NF-e Entrada (base)', path: '/nfe-entrada-historica-importada' },
      { type: 'link', label: 'CT-e (base)', path: '/cte-historico-importado' },
      { type: 'link', label: 'CT-e Entrada', path: '/cte-entrada' },
      { type: 'link', label: 'NF-e Saída (base)', path: '/nfe-historica-importada' },
      { type: 'link', label: 'Painel fiscal gerencial', path: '/visao-gerencial-nfe-historica' },
      { type: 'group', label: 'Gestão' },
      { type: 'link', label: 'Apuração Fiscal', path: '/apuracao-fiscal' },
      { type: 'link', label: 'Regras Fiscais', path: '/regras-fiscais' },
    ],
  },
  {
    label: 'Qualidade',
    icon: ShieldCheck,
    children: [
      { type: 'link', label: 'Certificados de Qualidade', path: '/certificados' },
      { type: 'link', label: 'Certificados de Fornecedor', path: '/certificados-fornecedor' },
    ],
  },
  {
    label: 'Financeiro',
    icon: Wallet,
    children: [
      { type: 'link', label: 'Visão geral', path: '/financeiro' },
      { type: 'link', label: 'Contas a Receber', path: '/financeiro/contas-receber' },
      { type: 'link', label: 'Contas a Pagar', path: '/financeiro/contas-pagar' },
      { type: 'link', label: 'Créditos', path: '/financeiro/creditos' },
      { type: 'link', label: 'Análises Financeiras', path: '/financeiro/analises' },
      { type: 'link', label: 'Relatórios', path: '/financeiro/relatorios' },
      { type: 'link', label: 'Cadastros financeiros', path: '/financeiro/cadastros' },
    ],
  },
  {
    label: 'Gestão de Resultado',
    icon: TrendingUp,
    children: [{ type: 'link', label: 'Visão geral', path: '/modulos/gestao-resultado' }],
  },
  {
    label: 'Folha / RH',
    icon: UserCircle,
    children: [{ type: 'link', label: 'Visão geral', path: '/modulos/folha-rh' }],
  },
  { label: 'Contábil', path: '/contabil', icon: BookOpen },
  {
    label: 'Contador',
    icon: Calculator,
    children: [
      { type: 'link', label: 'Exportar XMLs', path: '/contador/exportar-xmls' },
      { type: 'link', label: 'SPED', path: '/contador/sped' },
    ],
  },
];
