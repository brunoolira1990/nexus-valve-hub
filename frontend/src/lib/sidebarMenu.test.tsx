import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { SIDEBAR_MENU_ITEMS } from '@/config/sidebarMenuConfig';
import { Sidebar } from '@/components/Sidebar';
import {
  AppSwitcher,
  APP_SWITCHER_OTHER_SECTIONS,
  APP_SWITCHER_PRIMARY_SECTIONS,
  buildAppSwitcherModules,
} from '@/components/layout/AppSwitcher';
import { resolveActiveSidebarSection, resolveSidebarModule, isSidebarPathActive } from '@/lib/sidebarNav';

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
      'Notificações',
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
    expect(labels).toEqual(['Pedidos de Compra', 'Entrada Própria', 'Cotações com Fornecedores']);
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

describe('sidebarNav — resolveSidebarModule (quando a Sidebar existe)', () => {
  const module_ = (pathname: string) => resolveSidebarModule(pathname, SIDEBAR_MENU_ITEMS)?.label ?? null;

  it('só blocos com submenu geram Sidebar', () => {
    expect(module_('/produtos')).toBe('Catálogo');
    expect(module_('/financeiro/cadastros')).toBe('Financeiro');
    expect(module_('/empresas')).toBe('Cadastros');
    expect(module_('/familias')).toBe('Catálogo');
  });

  it('Dashboard e blocos isolados não geram Sidebar', () => {
    for (const pathname of ['/dashboard', '/dashboard/comercial', '/dashboard/financeiro', '/notificacoes', '/contabil', '/rota-inexistente', '/']) {
      expect(resolveSidebarModule(pathname, SIDEBAR_MENU_ITEMS)).toBeNull();
    }
  });

  it('o bloco devolvido é o mesmo que resolveActiveSidebarSection nomeia', () => {
    const item = resolveSidebarModule('/central-dfe', SIDEBAR_MENU_ITEMS);
    expect(item?.label).toBe(resolveActiveSidebarSection('/central-dfe', SIDEBAR_MENU_ITEMS));
    expect(item?.children?.length).toBeGreaterThan(0);
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

describe('App shell 3.8 — sidebar só com o submenu do módulo ativo', () => {
  const BLOCO_SOZINHO = ['Catálogo', 'Cadastros', 'CRM', 'Contador', 'Gestão de Resultado', 'Folha / RH'];

  it('em /dashboard a Sidebar não existe: as abas ficam no conteúdo', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Sidebar isOpen onClose={() => undefined} onOpenAppSwitcher={() => undefined} />
      </MemoryRouter>,
    );
    expect(document.querySelector('aside')).toBeNull();
    expect(document.querySelectorAll('nav')).toHaveLength(0);
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Trocar de módulo')).not.toBeInTheDocument();
  });

  it('em /dashboard/<módulo> também não há Sidebar', () => {
    for (const modulo of ['comercial', 'fiscal', 'financeiro']) {
      const { unmount } = render(
        <MemoryRouter initialEntries={[`/dashboard/${modulo}`]}>
          <Sidebar isOpen onClose={() => undefined} onOpenAppSwitcher={() => undefined} />
        </MemoryRouter>,
      );
      expect(document.querySelector('aside')).toBeNull();
      unmount();
    }
  });

  it('em /produtos mostra só Catálogo, sem nenhum outro bloco', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <Sidebar isOpen onClose={() => undefined} onOpenAppSwitcher={() => undefined} />
      </MemoryRouter>,
    );
    expect(document.querySelector('aside')).not.toBeNull();
    expect(screen.getByText('Catálogo')).toBeInTheDocument();
    expect(screen.getByText('Produtos')).toBeInTheDocument();
    expect(screen.getByText('Famílias')).toBeInTheDocument();
    expect(screen.getByText('Materiais')).toBeInTheDocument();
    expect(screen.getByText('Corridas / Lotes')).toBeInTheDocument();
    expect(screen.queryByText('Inbox Fiscal')).not.toBeInTheDocument();
    expect(screen.queryByText('Pedidos de Compra')).not.toBeInTheDocument();
    expect(document.querySelectorAll('nav')).toHaveLength(1);
    for (const label of BLOCO_SOZINHO.filter((l) => l !== 'Catálogo')) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });

  it('em /central-dfe mostra só Fiscal, preservando os subgrupos', () => {
    render(
      <MemoryRouter initialEntries={['/central-dfe']}>
        <Sidebar isOpen onClose={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Fiscal')).toBeInTheDocument();
    expect(screen.getByText('Bases / Histórico')).toBeInTheDocument();
    expect(screen.queryByText('Produtos')).not.toBeInTheDocument();
  });

  it('em /notificacoes (bloco sem submenu) não há Sidebar', () => {
    render(
      <MemoryRouter initialEntries={['/notificacoes']}>
        <Sidebar isOpen onClose={() => undefined} onOpenAppSwitcher={() => undefined} />
      </MemoryRouter>,
    );
    expect(document.querySelector('aside')).toBeNull();
    expect(screen.queryByText('Voltar para Dashboard')).not.toBeInTheDocument();
    for (const label of BLOCO_SOZINHO) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });

  it('em /contabil (bloco sem submenu) também não há Sidebar', () => {
    render(
      <MemoryRouter initialEntries={['/contabil']}>
        <Sidebar isOpen onClose={() => undefined} />
      </MemoryRouter>,
    );
    expect(document.querySelector('aside')).toBeNull();
    expect(document.querySelectorAll('nav a')).toHaveLength(0);
  });

  it('em /empresas mostra o submenu de Cadastros', () => {
    render(
      <MemoryRouter initialEntries={['/empresas']}>
        <Sidebar isOpen onClose={() => undefined} onOpenAppSwitcher={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Cadastros')).toBeInTheDocument();
    expect(screen.getByText('Transportadoras')).toBeInTheDocument();
    expect(screen.queryByText('Produtos')).not.toBeInTheDocument();
  });

  it('todo link do menu tem entrada clicável na rota raiz do próprio bloco', () => {
    for (const item of SIDEBAR_MENU_ITEMS) {
      const links = (item.children ?? []).filter((child) => child.type === 'link');
      const root = item.path ?? links[0]?.path ?? (item.dashboardNav ? '/dashboard' : null);
      if (!root) continue;
      const { unmount } = render(
        <MemoryRouter initialEntries={[root]}>
          <Sidebar isOpen onClose={() => undefined} />
        </MemoryRouter>,
      );
      for (const link of links) {
        expect(document.querySelector(`a[href="${link.path}"]`)).not.toBeNull();
      }
      unmount();
    }
  });
});

describe('App shell 3.8 — AppSwitcher com 8 módulos + outras áreas', () => {
  it('grade primária tem os 8 módulos apontando para rotas existentes', () => {
    const modules = buildAppSwitcherModules(APP_SWITCHER_PRIMARY_SECTIONS);
    expect(modules.map((m) => m.label)).toEqual([
      'Dashboard',
      'Catálogo',
      'Compras',
      'Comercial',
      'Estoque & Logística',
      'Fiscal',
      'Qualidade',
      'Financeiro',
    ]);
    expect(modules.map((m) => m.path)).toEqual([
      '/dashboard',
      '/produtos',
      '/pedidos-compra',
      '/propostas',
      '/estoque',
      '/central-dfe',
      '/certificados',
      '/financeiro',
    ]);
  });

  it('"Outras áreas" cobre os blocos restantes, sem órfãos', () => {
    const others = buildAppSwitcherModules(APP_SWITCHER_OTHER_SECTIONS);
    expect(others.map((m) => m.path)).toEqual([
      '/empresas',
      '/crm',
      '/modulos/gestao-resultado',
      '/modulos/folha-rh',
      '/contabil',
      '/contador/exportar-xmls',
      '/notificacoes',
    ]);
    const cobertos = [
      ...APP_SWITCHER_PRIMARY_SECTIONS,
      ...APP_SWITCHER_OTHER_SECTIONS,
    ];
    expect(SIDEBAR_MENU_ITEMS.map((i) => i.label).sort()).toEqual(cobertos.slice().sort());
  });

  it('abre e lista os módulos', () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <AppSwitcher open onClose={onClose} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Estoque & Logística')).toBeInTheDocument();
    expect(screen.getByText('Outras áreas')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Notificações/ }));
    expect(onClose).toHaveBeenCalled();
  });
});
