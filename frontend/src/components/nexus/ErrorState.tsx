import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Erro ao carregar',
  message = 'Não foi possível carregar os dados. Tente novamente.',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        'rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-4 flex flex-col sm:flex-row sm:items-center gap-3',
        className,
      )}
    >
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-destructive">{title}</p>
          <p className="text-sm text-destructive/90 mt-0.5">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <Button type="button" variant="outline" size="sm" onClick={onRetry} className="shrink-0">
          Tentar novamente
        </Button>
      ) : null}
    </div>
  );
}
