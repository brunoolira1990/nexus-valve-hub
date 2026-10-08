import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PageContainerProps {
  children: ReactNode;
  className?: string;
  /** Largura máxima do conteúdo (default: full dentro do main). */
  narrow?: boolean;
}

export function PageContainer({ children, className, narrow }: PageContainerProps) {
  return (
    <div
      className={cn(
        'w-full mx-auto space-y-[var(--section-gap)]',
        narrow ? 'max-w-5xl' : 'max-w-[1600px]',
        className,
      )}
    >
      {children}
    </div>
  );
}
