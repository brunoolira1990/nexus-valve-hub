import { useEffect, useRef, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface DataTableProps {
  children: ReactNode;
  className?: string;
}

type DataTableMobileMode = 'auto' | 'scroll' | 'cards';

interface DataTableComponentProps extends DataTableProps {
  /**
   * `auto` mantém a tabela no desktop e apresenta registros em cartões no celular.
   * Use `scroll` apenas para grades analíticas em que todas as colunas precisam
   * permanecer comparáveis lado a lado.
   */
  mobileMode?: DataTableMobileMode;
}

export function DataTableShell({ children, className }: DataTableProps) {
  return <div className={cn('nexus-card max-w-full overflow-x-auto overscroll-x-contain', className)}>{children}</div>;
}

export function DataTable({ children, className, mobileMode = 'auto' }: DataTableComponentProps) {
  const tableRef = useRef<HTMLTableElement>(null);

  useEffect(() => {
    if (mobileMode === 'scroll') return;

    const table = tableRef.current;
    const headerRow = table?.tHead?.rows.item(table.tHead.rows.length - 1);
    if (!table || !headerRow) return;

    const labels = Array.from(headerRow.cells).map((header) => header.textContent?.replace(/\s+/g, ' ').trim() || 'Detalhe');

    Array.from(table.tBodies).forEach((body) => {
      Array.from(body.rows).forEach((row) => {
        Array.from(row.cells).forEach((cell, index) => {
          if (cell.colSpan > 1 || cell.dataset.label) return;
          cell.dataset.label = labels[index] || 'Detalhe';
        });
      });
    });
  }, [children, mobileMode]);

  return (
    <table
      ref={tableRef}
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
