import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
  className?: string;
}

const sizeMap = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
};

export function LoadingSpinner({ size = 'md', label, className }: LoadingSpinnerProps) {
  return (
    <div className={cn('inline-flex items-center gap-2 text-muted-foreground', className)} role="status">
      <Loader2 className={cn('animate-spin', sizeMap[size])} aria-hidden />
      {label ? <span className="text-sm">{label}</span> : null}
      {!label ? <span className="sr-only">Carregando</span> : null}
    </div>
  );
}
