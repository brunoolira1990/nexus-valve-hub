import { Link, useNavigate } from 'react-router-dom';
import { LogOut, Menu } from 'lucide-react';
import { NexusButton } from '@/components/nexus';
import { clearAuthSession } from '@/services/api/config';
import { clearAppContextoCache, useAppContexto } from '@/hooks/useAppContexto';
import { GlobalSearch } from './header/GlobalSearch';
import { EmpresaAtualBadge } from './header/EmpresaAtualBadge';
import { AmbienteBadge } from './header/AmbienteBadge';
import { UserMenu } from './header/UserMenu';
import { NotificacoesSino } from './layout/NotificacoesSino';

interface HeaderProps {
  onToggleSidebar: () => void;
  breadcrumbs?: { label: string; path?: string }[];
}

export const Header = ({ onToggleSidebar, breadcrumbs = [] }: HeaderProps) => {
  const navigate = useNavigate();
  const { contexto } = useAppContexto();

  const handleLogout = () => {
    clearAppContextoCache();
    clearAuthSession();
    navigate('/login');
  };

  return (
    <header className="min-h-14 bg-card/95 backdrop-blur-sm border-b border-border flex items-center gap-2 px-3 py-2 sm:px-4 sm:py-0 lg:px-6 shrink-0 shadow-sm">
      <div className="flex flex-1 items-center gap-2 min-w-0">
        <NexusButton type="button" variant="ghost" size="icon" className="lg:hidden shrink-0" onClick={onToggleSidebar}>
          <Menu className="h-5 w-5" />
        </NexusButton>
        <nav
          aria-label="Breadcrumb"
          className="hidden md:flex items-center gap-1 text-sm text-muted-foreground min-w-0 max-w-[180px] lg:max-w-[240px] truncate"
        >
          {breadcrumbs.map((bc, i) => (
            <span key={i} className="flex items-center gap-1 shrink-0 min-w-0">
              {i > 0 && <span className="text-border">/</span>}
              {bc.path ? (
                <Link to={bc.path} className="hover:text-foreground transition-colors truncate">
                  {bc.label}
                </Link>
              ) : (
                <span className="text-foreground font-medium truncate">{bc.label}</span>
              )}
            </span>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-1.5 sm:gap-3 min-w-0 shrink-0 justify-end">
        <div className="min-w-0 flex-shrink">
          <EmpresaAtualBadge empresa={contexto.empresa} />
        </div>
        <AmbienteBadge label={contexto.ambiente_label} />
        <NotificacoesSino />
        <UserMenu usuario={contexto.usuario} />
        <NexusButton
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          className="text-destructive hover:text-destructive hover:bg-destructive/10 shrink-0"
          title="Sair"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Sair</span>
        </NexusButton>
        <div className="min-w-0 w-8 sm:w-auto sm:max-w-[200px] lg:max-w-xs shrink-0">
          <GlobalSearch compact />
        </div>
      </div>
    </header>
  );
};
