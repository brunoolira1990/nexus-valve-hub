import { Link, useNavigate } from 'react-router-dom';
import { LogOut, Menu, User } from 'lucide-react';

interface HeaderProps {
  onToggleSidebar: () => void;
  breadcrumbs?: { label: string; path?: string }[];
}

export const Header = ({ onToggleSidebar, breadcrumbs = [] }: HeaderProps) => {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  return (
    <header className="h-14 bg-card border-b border-border flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-3">
        <button onClick={onToggleSidebar} className="erp-btn-ghost erp-btn-sm lg:hidden">
          <Menu className="h-5 w-5" />
        </button>
        <nav className="flex items-center gap-1 text-sm text-muted-foreground">
          {breadcrumbs.map((bc, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span>/</span>}
              {bc.path ? (
                <Link to={bc.path} className="hover:text-foreground transition-colors">{bc.label}</Link>
              ) : (
                <span className="text-foreground font-medium">{bc.label}</span>
              )}
            </span>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm">
          <User className="h-4 w-4 text-muted-foreground" />
          <span className="hidden sm:inline">Admin</span>
        </div>
        <button onClick={handleLogout} className="erp-btn-ghost erp-btn-sm text-destructive" title="Sair">
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Sair</span>
        </button>
      </div>
    </header>
  );
};
