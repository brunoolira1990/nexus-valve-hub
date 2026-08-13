import type { ReactNode } from 'react';
import { Inbox } from 'lucide-react';

/**
 * Estado vazio padronizado — substitui o grid cru de travessões "— —".
 * Usar dentro de cards ou tabelas quando não há dados a exibir.
 */
export const EmptyState = ({
  icon: Icon = Inbox,
  title = 'Nada por aqui',
  description,
  children,
}: {
  icon?: typeof Inbox;
  title?: string;
  description?: ReactNode;
  children?: ReactNode;
}) => (
  <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-14 text-center">
    <div className="flex h-11 w-11 items-center justify-center rounded-full bg-muted">
      <Icon className="h-5 w-5 text-muted-foreground" />
    </div>
    <div className="space-y-1">
      <p className="text-sm font-medium text-muted-foreground">{title}</p>
      {description ? (
        <p className="text-xs text-muted-foreground/80 max-w-sm">{description}</p>
      ) : null}
    </div>
    {children}
  </div>
);
