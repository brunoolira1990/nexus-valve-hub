import { BarChart3 } from 'lucide-react';

export function BIEmptyState({ message = 'Nenhum dado disponível para o período selecionado.' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center text-sm text-muted-foreground">
      <BarChart3 className="h-8 w-8 opacity-40" />
      <p>{message}</p>
    </div>
  );
}
