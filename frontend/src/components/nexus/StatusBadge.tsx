import { cn } from '@/lib/utils';
import { resolveStatusToken, statusToneClasses, type StatusBadgeVariant } from '@/design-system/tokens';

interface StatusBadgeProps {
  status: string;
  variant?: StatusBadgeVariant;
  className?: string;
  tooltip?: string;
}

export function StatusBadge({ status, variant = 'soft', className, tooltip }: StatusBadgeProps) {
  const token = resolveStatusToken(status);
  const toneClass = statusToneClasses[token.tone][variant];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
        toneClass,
        token.homologacao && 'ring-2 ring-dashed ring-current/30',
        className,
      )}
      title={tooltip ?? (token.homologacao ? 'Ambiente de homologação' : undefined)}
    >
      {token.label}
    </span>
  );
}
