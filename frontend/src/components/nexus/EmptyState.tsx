import type { ReactNode } from 'react';
import { Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  title?: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: ReactNode;
  className?: string;
}

export function EmptyState({
  title = 'Nenhum registro encontrado',
  message,
  actionLabel,
  onAction,
  icon,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-12 px-4 text-center', className)}>
      <div className="mb-3 text-muted-foreground">{icon ?? <Inbox className="h-10 w-10 opacity-40" />}</div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {message ? <p className="text-sm text-muted-foreground mt-1 max-w-md">{message}</p> : null}
      {actionLabel && onAction ? (
        <Button type="button" className="mt-4" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}
