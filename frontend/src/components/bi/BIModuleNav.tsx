import { Link, useLocation } from 'react-router-dom';
import { navItemsForPermissoes } from './dashboardBiConfig';
import type { DashboardPermissoes } from '@/services/api/dashboard';

type BIModuleNavProps = {
  permissoes: DashboardPermissoes | null;
};

export function BIModuleNav({ permissoes }: BIModuleNavProps) {
  const location = useLocation();
  const items = navItemsForPermissoes(permissoes).filter((i) => i.modulo !== null || i.path === '/dashboard');

  if (items.length <= 1) return null;

  // -mb-6 encosta a borda inferior das abas no border-b do cabeçalho do BIPageLayout:
  // a linha do cabeçalho é a régua da barra de abas, não uma segunda borda.
  return (
    <nav
      className="-mb-6 flex gap-5 overflow-x-auto"
      aria-label="Navegação dos painéis BI"
    >
      {items.map((item) => {
        const active =
          item.path === '/dashboard'
            ? location.pathname === '/dashboard'
            : location.pathname.startsWith(item.path);
        return (
          <Link
            key={item.path}
            to={item.path}
            aria-current={active ? 'page' : undefined}
            className={
              'flex items-center gap-1.5 border-b-2 pb-2.5 pt-1.5 text-sm transition-colors ' +
              (active
                ? 'border-nexus-blue font-medium text-nexus-blue'
                : 'border-transparent text-muted-foreground hover:text-foreground')
            }
          >
            <item.icon className="h-4 w-4 shrink-0" aria-hidden />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
