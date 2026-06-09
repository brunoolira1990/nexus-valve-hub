/** Rotas raiz de módulo: só coincidem exatamente (não ativam em filhas). */
const EXACT_ONLY_PATHS = new Set(['/financeiro']);

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
