import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronDown, ChevronRight, X } from 'lucide-react';
import { useDashboardPermissoes } from '@/hooks/useDashboardPermissoes';
import { navItemsForPermissoes } from '@/components/bi/dashboardBiConfig';
import { SIDEBAR_MENU_ITEMS, type SidebarChild } from '@/config/sidebarMenuConfig';
import { isSidebarPathActive, isSidebarSectionActive, resolveActiveSidebarSection } from '@/lib/sidebarNav';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

function renderChildLink(
  child: SidebarChild,
  sectionLabel: string,
  isActive: (path?: string, activeMatchPaths?: string[]) => boolean,
  onClose: () => void,
) {
  if (child.type === 'group') {
    return (
      <p
        key={`${sectionLabel}-${child.label}`}
        className="px-3 pt-2.5 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-sidebar-muted/75 first:pt-1"
      >
        {child.label}
      </p>
    );
  }

  return (
    <Link
      key={`${sectionLabel}-${child.label}`}
      to={child.path}
      onClick={onClose}
      className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors duration-150 ${
        isActive(child.path, child.activeMatchPaths)
          ? 'bg-sidebar-active text-primary-foreground font-medium shadow-sm'
          : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
      }`}
    >
      {child.label}
    </Link>
  );
}

export const Sidebar = ({ isOpen, onClose }: SidebarProps) => {
  const location = useLocation();
  const { permissoes } = useDashboardPermissoes();

  const activeSection = useMemo(
    () => resolveActiveSidebarSection(location.pathname, SIDEBAR_MENU_ITEMS),
    [location.pathname],
  );

  const [expanded, setExpanded] = useState<string[]>(() => (activeSection ? [activeSection] : []));

  useEffect(() => {
    if (activeSection) {
      setExpanded([activeSection]);
    }
  }, [activeSection]);

  const dashboardChildren = useMemo(
    () => navItemsForPermissoes(permissoes).map((item) => ({ label: item.label, path: item.path })),
    [permissoes],
  );

  const toggleExpand = (label: string) => {
    setExpanded((prev) => (prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]));
  };

  const isActive = (path?: string, activeMatchPaths?: string[]) =>
    isSidebarPathActive(location.pathname, path, activeMatchPaths);

  return (
    <>
      {isOpen ? (
        <div className="fixed inset-0 bg-foreground/30 z-40 lg:hidden" onClick={onClose} />
      ) : null}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-sidebar-bg text-sidebar-fg flex flex-col transition-transform duration-200 ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        <div className="h-14 flex items-center justify-between px-4 border-b border-sidebar-hover">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-sidebar-active flex items-center justify-center text-primary-foreground font-bold text-sm">
              NV
            </div>
            <span className="font-semibold text-sm">NEXUS APP</span>
          </Link>
          <button type="button" onClick={onClose} className="lg:hidden text-sidebar-muted hover:text-sidebar-fg">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {SIDEBAR_MENU_ITEMS.map((item) => {
            const sectionActive = isSidebarSectionActive(location.pathname, item);

            if (item.dashboardNav) {
              return (
                <div key={item.label}>
                  <button
                    type="button"
                    onClick={() => toggleExpand(item.label)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-150 ${
                      sectionActive
                        ? 'bg-sidebar-active text-primary-foreground font-medium shadow-sm'
                        : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                    }`}
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {expanded.includes(item.label) ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                  </button>
                  {expanded.includes(item.label) ? (
                    <div className="ml-3 pl-3 border-l border-sidebar-hover/80 mb-1 space-y-0.5">
                      {dashboardChildren.map((child) => (
                        <Link
                          key={child.path}
                          to={child.path}
                          onClick={onClose}
                          className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors duration-150 ${
                            isActive(child.path)
                              ? 'bg-sidebar-active text-primary-foreground font-medium shadow-sm'
                              : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                          }`}
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            }

            if (item.children) {
              return (
                <div key={item.label}>
                  <button
                    type="button"
                    onClick={() => toggleExpand(item.label)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-150 ${
                      sectionActive
                        ? 'bg-sidebar-active/90 text-primary-foreground font-medium'
                        : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                    }`}
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {expanded.includes(item.label) ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                  </button>
                  {expanded.includes(item.label) ? (
                    <div className="ml-3 pl-3 border-l border-sidebar-hover/80 space-y-0.5 mb-1">
                      {item.children.map((child) => renderChildLink(child, item.label, isActive, onClose))}
                    </div>
                  ) : null}
                </div>
              );
            }

            return (
              <Link
                key={item.label}
                to={item.path!}
                onClick={onClose}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-150 ${
                  isActive(item.path)
                    ? 'bg-sidebar-active text-primary-foreground font-medium shadow-sm'
                    : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg'
                }`}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
    </>
  );
};
