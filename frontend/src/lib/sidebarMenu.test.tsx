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
});

describe('sidebarNav — seção ativa', () => {
  it('resolve Catálogo para /corridas', () => {
    expect(resolveActiveSidebarSection('/corridas', SIDEBAR_MENU_ITEMS)).toBe('Catálogo');
  });

  it('resolve Estoque & Logística para /expedicao', () => {
    expect(resolveActiveSidebarSection('/expedicao', SIDEBAR_MENU_ITEMS)).toBe('Estoque & Logística');
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
