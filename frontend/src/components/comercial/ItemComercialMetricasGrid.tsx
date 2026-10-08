import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/** Grid de unidade, quantidade, preço, desconto e total (Comercial 2.4). */
export function ItemComercialMetricasGrid({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 sm:grid-cols-2 gap-2 items-end',
        'lg:grid-cols-[minmax(160px,1fr)_minmax(120px,1fr)_minmax(140px,1fr)_minmax(120px,1fr)_minmax(140px,1fr)]',
        className,
      )}
    >
      {children}
    </div>
  );
}
