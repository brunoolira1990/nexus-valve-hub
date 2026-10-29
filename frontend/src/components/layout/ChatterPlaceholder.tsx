import { MessageSquare } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';

/**
 * Rail direito no padrão Odoo (chatter) — placeholder até a Sprint 3.14,
 * quando recebe mensagens, anexos e o histórico de status reais da entidade.
 */
export function ChatterPlaceholder() {
  return (
    <div data-testid="chatter-placeholder" className="space-y-4">
      <div className="flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold tracking-tight">Chatter</h3>
      </div>

      <p className="text-xs text-muted-foreground">Chatter em breve (Sprint 3.14).</p>

      <div className="flex items-start gap-3 rounded-md border border-dashed border-border p-3">
        <Avatar className="h-8 w-8">
          <AvatarFallback>NX</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="text-sm font-medium">Sem activity ainda</p>
          <p className="text-xs text-muted-foreground">
            As mensagens, anexos e mudanças de status desta entidade aparecerão aqui.
          </p>
        </div>
      </div>

      <ol className="relative ml-2 space-y-3 border-l border-border pl-4 text-xs text-muted-foreground">
        <li className="flex items-center gap-2">
          <span className="absolute -left-[5px] h-2 w-2 rounded-full bg-border" aria-hidden />
          Timeline vazia
        </li>
      </ol>
    </div>
  );
}
