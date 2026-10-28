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

  // Conferência da base importada (/nfe-entrada/:id/conferencia) não pertence a Entrada Própria.
  if (path === '/nfe-entrada' && /^\/nfe-entrada\/[^/]+\/conferencia$/.test(pathname)) {
    return false;
  }

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

/**
 * Rotas em que o próprio conteúdo (BIPageLayout) mostra empresa e ambiente.
 * São exatamente as 8 páginas BI abaixo de `/dashboard`; nelas o selo do Header
 * seria duplicado. Nas demais o selo continua no shell — fora do BI ele é o
 * único indicador de Homologação/Produção da tela.
 */
export function isRotaSelosNoConteudo(pathname: string): boolean {
  return pathname === '/dashboard' || pathname.startsWith('/dashboard/');
}

/**
 * Módulo que justifica a Sidebar: precisa ter submenu próprio.
 *
 * Dashboard fica de fora — as abas (Visão geral, Comercial, ...) já são
 * renderizadas no conteúdo por BIModuleNav, então uma sidebar só com o
 * cabeçalho seria um painel vazio. Blocos sem children (Notificações,
 * Contábil) e rotas fora do menu também ficam sem Sidebar.
 */
export function resolveSidebarModule<T extends SidebarPathItem>(
  pathname: string,
  items: T[],
): T | null {
  const label = resolveActiveSidebarSection(pathname, items);
  const active = items.find((item) => item.label === label);
  if (!active || active.dashboardNav) return null;
  return active.children?.length ? active : null;
}
