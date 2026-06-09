import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { friendlyOperationalMessage } from '@/lib/operationalUi';

export type OperationalMessageVariant = 'info' | 'success' | 'warning' | 'error';

const VARIANT_CLASS: Record<OperationalMessageVariant, string> = {
  info: 'border-border bg-muted/30 text-foreground',
  success: 'border-emerald-600/30 bg-emerald-600/5 text-emerald-900 dark:text-emerald-100',
  warning: 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100',
  error: 'border-destructive/40 bg-destructive/5 text-destructive',
};

export type OperationalMessageProps = {
  /** Texto bruto (será traduzido se técnico) ou mensagem já amigável. */
  message?: string | null;
  title?: string;
  variant?: OperationalMessageVariant;
  /** Quando true, exibe message literalmente (sem tradução). */
  raw?: boolean;
  children?: ReactNode;
  className?: string;
};

/** Mensagem operacional: o que aconteceu + orientação ao usuário. */
export function OperationalMessage({
  message,
  title,
  variant = 'info',
  raw = false,
  children,
  className,
}: OperationalMessageProps) {
  const body = message
    ? raw
      ? message
      : friendlyOperationalMessage(message)
    : null;

  if (!body && !children && !title) return null;

  return (
    <div className={cn('rounded-md border p-3 text-sm space-y-1', VARIANT_CLASS[variant], className)}>
      {title ? <p className="font-semibold text-[13px]">{title}</p> : null}
      {body ? <p className="text-xs leading-relaxed opacity-95">{body}</p> : null}
      {children}
    </div>
  );
}
