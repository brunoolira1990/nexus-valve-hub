import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface DataTableProps {
  children: ReactNode;
  className?: string;
}

interface DataTableComponentProps extends DataTableProps {
  mobileMode?: 'scroll' | 'cards';
}

export function DataTableShell({ children, className }: DataTableProps) {
  return <div className={cn('nexus-card max-w-full overflow-x-auto overscroll-x-contain', className)}>{children}</div>;
}

export function DataTable({ children, className, mobileMode = 'scroll' }: DataTableComponentProps) {
  return (
    <table
      className={cn('nexus-table erp-table', className)}
      data-mobile-mode={mobileMode}
    >
      {children}
    </table>
  );
}

export function TableToolbar({ children, className }: DataTableProps) {
  return (
    <div className={cn('flex flex-col gap-3 mb-3 sm:flex-row sm:items-center sm:justify-between', className)}>
      {children}
    </div>
  );
}

export function TableActions({ children, className }: DataTableProps) {
  return <div className={cn('flex flex-wrap items-center gap-1 sm:flex-nowrap', className)}>{children}</div>;
}

export function TableEmptyState({ children }: { children: ReactNode }) {
  return (
    <tr>
      <td colSpan={100}>{children}</td>
    </tr>
  );
}
