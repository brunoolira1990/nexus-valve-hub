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

  return (
    <nav className="flex flex-wrap gap-2 mb-6" aria-label="Navegação dos painéis BI">
      {items.map((item) => {
        const active =
          item.path === '/dashboard'
            ? location.pathname === '/dashboard'
            : location.pathname.startsWith(item.path);
        return (
          <Link
            key={item.path}
            to={item.path}
            className={
              'inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium transition-colors ' +
              (active
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground')
            }
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
