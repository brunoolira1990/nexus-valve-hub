import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, LayoutGrid, X } from 'lucide-react';
import { SIDEBAR_MENU_ITEMS, type SidebarChild } from '@/config/sidebarMenuConfig';
import { isSidebarPathActive, resolveSidebarModule } from '@/lib/sidebarNav';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  /** Abre o grid de módulos (TopBar/MainLayout). Opcional para manter chamadas antigas válidas. */
  onOpenAppSwitcher?: () => void;
}

function childKey(sectionLabel: string, child: SidebarChild) {
  return `${sectionLabel}-${child.label}`;
}

export const Sidebar = ({ isOpen, onClose, onOpenAppSwitcher }: SidebarProps) => {
  const location = useLocation();

  /**
   * Padrão Odoo: a Sidebar mostra apenas o submenu do módulo ativo — e só
   * existe quando há submenu. Dashboard, blocos sem children e rotas fora do
   * menu renderizam nada (trocar de módulo é feito pelo grid da TopBar).
   */
  const module = resolveSidebarModule(location.pathname, SIDEBAR_MENU_ITEMS);

  const isActive = (path?: string, activeMatchPaths?: string[]) =>
    isSidebarPathActive(location.pathname, path, activeMatchPaths);

  if (!module) return null;

  const children = module.children ?? [];
  const ModuleIcon = module.icon;

  return (
    <>
      {isOpen ? (
        <div className="fixed left-0 right-0 top-14 bottom-0 bg-foreground/30 z-40 lg:hidden" onClick={onClose} />
      ) : null}
      <aside
        className={`fixed lg:static left-0 top-14 bottom-0 z-50 w-64 bg-sidebar-bg text-sidebar-fg flex flex-col transition-transform duration-200 ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        <div className="h-14 shrink-0 flex items-center justify-between gap-2 border-b border-sidebar-hover px-3">
          <div className="flex min-w-0 items-center gap-2">
            <ModuleIcon className="h-4 w-4 shrink-0 text-sidebar-muted" />
            <span className="truncate text-sm font-semibold">{module.label}</span>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {onOpenAppSwitcher ? (
              <button
                type="button"
                onClick={onOpenAppSwitcher}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-sidebar-muted transition-colors hover:bg-sidebar-hover hover:text-sidebar-fg"
                title="Trocar de módulo"
              >
                <LayoutGrid className="h-4 w-4" />
                <span className="hidden xl:inline">Trocar</span>
                <ChevronRight className="h-4 w-4" />
              </button>
            ) : null}
            <button type="button" onClick={onClose} className="lg:hidden text-sidebar-muted hover:text-sidebar-fg">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-px">
          {children.map((child) =>
            child.type === 'group' ? (
              <p
                key={childKey(module.label, child)}
                className="border-l-[3px] border-transparent px-3 pt-2.5 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-sidebar-muted first:pt-1"
              >
                {child.label}
              </p>
            ) : (
              <Link
                key={childKey(module.label, child)}
                to={child.path}
                onClick={onClose}
                className={`flex items-center gap-2 rounded-r-md border-l-[3px] px-3 py-1.5 text-[13px] transition-colors duration-150 ${
                  isActive(child.path, child.activeMatchPaths)
                    ? 'border-nexus-orange bg-sidebar-active font-medium text-sidebar-fg'
                    : 'border-transparent text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                }`}
              >
                {child.label}
              </Link>
            ),
          )}
        </nav>
      </aside>
    </>
  );
};
