import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronDown, LayoutGrid, LogOut, Plus } from 'lucide-react';
import { NexusButton } from '@/components/nexus';
import { clearAuthSession } from '@/services/api/config';
import { clearAppContextoCache, useAppContexto } from '@/hooks/useAppContexto';
import { GlobalSearch } from '@/components/header/GlobalSearch';
import { UserMenu } from '@/components/header/UserMenu';
import { NotificacoesSino } from '@/components/layout/NotificacoesSino';
import { cn } from '@/lib/utils';

/**
 * Criações rápidas. Cada destino é uma rota real declarada em App.tsx:
 * produtos/novo, familias/nova e pedidos-compra/novo. Rotas de criação que não
 * existem (ex.: NF-e Saída) não entram aqui.
 */
const QUICK_CREATE_ITEMS = [
  { label: 'Novo Produto', path: '/produtos/novo' },
  { label: 'Nova Família', path: '/familias/nova' },
  { label: 'Novo Pedido de Compra', path: '/pedidos-compra/novo' },
];

interface TopBarProps {
  onOpenAppSwitcher: () => void;
}

export const TopBar = ({ onOpenAppSwitcher }: TopBarProps) => {
  const navigate = useNavigate();
  const { contexto } = useAppContexto();
  const quickCreateRef = useRef<HTMLDivElement>(null);
  const [quickCreateOpen, setQuickCreateOpen] = useState(false);

  useEffect(() => {
    if (!quickCreateOpen) return;
    const handleOutside = (event: MouseEvent) => {
      if (!quickCreateRef.current?.contains(event.target as Node)) setQuickCreateOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setQuickCreateOpen(false);
    };
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [quickCreateOpen]);

  const handleLogout = () => {
    clearAppContextoCache();
    clearAuthSession();
    navigate('/login');
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-card px-2 shadow-sm sm:gap-3 sm:px-4">
      <NexusButton
        type="button"
        variant="ghost"
        size="icon"
        onClick={onOpenAppSwitcher}
        aria-label="Trocar de módulo"
        title="Módulos"
        className="shrink-0"
      >
        <LayoutGrid className="h-5 w-5" />
      </NexusButton>

      <Link to="/apps" className="flex shrink-0 items-center gap-2 rounded-md px-1 py-1">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
          NV
        </span>
        <span className="hidden text-sm font-semibold tracking-wide text-foreground sm:inline">NEXUS APP</span>
      </Link>

      <div ref={quickCreateRef} className="relative shrink-0">
        <NexusButton
          type="button"
          variant="outline"
          size="sm"
          aria-haspopup="menu"
          aria-expanded={quickCreateOpen}
          aria-label="Criar rapidamente"
          title="Criar rapidamente"
          onClick={() => setQuickCreateOpen((open) => !open)}
          className={cn(
            'gap-1 border-transparent bg-nexus-orange text-white hover:bg-nexus-orange-strong hover:text-white',
            quickCreateOpen && 'bg-nexus-orange-strong',
          )}
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">Novo</span>
          <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', quickCreateOpen && 'rotate-180')} />
        </NexusButton>
        {quickCreateOpen ? (
          <div
            role="menu"
            className="absolute left-0 top-full z-[65] mt-1 w-56 rounded-md border border-border bg-popover py-1 shadow-lg"
          >
            <p className="px-3 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Criar rápido
            </p>
            {QUICK_CREATE_ITEMS.map((item) => (
              <button
                type="button"
                key={item.path}
                role="menuitem"
                className="block w-full px-3 py-2 text-left text-sm text-foreground/90 transition-colors hover:bg-muted/60"
                onClick={() => {
                  setQuickCreateOpen(false);
                  navigate(item.path);
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {/* Ordem: [Grid] [Logo] [+ Novo] [Busca] [🔔] [👤] — a busca ocupa o meio, sem spacer vazio. */}
      <div className="min-w-0 flex-1">
        <GlobalSearch />
      </div>
      <NotificacoesSino />
      <UserMenu usuario={contexto.usuario} />
      <NexusButton
        type="button"
        variant="ghost"
        size="sm"
        onClick={handleLogout}
        className="shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
        title="Sair"
      >
        <LogOut className="h-4 w-4" />
        <span className="hidden sm:inline">Sair</span>
      </NexusButton>
    </header>
  );
};

export default TopBar;
