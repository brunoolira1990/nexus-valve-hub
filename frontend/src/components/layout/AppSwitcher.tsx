import { useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import {
  SIDEBAR_MENU_ITEMS,
  type SidebarLinkChild,
  type SidebarMenuItem,
} from '@/config/sidebarMenuConfig';
import { DASHBOARD_NAV_ITEMS } from '@/components/bi/dashboardBiConfig';
import { resolveActiveSidebarSection } from '@/lib/sidebarNav';
import { cn } from '@/lib/utils';

/**
 * Grade de módulos no padrão Odoo. Cada entrada é um bloco real de
 * SIDEBAR_MENU_ITEMS: a rota raiz e a descrição saem dos links que já existem
 * no menu, nenhuma rota é inventada aqui.
 */
export const APP_SWITCHER_PRIMARY_SECTIONS = [
  'Dashboard',
  'Catálogo',
  'Compras',
  'Comercial',
  'Estoque & Logística',
  'Fiscal',
  'Qualidade',
  'Financeiro',
] as const;

/** Blocos que não são módulos, mas continuam alcançáveis pelo grid. */
export const APP_SWITCHER_OTHER_SECTIONS = [
  'Cadastros',
  'CRM',
  'Gestão de Resultado',
  'Folha / RH',
  'Contábil',
  'Contador',
  'Notificações',
] as const;

export type AppSwitcherModule = {
  label: string;
  path: string;
  descricao: string;
  icon: SidebarMenuItem['icon'];
};

function linkChildren(item: SidebarMenuItem): SidebarLinkChild[] {
  if (item.dashboardNav) {
    return DASHBOARD_NAV_ITEMS.map((nav) => ({ type: 'link', label: nav.label, path: nav.path }));
  }
  return (item.children ?? []).filter((child): child is SidebarLinkChild => child.type === 'link');
}

/** Rota raiz do bloco: o próprio path, ou o primeiro link quando há submenu. */
function rootPath(item: SidebarMenuItem, links: SidebarLinkChild[]): string | null {
  if (item.path) return item.path;
  if (item.dashboardNav) return '/dashboard';
  return links[0]?.path ?? null;
}

export function buildAppSwitcherModules(labels: readonly string[]): AppSwitcherModule[] {
  return labels
    .map((label) => SIDEBAR_MENU_ITEMS.find((item) => item.label === label))
    .filter((item): item is SidebarMenuItem => Boolean(item))
    .map((item) => {
      const links = linkChildren(item);
      const path = rootPath(item, links);
      if (!path) return null;
      return {
        label: item.label,
        path,
        descricao: links.slice(0, 3).map((link) => link.label).join(' · '),
        icon: item.icon,
      };
    })
    .filter((module): module is AppSwitcherModule => module !== null);
}

interface AppSwitcherProps {
  open: boolean;
  onClose: () => void;
}

export const AppSwitcher = ({ open, onClose }: AppSwitcherProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const panelRef = useRef<HTMLDivElement>(null);
  const primary = useMemo(() => buildAppSwitcherModules(APP_SWITCHER_PRIMARY_SECTIONS), []);
  const others = useMemo(() => buildAppSwitcherModules(APP_SWITCHER_OTHER_SECTIONS), []);
  const activeLabel = useMemo(
    () => resolveActiveSidebarSection(location.pathname, SIDEBAR_MENU_ITEMS),
    [location.pathname],
  );

  useEffect(() => {
    if (!open) return;
    const handleOutside = (event: MouseEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, onClose]);

  if (!open || typeof document === 'undefined') return null;

  const renderCards = (modules: AppSwitcherModule[]) => (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {modules.map((module) => (
        <button
          type="button"
          key={`${module.label}-${module.path}`}
          onClick={() => {
            onClose();
            navigate(module.path);
          }}
          className={cn(
            'flex items-start gap-3 rounded-lg border p-3 text-left transition-colors',
            module.label === activeLabel
              ? 'border-primary/40 bg-primary/5'
              : 'border-border bg-background hover:border-primary/30 hover:bg-muted/60',
          )}
        >
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <module.icon className="h-5 w-5" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold text-foreground">{module.label}</span>
            <span className="mt-0.5 block line-clamp-2 text-xs text-muted-foreground">{module.descricao}</span>
          </span>
        </button>
      ))}
    </div>
  );

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-foreground/30 p-4 sm:p-6">
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Trocar de módulo"
        className="mt-[6vh] max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-border bg-card shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Módulos</p>
            <p className="text-xs text-muted-foreground">Selecione um módulo para ver seus menus</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar módulos"
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-4 p-3">
          {renderCards(primary)}
          <div>
            <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Outras áreas
            </p>
            {renderCards(others)}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
};

export default AppSwitcher;
