import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface DataTableProps {
  children: ReactNode;
  className?: string;
}

export function DataTableShell({ children, className }: DataTableProps) {
  return <div className={cn('nexus-card overflow-x-auto', className)}>{children}</div>;
}

export function DataTable({ children, className }: DataTableProps) {
  return <table className={cn('nexus-table erp-table', className)}>{children}</table>;
}

export function TableToolbar({ children, className }: DataTableProps) {
  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-3 mb-3', className)}>
      {children}
    </div>
  );
}

export function TableActions({ children, className }: DataTableProps) {
  return <div className={cn('flex items-center gap-1', className)}>{children}</div>;
}

export function TableEmptyState({ children }: { children: ReactNode }) {
  return (
    <tr>
      <td colSpan={100}>{children}</td>
    </tr>
  );
}
