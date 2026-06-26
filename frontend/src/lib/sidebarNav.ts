/** Rotas raiz de módulo: só coincidem exatamente (não ativam em filhas). */
const EXACT_ONLY_PATHS = new Set(['/financeiro']);

export type SidebarPathItem = {
  label: string;
  path?: string;
  dashboardNav?: boolean;
  children?: { type: string; path?: string; activeMatchPaths?: string[] }[];
};

export function isSidebarPathActive(
  pathname: string,
  path?: string,
  activeMatchPaths?: string[],
): boolean {
  if (!path) return false;
  if (pathname === path) return true;

  if (activeMatchPaths?.length) {
    const matched = activeMatchPaths.some((p) => {
      if (p === '/nfe-entrada/:id/conferencia') {
        return /^\/nfe-entrada\/[^/]+\/conferencia$/.test(pathname);
      }
      return pathname.startsWith(p);
    });
    if (matched) return true;
  }

  if (EXACT_ONLY_PATHS.has(path)) return false;
  if (path !== '/dashboard' && pathname.startsWith(`${path}/`)) return true;

  return false;
}

export function resolveActiveSidebarSection(pathname: string, items: SidebarPathItem[]): string | null {
  for (const item of items) {
    if (item.dashboardNav && pathname.startsWith('/dashboard')) {
      return item.label;
    }
    if (item.path && isSidebarPathActive(pathname, item.path)) {
      return item.label;
    }
    if (item.children) {
      for (const child of item.children) {
        if (child.type === 'link' && child.path && isSidebarPathActive(pathname, child.path, child.activeMatchPaths)) {
          return item.label;
        }
      }
    }
  }
  return null;
}

export function isSidebarSectionActive(pathname: string, item: SidebarPathItem): boolean {
  if (item.dashboardNav) return pathname.startsWith('/dashboard');
  if (item.path) return isSidebarPathActive(pathname, item.path);
  if (!item.children) return false;
  return item.children.some(
    (child) => child.type === 'link' && child.path && isSidebarPathActive(pathname, child.path, child.activeMatchPaths),
  );
}
