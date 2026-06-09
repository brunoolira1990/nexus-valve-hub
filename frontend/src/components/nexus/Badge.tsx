import { cn } from '@/lib/utils';
import type { StatusTone } from '@/design-system/tokens';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';

const toneMap: Record<BadgeVariant, string> = {
  default: 'bg-primary/10 text-primary ring-1 ring-primary/20',
  success: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  warning: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200',
  danger: 'bg-red-50 text-red-700 ring-1 ring-red-200',
  info: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200',
  neutral: 'bg-muted text-muted-foreground ring-1 ring-border',
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', toneMap[variant], className)}>
      {children}
    </span>
  );
}

export function toneToBadgeVariant(tone: StatusTone): BadgeVariant {
  if (tone === 'primary') return 'default';
  if (tone === 'preparation') return 'info';
  return tone;
}
