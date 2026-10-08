import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';

export type AdvancedSupportSectionProps = {
  title?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  /** Exibir apenas em dev/homologação (nunca esconde em produção se adminOnly). */
  debugOnly?: boolean;
  adminOnly?: boolean;
  warningText?: string;
  className?: string;
};

/**
 * Seção recolhível para detalhes técnicos — não compete com ações principais de negócio.
 */
export function AdvancedSupportSection({
  title = 'Avançado / Suporte técnico',
  children,
  defaultOpen = false,
  debugOnly = false,
  warningText,
  className,
}: AdvancedSupportSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (debugOnly && import.meta.env.PROD) {
    return null;
  }

  return (
    <div
      className={cn(
        'rounded-md border border-dashed border-border/80 bg-muted/20 text-xs',
        className,
      )}
    >
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-muted-foreground hover:text-foreground transition-colors"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
        <Wrench className="h-3.5 w-3.5 shrink-0 opacity-70" />
        <span className="font-medium">{title}</span>
      </button>
      {open ? (
        <div className="border-t border-border/60 px-3 py-3 space-y-2">
          {warningText ? (
            <p className="text-[11px] text-amber-800 dark:text-amber-300">{warningText}</p>
          ) : null}
          {children}
        </div>
      ) : null}
    </div>
  );
}
