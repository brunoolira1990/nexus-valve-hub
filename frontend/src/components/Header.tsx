import { Link } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { NexusButton } from '@/components/nexus';
import { useAppContexto } from '@/hooks/useAppContexto';
import { EmpresaAtualBadge } from './header/EmpresaAtualBadge';
import { AmbienteBadge } from './header/AmbienteBadge';

interface HeaderProps {
  onToggleSidebar: () => void;
  /** Falso em rotas sem Sidebar (Dashboard, blocos isolados): o hambúrguer viraria botão morto. */
  showMenuButton?: boolean;
  /**
   * Falso quando a própria página já mostra empresa/ambiente no conteúdo (BI).
   * O padrão é `true`: fora do BI o selo de Homologação é o único aviso de
   * ambiente das 94 rotas do shell, e sumir com ele não é um ganho de layout.
   */
  mostraSelos?: boolean;
  breadcrumbs?: { label: string; path?: string }[];
}

/**
 * Segunda linha do app shell (36px): contexto da página — módulo/breadcrumb e
 * empresa+ambiente. Identidade, busca, notificações e usuário ficam na TopBar.
 */
export const Header = ({
  onToggleSidebar,
  showMenuButton = true,
  mostraSelos = true,
  breadcrumbs = [],
}: HeaderProps) => {
  const { contexto } = useAppContexto();

  return (
    <header className="min-h-9 bg-card/95 backdrop-blur-sm border-b border-border flex items-center gap-2 px-3 py-1 sm:px-4 sm:py-0 lg:px-6 shrink-0 shadow-sm">
      <div className="flex flex-1 items-center gap-2 min-w-0">
        {showMenuButton ? (
          <NexusButton
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 lg:hidden shrink-0"
            aria-label="Abrir menu"
            onClick={onToggleSidebar}
          >
            <Menu className="h-4 w-4" />
          </NexusButton>
        ) : null}
        <nav
          aria-label="Breadcrumb"
          className="hidden md:flex items-center gap-1 text-xs text-muted-foreground min-w-0 max-w-[180px] lg:max-w-[240px] truncate"
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

      {mostraSelos ? (
        <div className="flex items-center gap-1.5 sm:gap-3 min-w-0 shrink-0 justify-end">
          <div className="min-w-0 flex-shrink">
            <EmpresaAtualBadge empresa={contexto.empresa} />
          </div>
          <AmbienteBadge label={contexto.ambiente_label} />
        </div>
      ) : null}
    </header>
  );
};
