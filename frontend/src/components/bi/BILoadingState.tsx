import { Loader2 } from 'lucide-react';

export function BILoadingState({ message = 'Carregando indicadores…' }: { message?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin text-primary" />
      {message}
    </div>
  );
}
