import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { ChevronDown, User } from 'lucide-react';
import type { AppContextoUsuario } from '@/services/api/appContexto';
import { getUsuarioNomeCurto, getUsuarioNomeExibicao } from '@/lib/usuarioExibicao';
import { cn } from '@/lib/utils';

type Props = {
  usuario: AppContextoUsuario;
};

type MenuPos = {
  top: number;
  right: number;
};

export function UserMenu({ usuario }: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<MenuPos | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const nomeExibicao = getUsuarioNomeExibicao(usuario);
  const nomeCurto = getUsuarioNomeCurto(usuario);

  const updatePosition = () => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    setPos({
      top: rect.bottom + 4,
      right: Math.max(8, window.innerWidth - rect.right),
    });
  };

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      const target = e.target as Node;
      if (rootRef.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  const menu =
    open && pos ? (
      <div
        ref={menuRef}
        role="menu"
        className="fixed z-[60] w-64 rounded-md border border-border bg-popover shadow-lg py-1"
        style={{ top: pos.top, right: pos.right }}
      >
        <div className="px-3 py-2 border-b border-border space-y-0.5">
          <p className="text-sm font-medium truncate">{nomeExibicao}</p>
          {usuario.username ? (
            <p className="text-xs text-muted-foreground truncate">Login: {usuario.username}</p>
          ) : null}
          {usuario.email ? (
            <p className="text-xs text-muted-foreground truncate">E-mail: {usuario.email}</p>
          ) : null}
          {usuario.perfil_label ? (
            <p className="text-xs text-muted-foreground">Perfil: {usuario.perfil_label}</p>
          ) : null}
        </div>
        <Link
          to="/minha-conta"
          role="menuitem"
          className="block px-3 py-2 text-sm hover:bg-muted/60"
          onClick={() => setOpen(false)}
        >
          Minha conta
        </Link>
        <Link
          to="/minha-conta/alterar-senha"
          role="menuitem"
          className="block px-3 py-2 text-sm hover:bg-muted/60"
          onClick={() => setOpen(false)}
        >
          Alterar senha
        </Link>
      </div>
    ) : null;

  return (
    <div ref={rootRef} className="relative min-w-0">
      <button
        ref={buttonRef}
        type="button"
        className={cn(
          'flex items-center gap-1.5 text-sm pl-2 pr-1 py-1.5 rounded-md border-l border-border',
          'hover:text-primary hover:bg-muted/50 transition-colors min-w-0 max-w-[120px] sm:max-w-[160px] md:max-w-[220px]',
          'outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          open && 'bg-muted/50 text-primary',
        )}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Menu do usuário ${nomeExibicao}`}
        title={nomeExibicao}
        onClick={() => setOpen((v) => !v)}
      >
        <User className="h-4 w-4 text-muted-foreground shrink-0" />
        <span className="truncate text-foreground/90 sm:hidden">{nomeCurto}</span>
        <span className="hidden sm:inline truncate text-foreground/90">{nomeExibicao}</span>
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>

      {typeof document !== 'undefined' && menu ? createPortal(menu, document.body) : null}
    </div>
  );
}
