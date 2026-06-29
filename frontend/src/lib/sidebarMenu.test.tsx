import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { SIDEBAR_MENU_ITEMS } from '@/config/sidebarMenuConfig';
import { Sidebar } from '@/components/Sidebar';
import { resolveActiveSidebarSection, isSidebarPathActive } from '@/lib/sidebarNav';

vi.mock('@/hooks/useDashboardPermissoes', () => ({
  useDashboardPermissoes: () => ({
    permissoes: {
      pode_ver_comercial: true,
      pode_ver_fiscal: true,
      pode_ver_estoque: true,
      pode_ver_expedicao: true,
      pode_ver_compras: true,
      pode_ver_qualidade: true,
      pode_ver_financeiro: true,
      pode_ver_consolidado: false,
    },
  }),
}));

describe('sidebarMenuConfig — estrutura reorganizada', () => {
  it('contém seções principais confirmadas', () => {
    const labels = SIDEBAR_MENU_ITEMS.map((i) => i.label);
    expect(labels).toEqual([
      'Dashboard',
      'Cadastros',
      'Catálogo',
      'Compras',
      'Comercial',
      'CRM',
      'Estoque & Logística',
      'Fiscal',
      'Qualidade',
      'Financeiro',
      'Gestão de Resultado',
      'Folha / RH',
      'Contábil',
      'Contador',
    ]);
  });

  it('Corridas está em Catálogo', () => {
    const catalogo = SIDEBAR_MENU_ITEMS.find((i) => i.label === 'Catálogo');
    const paths = catalogo?.children?.filter((c) => c.type === 'link').map((c) => c.path);
    expect(paths).toContain('/corridas');
  });

  it('CT-e base está em Fiscal', () => {
    const fiscal = SIDEBAR_MENU_ITEMS.find((i) => i.label === 'Fiscal');
    const paths = fiscal?.children?.filter((c) => c.type === 'link').map((c) => c.path);
    expect(paths).toContain('/cte-historico-importado');
  });

  it('Fiscal possui subgrupos visuais', () => {
    const fiscal = SIDEBAR_MENU_ITEMS.find((i) => i.label === 'Fiscal');
    const groups = fiscal?.children?.filter((c) => c.type === 'group').map((c) => c.label);
    expect(groups).toEqual(['Operação', 'Bases / Histórico', 'Gestão']);
  });

  it('menu Compras exibe Entrada Própria sem bases importadas', () => {
    const compras = SIDEBAR_MENU_ITEMS.find((i) => i.label === 'Compras');
    const labels = compras?.children?.filter((c) => c.type === 'link').map((c) => c.label);
    expect(labels).toEqual(['Pedidos de Compra', 'Entrada Própria']);
    expect(labels).not.toContain('NF-e Entrada (base)');
  });

  it('Inbox Fiscal é o caminho principal em Fiscal > Operação', () => {
    const fiscal = SIDEBAR_MENU_ITEMS.find((i) => i.label === 'Fiscal');
    const children = fiscal?.children ?? [];
    const basesIdx = children.findIndex((c) => c.type === 'group' && c.label === 'Bases / Histórico');
    const operacaoLinks = children
      .slice(1, basesIdx)
      .filter((c) => c.type === 'link')
      .map((c) => (c.type === 'link' ? c.label : ''));
    expect(operacaoLinks).toEqual(['Inbox Fiscal', 'NF-e Saída', 'Status SEFAZ']);
  });

  it('bases de recebimento ficam em Fiscal > Bases / Histórico', () => {
    const fiscal = SIDEBAR_MENU_ITEMS.find((i) => i.label === 'Fiscal');
    const children = fiscal?.children ?? [];
    const basesIdx = children.findIndex((c) => c.type === 'group' && c.label === 'Bases / Histórico');
    const gestaoIdx = children.findIndex((c) => c.type === 'group' && c.label === 'Gestão');
    const basePaths = children
      .slice(basesIdx + 1, gestaoIdx)
      .filter((c) => c.type === 'link')
      .map((c) => (c.type === 'link' ? c.path : ''));
    expect(basePaths).toEqual([
      '/nfe-entrada-historica-importada',
      '/cte-historico-importado',
      '/cte-entrada',
      '/nfe-historica-importada',
      '/visao-gerencial-nfe-historica',
    ]);
  });
});

describe('sidebarNav — seção ativa', () => {
  it('resolve Catálogo para /corridas', () => {
    expect(resolveActiveSidebarSection('/corridas', SIDEBAR_MENU_ITEMS)).toBe('Catálogo');
  });

  it('resolve Estoque & Logística para /expedicao', () => {
    expect(resolveActiveSidebarSection('/expedicao', SIDEBAR_MENU_ITEMS)).toBe('Estoque & Logística');
  });

  it('resolve Compras para /nfe-entrada', () => {
    expect(resolveActiveSidebarSection('/nfe-entrada', SIDEBAR_MENU_ITEMS)).toBe('Compras');
  });

  it('resolve Fiscal para Inbox e bases importadas', () => {
    expect(resolveActiveSidebarSection('/central-dfe', SIDEBAR_MENU_ITEMS)).toBe('Fiscal');
    expect(resolveActiveSidebarSection('/nfe-entrada-historica-importada', SIDEBAR_MENU_ITEMS)).toBe('Fiscal');
    expect(resolveActiveSidebarSection('/cte-entrada', SIDEBAR_MENU_ITEMS)).toBe('Fiscal');
  });

  it('conferência da base importada não destaca Entrada Própria no menu', () => {
    expect(isSidebarPathActive('/nfe-entrada/42/conferencia', '/nfe-entrada')).toBe(false);
  });

  it('resolve Contador para exportação', () => {
    expect(resolveActiveSidebarSection('/contador/exportar-xmls', SIDEBAR_MENU_ITEMS)).toBe('Contador');
  });
});

describe('Sidebar — colapso e destaque', () => {
  it('expandida mostra só seção ativa em /fornecedores', () => {
    render(
      <MemoryRouter initialEntries={['/fornecedores']}>
        <Sidebar isOpen onClose={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Fornecedores')).toBeInTheDocument();
    expect(screen.queryByText('Produtos')).not.toBeInTheDocument();
  });

  it('destaca Cadastros financeiros sem ativar Visão geral', () => {
    expect(isSidebarPathActive('/financeiro/cadastros', '/financeiro')).toBe(false);
    expect(isSidebarPathActive('/financeiro/cadastros', '/financeiro/cadastros')).toBe(true);
  });
});
