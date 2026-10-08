import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';
import { statusToneClasses, type StatusTone } from '@/design-system/tokens';
import { cn } from '@/lib/utils';

type Props = {
  badge: ResumoAtendimentoOperacional['badges'][number];
  className?: string;
};

const variantToTone: Record<string, StatusTone> = {
  neutral: 'neutral',
  info: 'info',
  warning: 'warning',
  success: 'success',
  danger: 'danger',
};

export function AtendimentoOperacionalBadge({ badge, className }: Props) {
  const tone = variantToTone[badge.variant] ?? 'neutral';
  const toneClass = statusToneClasses[tone].soft;
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap', toneClass, className)}>
      {badge.label}
    </span>
  );
}
